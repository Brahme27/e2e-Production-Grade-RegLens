"use client";

import Link from "next/link";
import { useState } from "react";
import { Card, ErrorBox, Loading, PageHeader, RegulatorBadge, StatusBadge, Table } from "@/components/ui";
import { useApi } from "@/lib/api";
import type { DocVersion } from "@/lib/types";

const FILTERS = ["ALL", "RBI", "SEBI", "FCA", "PRA"];

export default function DocumentsPage() {
  const [regulator, setRegulator] = useState("ALL");
  const { data, error, loading } = useApi<DocVersion[]>("/v1/documents");

  // one row per document: its latest version, plus how many versions we hold
  const latest = new Map<string, { version: DocVersion; count: number }>();
  for (const v of data ?? []) {
    const seen = latest.get(v.doc_id);
    if (!seen || (v.valid_from ?? "") > (seen.version.valid_from ?? "")) {
      latest.set(v.doc_id, { version: v, count: (seen?.count ?? 0) + 1 });
    } else {
      seen.count += 1;
    }
  }
  const rows = [...latest.values()]
    .filter(({ version }) => regulator === "ALL" || version.regulator === regulator)
    .sort((a, b) => a.version.regulator.localeCompare(b.version.regulator) || a.version.title.localeCompare(b.version.title));

  return (
    <div>
      <PageHeader
        title="Indexed documents"
        subtitle="Every document with its validity window. Superseded documents stay searchable for questions about the past."
      />
      <div className="mb-4 flex gap-1">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setRegulator(f)}
            aria-pressed={regulator === f}
            className={`rounded-full px-3 py-1 text-xs font-semibold ${regulator === f ? "bg-brand text-white" : "bg-white text-slate-600"}`}
          >
            {f}
          </button>
        ))}
      </div>
      <Card>
        {loading && <Loading />}
        {error && <ErrorBox message={error} />}
        {data && (
          <Table
            headers={["Regulator", "Document", "Status", "Valid from", "Valid to", "Versions", "Paragraphs"]}
            rows={rows.map(({ version: v, count }) => [
              <RegulatorBadge key="r" regulator={v.regulator} />,
              <div key="t">
                <Link className="font-medium text-brand hover:underline" href={`/documents/${v.doc_id}`}>
                  {v.title}
                </Link>
                <div className="text-xs text-slate-500">{v.doc_number}</div>
              </div>,
              <StatusBadge key="s" status={v.status} />,
              v.valid_from ?? "—",
              v.valid_to ?? "—",
              count,
              v.paragraph_count,
            ])}
          />
        )}
      </Card>
    </div>
  );
}
