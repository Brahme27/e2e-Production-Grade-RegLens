"""End-to-end answer evaluation with an LLM judge, plus abstention calibration.

The judge (``fallback`` alias = Qwen) is a different model family from the answerer
(gpt-oss-120b), which reduces self-preference bias. For every answered question it reads
the numbered sources and the answer, and labels each sentence:
- ``supported``: is the sentence supported by ANY of the sources?   -> faithfulness
- ``cited_supports``: do the sources it CITES support it?           -> citation precision
and rates relevancy 1-5. Abstention / refusal accuracy needs no judge.

Free-tier budget: a stratified subset (default 60 questions) per pipeline.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from collections import defaultdict
from dataclasses import replace
from datetime import date
from typing import Any

from reglens.config import Settings, get_settings
from reglens.evals.ablation import BASE, ROWS
from reglens.evals.golden import GoldItem, load
from reglens.evals.retrieval_metrics import percentile
from reglens.llm.client import LLMClient, LLMUnavailableError, build_client
from reglens.log import configure_logging, get_logger
from reglens.obs.tracing import Tracer
from reglens.qa import AskRequest, QAService
from reglens.services import build_answerer, build_retriever

log = get_logger(__name__)

SUBSET = {
    "lookup": 15,
    "temporal": 10,
    "comparison": 8,
    "global": 5,
    "unanswerable": 12,
    "adversarial": 10,
}
JUDGE_ALIAS = "fallback"
JUDGE_SYSTEM = """You are a strict evaluator of a regulatory question-answering system.
You get a question, numbered source passages and an answer with citation markers like [2].
Split the answer into its factual sentences. For each sentence decide:
- "supported": true if the sources (any of them) state or directly imply it;
- "cited_supports": true if the sources it cites (its [n] markers) support it; false if it
  cites nothing or cites the wrong source.
