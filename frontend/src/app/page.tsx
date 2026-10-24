"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { Card, ErrorBox, PageHeader, RegulatorBadge, StatusBadge } from "@/components/ui";
import { apiFetch, streamSSE } from "@/lib/api";
import type { Answer, Citation, Regulator, Source } from "@/lib/types";

const REGULATORS: Regulator[] = ["RBI", "SEBI", "FCA", "PRA"];
const EXAMPLES: { q: string; asOf?: string }[] = [
  { q: "What must a bank's board approve before outsourcing a material activity under RBI rules?" },
  { q: "How often must high-risk customers' KYC be updated by commercial banks?" },
  { q: "What did the PRA expect from firms on outsourcing?", asOf: "2025-06-30" },
  { q: "How do the FCA and the PRA approach operational resilience impact tolerances?" },
  { q: "What are the main themes of the FCA Consumer Duty?" },
];

/** Answer text with [n] markers turned into clickable citation chips. */
function AnswerText({ text, onCite }: { text: string; onCite: (n: number) => void }) {
  const parts = text.split(/(\[\d{1,2}\])/g);
  return (
    <div className="whitespace-pre-wrap leading-relaxed text-slate-800">
      {parts.map((part, i) => {
        const m = /^\[(\d{1,2})\]$/.exec(part);
        return m ? (
          <button
            key={i}
            type="button"
            onClick={() => onCite(Number(m[1]))}
            className="mx-0.5 rounded bg-brand-light px-1 text-xs font-semibold text-brand hover:bg-brand hover:text-white"
            aria-label={`Show source ${m[1]}`}
          >
            {m[1]}
          </button>
        ) : (
          <span key={i}>{part}</span>
        )
      })}
    </div>
  );
}

