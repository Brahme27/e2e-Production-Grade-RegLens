"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card, ErrorBox, Loading, PageHeader, RegulatorBadge, StatusBadge } from "@/components/ui";
import { useApi } from "@/lib/api";
import type { Change, DocVersion, Edge, ParsedDocument } from "@/lib/types";

/** "[-old words-] {+new words+}" markup rendered as red / green spans. */
export function WordDiff({ markup }: { markup: string }) {
  const parts = markup.split(/(\[-[\s\S]*?-\]|\{\+[\s\S]*?\+\})/g);
  return (
    <span>
      {parts.map((p, i) =>
        p.startsWith("[-") ? (
          <del key={i} className="bg-rose-100 text-rose-800">
            {p.slice(2, -2)}
          </del>
        ) : p.startsWith("{+") ? (
          <ins key={i} className="bg-emerald-100 text-emerald-800 no-underline">
            {p.slice(2, -2)}
          </ins>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </span>
  );
}

function DiffView({ docId, versions }: { docId: string; versions: DocVersion[] }) {
  const [from, setFrom] = useState(versions[0]?.version ?? "");
  const [to, setTo] = useState(versions[versions.length - 1]?.version ?? "");
  const path = from && to && from !== to ? `/v1/documents/${docId}/diff?from=${from}&to=${to}` : null;
  const { data, error, loading } = useApi<{ summary: Record<string, number>; changes: Change[] }>(path);
  return (
    <Card title="What changed between versions">
      <div className="mb-3 flex gap-3 text-sm">
        <select value={from} onChange={(e) => setFrom(e.target.value)} className="rounded border px-2 py-1" aria-label="From version">
          {versions.map((v) => (
            <option key={v.version} value={v.version}>
              {v.version} ({v.valid_from})
            </option>
          ))}
        </select>
        <span>→</span>
        <select value={to} onChange={(e) => setTo(e.target.value)} className="rounded border px-2 py-1" aria-label="To version">
          {versions.map((v) => (
            <option key={v.version} value={v.version}>
              {v.version} ({v.valid_from})
            </option>
          ))}
        </select>
      </div>
      {loading && <Loading />}
      {error && <ErrorBox message={error} />}
      {data && (
        <>
          <p className="mb-3 text-xs text-slate-600" data-testid="diff-summary">
            {data.summary.substantive} substantive changes · {data.summary.added} added · {data.summary.removed} removed ·{" "}
            {data.summary.changed} changed · {data.summary.unchanged} unchanged
          </p>
          <ul className="flex flex-col gap-3 text-sm">
            {data.changes
              .filter((c) => c.substantive)
              .map((c) => (
                <li key={`${c.kind}-${c.ref}`} className="rounded border border-slate-200 p-3">
                  <div className="mb-1 text-xs font-semibold text-slate-500">
                    §{c.ref} · {c.kind}
                  </div>
                  <WordDiff markup={c.word_diff} />
                </li>
              ))}
          </ul>
        </>
      )}
    </Card>
  );
}

export function DocumentView({
  docId,
  initialVersion,
  highlightRef,
}: {
  docId: string;
  initialVersion: string | null;
  highlightRef: string | null;
}) {
  const info = useApi<{ versions: DocVersion[]; edges: Edge[] }>(`/v1/documents/${docId}`);
  const versions = info.data?.versions ?? [];
  const [chosen, setChosen] = useState<string | null>(initialVersion);
  const version = chosen ?? versions[versions.length - 1]?.version ?? null;
  const text = useApi<ParsedDocument>(version ? `/v1/documents/${docId}/versions/${encodeURIComponent(version)}` : null);

  useEffect(() => {
    if (!highlightRef || !text.data) return;
    const el = document.getElementById(`para-${highlightRef}`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlightRef, text.data]);

  if (info.error) return <ErrorBox message={info.error} />;
  if (!info.data) return <Loading />;
  const current = versions.find((v) => v.version === version) ?? versions[versions.length - 1];

  return (
    <div>
      <PageHeader title={current?.title ?? docId} subtitle={current?.doc_number ?? undefined} />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-6 lg:col-span-2">
          <Card title={`Text · version ${version ?? "—"}`}>
            {text.loading && <Loading />}
            {text.error && <ErrorBox message={text.error} />}
            <ol className="flex flex-col gap-3" data-testid="paragraphs">
              {text.data?.paragraphs.map((p, i) => (
                <li
                  key={`${p.ref}-${i}`}
                  id={`para-${p.ref}`}
                  className={`rounded p-2 text-sm ${p.ref === highlightRef ? "highlight ring-2 ring-amber-300" : ""}`}
                >
                  <div className="mb-1 flex flex-wrap gap-2 text-xs text-slate-500">
                    <span className="font-semibold text-slate-700">§{p.ref}</span>
                    {p.section_path.length > 0 && <span>{p.section_path.join(" › ")}</span>}
                    {p.effective_from && <span>· in force since {p.effective_from}</span>}
                    {p.kind !== "paragraph" && <span className="rounded bg-slate-100 px-1">{p.kind}</span>}
                  </div>
                  <p className="whitespace-pre-wrap text-slate-800">{p.text}</p>
                </li>
              ))}
            </ol>
          </Card>
          {versions.length > 1 && <DiffView docId={docId} versions={versions} />}
        </div>
        <div className="flex flex-col gap-6">
          <Card title="Versions">
            <ol className="flex flex-col gap-2 text-sm">
              {versions.map((v) => (
                <li key={v.version}>
                  <button
                    type="button"
                    onClick={() => setChosen(v.version)}
                    className={`w-full rounded border p-2 text-left ${v.version === version ? "border-brand bg-brand-light" : "border-slate-200"}`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{v.version}</span>
                      <StatusBadge status={v.status} />
                    </div>
                    <div className="text-xs text-slate-500">
                      {v.valid_from ?? "?"} → {v.valid_to ?? "now"}
                    </div>
                  </button>
                </li>
              ))}
            </ol>
            {current && (
              <div className="mt-3 flex items-center gap-2 text-xs">
                <RegulatorBadge regulator={current.regulator} />
                <a className="text-brand underline" href={current.url} target="_blank" rel="noreferrer">
                  Official source
                </a>
              </div>
            )}
          </Card>
          <Card title="Supersession">
            {info.data.edges.length === 0 && <p className="text-xs text-slate-500">No repeal or amendment links.</p>}
            <ul className="flex flex-col gap-2 text-xs">
              {info.data.edges.map((e) => (
                <li key={`${e.source}-${e.target}-${e.type}`} className="rounded bg-slate-50 p-2">
                  {e.source === docId ? (
                    <>
                      <b>{e.type === "SUPERSEDES" ? "Replaces" : "Amends"}</b>{" "}
                      {e.target.startsWith("ext:") ? e.target.slice(4) : <Link className="text-brand underline" href={`/documents/${e.target}`}>{e.target}</Link>}
                    </>
                  ) : (
                    <>
                      <b>{e.type === "SUPERSEDES" ? "Replaced by" : "Amended by"}</b>{" "}
                      <Link className="text-brand underline" href={`/documents/${e.source}`}>{e.source}</Link>
                    </>
                  )}
                  {e.effective && <span> · from {e.effective}</span>}
                  <span className="ml-1 rounded bg-white px-1 text-slate-500">{e.method}</span>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}
