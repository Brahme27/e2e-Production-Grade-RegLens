"use client";

import { Card, ErrorBox, Loading, Note, PageHeader, Stat, Table } from "@/components/ui";
import { num, pct, useApi } from "@/lib/api";

interface AblationRow {
  key: string;
  label: string;
  overall: Record<string, number>;
  latency_ms: { p50: number; p95: number };
}

interface GenerationSummary {
  faithfulness: number | null;
  citation_precision: number | null;
  answer_relevancy: number | null;
  abstention_accuracy: number | null;
  refusal_accuracy: number | null;
  false_abstention_rate: number | null;
  temporal_correctness: number | null;
  latency_p95_ms: number | null;
  n: number;
}

export default function EvaluationPage() {
  const ablation = useApi<AblationRow[]>("/v1/reports/ablation");
  const generation = useApi<Record<string, { summary: GenerationSummary }>>("/v1/reports/generation_eval");
  const supersession = useApi<Record<string, { f1: number; precision: number; recall: number }>>("/v1/reports/supersession_eval");
  const impact = useApi<{ extraction?: { f1: number; recall: number; precision: number }; gaps?: { accuracy: number; cohen_kappa: number; gap_detection_accuracy: number } }>(
    "/v1/reports/impact_eval",
  );
  const router = useApi<{ golden_accuracy: number; cv_accuracy: number }>("/v1/reports/router_eval");
  const final = generation.data?.final?.summary;

  return (
    <div>
      <PageHeader title="Evaluation" subtitle="Every number below is produced by code in the repository (uv run poe ablation / eval-answers / eval-impact)." />
      <Card title="Retrieval ablation: naive RAG → production pipeline">
        {ablation.loading && <Loading />}
        {ablation.error && <ErrorBox message={ablation.error} />}
        {ablation.data && (
          <Table
            headers={["Row", "Change", "Recall@10", "nDCG@10", "MRR", "Stale in top 5", "p95 ms"]}
            rows={ablation.data.map((r) => [
              <b key="k">{r.key}</b>,
              r.label,
              num(r.overall["recall@10"]),
              num(r.overall["ndcg@10"]),
              num(r.overall.mrr),
              pct(r.overall.stale_in_top5_rate, 0),
              r.latency_ms.p95,
            ])}
          />
        )}
        <Note>
          Retrieval metrics need no LLM, so every row is measured on all answerable golden questions. Rows marked as
          subset experiments use a fixed 30-question sample.
        </Note>
      </Card>
      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <Card title="Answers (LLM judge, stratified subset)">
          {!final && <Loading label={generation.error ?? "Loading…"} />}
          {final && (
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Faithfulness" value={num(final.faithfulness, 2)} />
              <Stat label="Citation precision" value={num(final.citation_precision, 2)} />
              <Stat label="Answer relevancy" value={num(final.answer_relevancy, 2)} />
              <Stat label="Temporal correctness" value={num(final.temporal_correctness, 2)} />
              <Stat label="Abstention on unanswerable" value={num(final.abstention_accuracy, 2)} />
              <Stat label="Refusal on adversarial" value={num(final.refusal_accuracy, 2)} />
              <Stat label="False abstention" value={num(final.false_abstention_rate, 2)} />
              <Stat label="p95 latency" value={`${final.latency_p95_ms ?? "—"} ms`} />
            </div>
          )}
        </Card>
        <Card title="Supersession, router, change impact">
          <div className="grid grid-cols-2 gap-3">
            <Stat label="Supersession F1 (rules + LLM)" value={num(supersession.data?.rules_plus_llm?.f1, 3)} hint="57 hand-labelled edges" />
            <Stat label="Router accuracy" value={num(router.data?.golden_accuracy, 3)} hint="golden set" />
            <Stat label="Obligation extraction F1" value={num(impact.data?.extraction?.f1, 2)} />
            <Stat label="Gap judgement accuracy" value={num(impact.data?.gaps?.accuracy, 2)} hint={`κ = ${num(impact.data?.gaps?.cohen_kappa, 2)}`} />
          </div>
        </Card>
      </div>
    </div>
  );
}