Then rate "relevancy" 1-5: does the answer address what was asked?
Reply as JSON: {"sentences": [{"text": "...", "supported": true, "cited_supports": true}], "relevancy": 1-5}"""


def subset(items: list[GoldItem], seed: int, sizes: dict[str, int] = SUBSET) -> list[GoldItem]:
    rng = random.Random(seed)
    by_cat: dict[str, list[GoldItem]] = defaultdict(list)
    for item in items:
        by_cat[item.category].append(item)
    chosen: list[GoldItem] = []
    for category, n in sizes.items():
        pool = sorted(by_cat.get(category, []), key=lambda i: i.id)
        rng.shuffle(pool)
        chosen.extend(pool[:n])
    return chosen


def judge(llm: LLMClient, question: str, sources: str, answer: str) -> dict[str, Any] | None:
    user = f"Question: {question}\n\nSources:\n{sources}\n\nAnswer:\n{answer}"
    try:
        verdict = llm.complete_json(
            [{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": user}],
            alias=JUDGE_ALIAS,
            max_tokens=1500,
            purpose="judge",
        )
    except (LLMUnavailableError, ValueError) as exc:
        log.warning("judge_failed", error=str(exc))
        return None
    sentences = verdict.get("sentences") or []
    if not sentences:
        return None
    return {
        "faithfulness": sum(bool(s.get("supported")) for s in sentences) / len(sentences),
        "citation_precision": sum(bool(s.get("cited_supports")) for s in sentences)
        / len(sentences),
        "relevancy": float(verdict.get("relevancy", 0)) / 5,
        "sentences": sentences,
    }


def _valid_on(citation: dict[str, Any], day: date) -> bool:
    start = date.fromisoformat(citation["valid_from"]) if citation["valid_from"] else date.min
    end = date.fromisoformat(citation["valid_to"]) if citation["valid_to"] else date.max
    return start <= day < end


def evaluate(
    service: QAService, items: list[GoldItem], judge_llm: LLMClient, today: date
) -> dict[str, Any]:
    rows = []
    for item in items:
        as_of = date.fromisoformat(item.as_of) if item.as_of else None
        started = time.perf_counter()
        events = list(service.ask_stream(AskRequest(item.question, as_of)))
        latency = (time.perf_counter() - started) * 1000
        answer = next(e["answer"] for e in events if e["type"] == "final")
        sources_event = next((e for e in events if e["type"] == "sources"), None)
        row: dict[str, Any] = {
            "id": item.id,
            "category": item.category,
            "expected": item.expected,
            "abstained": answer["abstained"],
            "refused": answer.get("route") == "refused",
            "route": answer.get("route"),
            "latency_ms": round(latency),
        }
        if item.expected == "answer" and not answer["abstained"]:
            day = as_of or today
            citations = answer["citations"]
            row["temporal_ok"] = all(_valid_on(c, day) for c in citations) if citations else None
            row["verifier_ok"] = (answer.get("verification") or {}).get("ok")
            if sources_event is not None:
                numbered = format_sources_from_event(sources_event, answer)
                verdict = judge(judge_llm, item.question, numbered, answer["text"])
                if verdict:
                    row.update(
                        {k: verdict[k] for k in ("faithfulness", "citation_precision", "relevancy")}
                    )
                    row["judged_sentences"] = verdict["sentences"]
        rows.append(row)
    return {"rows": rows, "summary": summarise(rows)}


def format_sources_from_event(sources_event: dict[str, Any], answer: dict[str, Any]) -> str:
    """The judge sees the passages the answer was generated from (full text from citations)."""
    by_number = {c["number"]: c for c in answer["citations"]}
    blocks = []
    for source in sources_event["sources"]:
        cited = by_number.get(source["number"])
        text = (
            cited["text"]
            if cited
            else f"(passage from {source['title']}, para {source['ref']}; not cited)"
        )
        blocks.append(
            f"[{source['number']}] {source['regulator']} | {source['title']} | para {source['ref']}\n{text}"
        )
    return "\n\n".join(blocks)


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    unanswerable = [r for r in rows if r["expected"] == "abstain"]
    adversarial = [r for r in rows if r["expected"] == "refuse"]
    answerable = [r for r in rows if r["expected"] == "answer"]
    answered = [r for r in answerable if not r["abstained"]]
    return {
        "n": len(rows),
        "faithfulness": _mean([r["faithfulness"] for r in answered if "faithfulness" in r]),
        "citation_precision": _mean(
            [r["citation_precision"] for r in answered if "citation_precision" in r]
        ),
        "answer_relevancy": _mean([r["relevancy"] for r in answered if "relevancy" in r]),
        "abstention_accuracy": _mean([1.0 if r["abstained"] else 0.0 for r in unanswerable]),
        "refusal_accuracy": _mean(
            [1.0 if (r["refused"] or r["abstained"]) else 0.0 for r in adversarial]
        ),
        "false_abstention_rate": _mean([1.0 if r["abstained"] else 0.0 for r in answerable]),
        "temporal_correctness": _mean(
            [1.0 if r["temporal_ok"] else 0.0 for r in answered if r.get("temporal_ok") is not None]
        ),
        "verifier_pass_rate": _mean([1.0 if r.get("verifier_ok") else 0.0 for r in answered]),
        "latency_p50_ms": round(percentile([r["latency_ms"] for r in rows], 0.5)),
        "latency_p95_ms": round(percentile([r["latency_ms"] for r in answered], 0.95))
        if answered
        else None,
        "judged": sum(1 for r in answered if "faithfulness" in r),
    }


def calibrate_abstention(settings: Settings, items: list[GoldItem], today: date) -> dict[str, Any]:
    """Choose the reranker-score threshold that best separates answerable from unanswerable."""
    retriever = build_retriever(settings, today=lambda: today)
    config = replace(ROWS[-1].config, collection="reglens", top_k=8)
    scores = []
    for item in items:
        if item.category not in ("lookup", "temporal", "unanswerable"):
            continue
        as_of = date.fromisoformat(item.as_of) if item.as_of else None
        top = retriever.retrieve(item.question, config, as_of=as_of).hits
        scores.append((top[0].score if top else -99.0, item.expected == "answer"))
    best = (0.0, -99.0)
    for threshold in sorted({s for s, _ in scores}):
        tpr = sum(1 for s, a in scores if a and s >= threshold) / max(1, sum(a for _, a in scores))
        tnr = sum(1 for s, a in scores if not a and s < threshold) / max(
            1, sum(not a for _, a in scores)
        )
        balanced = (tpr + tnr) / 2
        if balanced > best[0]:
            best = (balanced, threshold)
    result = {"threshold": best[1], "balanced_accuracy": round(best[0], 3), "n": len(scores)}
    out = settings.reports_dir / "abstention.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def build_service(settings: Settings, pipeline: str, llm: LLMClient) -> QAService:
    retriever = build_retriever(settings, today=lambda: date(2026, 10, 24))
    config = replace(ROWS[-1].config, collection="reglens", top_k=8)
    if pipeline == "naive":
        config = replace(BASE, top_k=8)
    tracer = Tracer(settings.artifacts_dir / f"eval-traces-{pipeline}.jsonl")
    guard = llm if (pipeline == "final" and settings.groq_api_key) else None
    service = QAService(
        retriever, build_answerer(settings, llm), tracer, None, config, guard_llm=guard
    )
    if pipeline == "naive":  # the naive baseline has no guardrails and never abstains early
        service.answerer.abstain_threshold = -1e9
        service.guard_llm = None
    return service


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="End-to-end answer evaluation")
    parser.add_argument("--pipelines", nargs="*", default=["final", "naive"])
    parser.add_argument(
        "--calibrate", action="store_true", help="recompute the abstention threshold first"
    )
    parser.add_argument("--today", type=date.fromisoformat, default=date(2026, 10, 24))
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    golden = load(settings.evals_dir / "golden" / "golden_v1.jsonl")
    if args.calibrate:
        log.info("abstention_calibrated", **calibrate_abstention(settings, golden, args.today))
    items = subset(golden, settings.random_seed)
    llm = build_client(settings)
    report: dict[str, Any] = {}
    out = settings.reports_dir / "generation_eval.json"
    if out.exists():
        report = json.loads(out.read_text(encoding="utf-8"))
    for pipeline in args.pipelines:
        service = build_service(settings, pipeline, llm)
        chosen = items if pipeline == "final" else [i for i in items if i.expected == "answer"]
        result = evaluate(service, chosen, llm, args.today)
        report[pipeline] = result
        log.info(
            "generation_eval",
            pipeline=pipeline,
            **{k: v for k, v in result["summary"].items() if v is not None},
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    main()
