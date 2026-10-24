"use client";

import Link from "next/link";
import { useState } from "react";
import { Card, ErrorBox, Loading, PageHeader, RegulatorBadge, StatusBadge } from "@/components/ui";
import { useApi } from "@/lib/api";
import type { DocVersion } from "@/lib/types";

type FeedEvent = DocVersion & { date: string; event: "in_force" | "upcoming" | "superseded" };

const EVENT_LABEL = { in_force: "came into force", upcoming: "comes into force", superseded: "stopped applying" };

export default function ChangesPage() {
  const [since, setSince] = useState("2025-01-01");
  const { data, error, loading } = useApi<FeedEvent[]>(`/v1/changes?since=${since}`);
  return (
    <div>
      <PageHeader
        title="Regulatory change feed"
        subtitle="New versions coming into force, documents being repealed, and changes already scheduled for the future."
      />
      <label className="mb-4 flex items-center gap-2 text-sm text-slate-700">
        Since
        <input type="date" value={since} onChange={(e) => setSince(e.target.value)} className="rounded border px-2 py-1" />
      </label>
      <Card>
        {loading && <Loading />}
        {error && <ErrorBox message={error} />}
        <ol className="flex flex-col gap-3" data-testid="feed">
          {data?.map((e) => (
            <li key={`${e.key}-${e.event}`} className="flex gap-4 border-b border-slate-100 pb-3 last:border-0">
              <div className="w-24 shrink-0 text-sm font-semibold text-slate-700">{e.date}</div>
              <div className="text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <RegulatorBadge regulator={e.regulator} />
                  <Link href={`/documents/${e.doc_id}?version=${encodeURIComponent(e.version)}`} className="font-medium text-brand hover:underline">
                    {e.title}
                  </Link>
                  <StatusBadge status={e.event === "superseded" ? "superseded" : e.status} />
                </div>
                <div className="text-xs text-slate-500">
                  Version {e.version} {EVENT_LABEL[e.event]}
                  {e.superseded_by && e.event === "superseded" ? ` (replaced by ${e.superseded_by})` : ""}
                </div>
              </div>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}
