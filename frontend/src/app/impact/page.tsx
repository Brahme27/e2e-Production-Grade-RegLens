"use client";

import { useState } from "react";
import { Card, ErrorBox, Note, PageHeader, StatusBadge, Table } from "@/components/ui";
import { API, apiFetch, useApi } from "@/lib/api";
import type { Entity, ObligationRow } from "@/lib/types";

const TARGETS = [
  { doc_key: "rbi-cb-internal-ombudsman-2026@current", label: "RBI Internal Ombudsman Directions 2026", entity: "sahyadri-bank" },
  { doc_key: "pra-outsourcing@asof2026-10-24", label: "PRA Rulebook Outsourcing (Oct 2025 rewrite)", entity: "northbridge-bank" },
  { doc_key: "fca-sysc-15a@current", label: "FCA SYSC 15A Operational resilience", entity: "northbridge-bank" },
];
const STATUSES = ["covered", "partially_covered", "not_covered"] as const;

export default function ImpactPage() {
  const entities = useApi<Entity[]>("/v1/entities");
  const [target, setTarget] = useState(TARGETS[0]);
  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rows = useApi<ObligationRow[]>(runId ? `/v1/obligations?run_id=${runId}` : null);

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const state = await apiFetch<{ run_id: string; status: string }>("/v1/impact", {
        method: "POST",
        body: JSON.stringify({ doc_key: target.doc_key, entity: target.entity }),
      });
      setRunId(state.run_id);
      setStatus(state.status);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function review(row: ObligationRow, override: string | null) {
    await apiFetch(`/v1/gaps/${row.gap_id}`, {
      method: "PATCH",
      body: JSON.stringify(override ? { review_status: "overridden", status: override } : { review_status: "approved" }),
    });
    rows.reload();
  }

  async function approve() {
    if (!runId) return;
    setBusy(true);
    try {
      const state = await apiFetch<{ status: string }>(`/v1/impact/${runId}/approve`, { method: "POST" });
      setStatus(state.status);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const counts = STATUSES.map((s) => [s, rows.data?.filter((r) => r.status === s).length ?? 0] as const);
  const entityName = entities.data?.find((e) => e.id === target.entity)?.name ?? target.entity;

  return (
    <div>
      <PageHeader
        title="Change-impact board"
        subtitle="A new rule → its obligations → which internal policies already meet them → human review → tickets."
      />
      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm">
            New or changed rule
            <select
              value={target.doc_key}
              onChange={(e) => setTarget(TARGETS.find((t) => t.doc_key === e.target.value) ?? TARGETS[0])}
              className="rounded border px-2 py-1.5"
              data-testid="impact-target"
            >
              {TARGETS.map((t) => (
                <option key={t.doc_key} value={t.doc_key}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <div className="text-sm text-slate-600">
            Firm: <b>{entityName}</b>
          </div>
          <button
            type="button"
            onClick={() => void start()}
            disabled={busy}
            data-testid="impact-start"
            className="ml-auto rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {busy && !runId ? "Analysing… (about a minute)" : "Run impact analysis"}
          </button>
        </div>
        <Note>
          The firms and their policies are fictional (written for this project with deliberate gaps). The workflow pauses
          for human review: nothing becomes a ticket until a reviewer approves.
        </Note>
      </Card>

      {error && (
        <div className="mt-4">
          <ErrorBox message={error} />
        </div>
      )}

      {runId && (
        <div className="mt-6 flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <div className="rounded-lg bg-white p-3 text-sm shadow-sm">
              Run <span className="font-mono text-xs">{runId.slice(0, 8)}</span>
              <div className="font-semibold" data-testid="impact-status">
                {status.replace("_", " ")}
              </div>
            </div>
            {counts.map(([s, n]) => (
              <div key={s} className="rounded-lg bg-white p-3 text-sm shadow-sm">
                <StatusBadge status={s} />
                <div className="mt-1 text-xl font-semibold">{n}</div>
              </div>
            ))}
          </div>
          <Card title="Obligations and gap judgements">
            {rows.error && <ErrorBox message={rows.error} />}
            {rows.data && (
              <Table
                headers={["§", "Obligation", "Gap", "Why", "Review"]}
                rows={rows.data.map((r) => [
                  r.source_ref,
                  <div key="o" className="max-w-md">
                    {r.text}
                    {r.deadline && <div className="text-xs text-slate-500">deadline: {r.deadline}</div>}
                  </div>,
                  <StatusBadge key="g" status={r.status} />,
                  <div key="w" className="max-w-sm text-xs text-slate-600">
                    {r.rationale}
                    {r.policy_refs.length > 0 && <div className="mt-1 text-slate-500">{r.policy_refs.join(", ")}</div>}
                  </div>,
                  status === "awaiting_review" ? (
                    <div key="r" className="flex flex-col gap-1 text-xs">
                      <span className="text-slate-500">{r.review_status}</span>
                      <button type="button" className="rounded bg-emerald-50 px-2 py-0.5" onClick={() => void review(r, null)}>
                        Agree
                      </button>
                      <select
                        aria-label="Override gap status"
                        className="rounded border px-1"
                        value=""
                        onChange={(e) => e.target.value && void review(r, e.target.value)}
                      >
                        <option value="">Override…</option>
                        {STATUSES.filter((s) => s !== r.status).map((s) => (
                          <option key={s} value={s}>
                            {s.replace("_", " ")}
                          </option>
                        ))}
                      </select>
                    </div>
                  ) : (
                    <span key="r" className="text-xs text-slate-500">
                      {r.review_status}
                    </span>
                  ),
                ])}
              />
            )}
            <div className="mt-4 flex gap-3">
              {status === "awaiting_review" && (
                <button
                  type="button"
                  onClick={() => void approve()}
                  disabled={busy}
                  data-testid="impact-approve"
                  className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                >
                  Approve review and create tickets
                </button>
              )}
              {status === "tickets_created" && (
                <a className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white" href={`${API}/v1/impact/${runId}/tickets.csv`}>
                  Download tickets (CSV)
                </a>
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