function CitationPanel({ citation }: { citation: Citation }) {
  const version = citation.doc_key.split("@")[1];
  return (
    <Card title={`Source ${citation.number}`}>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <RegulatorBadge regulator={citation.regulator} />
        <span className="font-semibold">{citation.label}</span>
        <StatusBadge status={citation.status} />
      </div>
      <p className="mt-1 text-xs text-slate-500">{citation.title}</p>
      <p className="mt-1 text-xs text-slate-500">
        Valid {citation.valid_from ?? "?"} → {citation.valid_to ?? "now"}
      </p>
      <blockquote className="mt-3 max-h-72 overflow-y-auto whitespace-pre-wrap border-l-4 border-accent pl-3 text-sm text-slate-700">
        {citation.text}
      </blockquote>
      <div className="mt-3 flex gap-4 text-xs">
        <Link
          className="text-brand underline"
          href={`/documents/${citation.doc_id}?version=${encodeURIComponent(version)}&ref=${encodeURIComponent(citation.ref)}`}
        >
          Open in document
        </Link>
        {citation.url && (
          <a className="text-brand underline" href={citation.url} target="_blank" rel="noreferrer">
            Regulator&apos;s website
          </a>
        )}
      </div>
    </Card>
  );
}

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [asOf, setAsOf] = useState("");
  const [regulators, setRegulators] = useState<Regulator[]>([]);
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [meta, setMeta] = useState<{ route?: string; as_of?: string }>({});
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);

  async function ask(q = question, date = asOf) {
    if (q.trim().length < 3) return;
    abort.current?.abort();
    abort.current = new AbortController();
    setBusy(true);
    setText("");
    setSources([]);
    setAnswer(null);
    setSelected(null);
    setError(null);
    setFeedback(null);
    setMeta({});
    try {
      await streamSSE(
        "/v1/ask",
        { question: q, as_of: date || null, regulators },
        (type, data) => {
          if (type === "sources") {
            setSources(data.sources as Source[]);
            setMeta({ route: data.route as string, as_of: data.as_of as string });
          } else if (type === "delta") {
            setText((t) => t + (data.text as string));
          } else if (type === "final") {
            const final = data.answer as Answer;
            setAnswer(final);
            setText(final.text);
          }
        },
        abort.current.signal,
      );
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "AbortError")) {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setBusy(false);
    }
  }

  async function sendFeedback(score: 1 | -1) {
    if (!answer?.trace_id) return;
    await apiFetch("/v1/feedback", { method: "POST", body: JSON.stringify({ trace_id: answer.trace_id, score }) });
    setFeedback(score > 0 ? "Thanks: marked helpful." : "Thanks: marked not helpful.");
  }

  const citation = answer?.citations.find((c) => c.number === selected) ?? null;
  const v = answer?.verification;

  return (
    <div>
      <PageHeader
        title="Ask the regulations"
        subtitle="Answers cite the exact paragraph and only use rules in force on the date you choose (today by default)."
      />
      <Card>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void ask();
          }}
          className="flex flex-col gap-3"
        >
          <label htmlFor="question" className="text-sm font-medium text-slate-700">
            Question
          </label>
          <textarea
            id="question"
            data-testid="question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={3}
            maxLength={2000}
            className="rounded-lg border border-slate-300 p-3 text-sm focus:border-brand focus:outline-none"
            placeholder="e.g. What must a bank do before outsourcing a critical function?"
          />
          <div className="flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-slate-700">
              As of
              <input
                type="date"
                data-testid="as-of"
                value={asOf}
                onChange={(e) => setAsOf(e.target.value)}
                className="rounded border border-slate-300 px-2 py-1 text-sm"
              />
            </label>
            <div className="flex items-center gap-1" role="group" aria-label="Regulators">
              {REGULATORS.map((r) => {
                const on = regulators.includes(r);
                return (
                  <button
                    key={r}
                    type="button"
                    aria-pressed={on}
                    onClick={() => setRegulators((rs) => (on ? rs.filter((x) => x !== r) : [...rs, r]))}
                    className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                      on ? "border-brand bg-brand text-white" : "border-slate-300 text-slate-600"
                    }`}
                  >
                    {r}
                  </button>
                );
              })}
            </div>
            <button
              type="submit"
              disabled={busy}
              data-testid="ask"
              className="ml-auto rounded-lg bg-brand px-5 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {busy ? "Searching…" : "Ask"}
            </button>
          </div>
        </form>
        <div className="mt-4 flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex.q}
              type="button"
              onClick={() => {
                setQuestion(ex.q);
                setAsOf(ex.asOf ?? "");
                void ask(ex.q, ex.asOf ?? "");
              }}
              className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700 hover:bg-slate-200"
            >
              {ex.q}
              {ex.asOf ? ` (as of ${ex.asOf})` : ""}
            </button>
          ))}
        </div>
      </Card>

      {error && (
        <div className="mt-4">
          <ErrorBox message={error} />
        </div>
      )}

      {(text || busy || sources.length > 0) && (
        <div className="mt-6 grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <Card title="Answer">
              <div className="mb-3 flex flex-wrap gap-2 text-xs text-slate-500">
                {meta.route && <span className="rounded bg-slate-100 px-2 py-0.5">route: {meta.route}</span>}
                {meta.as_of && <span className="rounded bg-slate-100 px-2 py-0.5">as of {meta.as_of}</span>}
                {answer?.cached && <span className="rounded bg-slate-100 px-2 py-0.5">from cache</span>}
              </div>
              <div data-testid="answer">
                {text ? <AnswerText text={text} onCite={setSelected} /> : <p className="text-sm text-slate-500">Searching the regulations…</p>}
              </div>
              {answer && !answer.abstained && v && (
                <p
                  data-testid="verification"
                  className={`mt-4 rounded p-2 text-xs ${v.ok ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-800"}`}
                >
                  {v.ok
                    ? "Every statement cites a retrieved paragraph that supports it."
                    : `${v.uncited_sentences + v.unsupported_sentences} statement(s) need checking against the sources.`}
                </p>
              )}
              {answer && (
                <div className="mt-4 flex items-center gap-3 text-xs text-slate-500">
                  <span>{answer.disclaimer}</span>
                  {!answer.abstained && !feedback && (
                    <>
                      <button type="button" onClick={() => void sendFeedback(1)} aria-label="Helpful" className="text-lg">
                        👍
                      </button>
                      <button type="button" onClick={() => void sendFeedback(-1)} aria-label="Not helpful" className="text-lg">
                        👎
                      </button>
                    </>
                  )}
                  {feedback && <span>{feedback}</span>}
                </div>
              )}
            </Card>
          </div>
          <div className="flex flex-col gap-4">
            {citation && <CitationPanel citation={citation} />}
            <Card title="Retrieved paragraphs">
              <ol className="flex flex-col gap-2 text-sm" data-testid="sources">
                {sources.map((s) => (
                  <li key={s.number} className="flex items-start gap-2">
                    <span className="w-5 shrink-0 text-xs font-semibold text-slate-400">{s.number}</span>
                    <div>
                      <div className="flex flex-wrap items-center gap-1">
                        <RegulatorBadge regulator={s.regulator} />
                        <span className="font-medium">{s.label}</span>
                        {s.status !== "current" && <StatusBadge status={s.status} />}
                      </div>
                      <div className="text-xs text-slate-500">{s.title}</div>
                    </div>
                  </li>
                ))}
                {sources.length === 0 && (
                  <li className="text-xs text-slate-500">
                    {answer?.cached
                      ? "Answered from the cache: open a citation chip to see its paragraph."
                      : "—"}
                  </li>
                )}
              </ol>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
