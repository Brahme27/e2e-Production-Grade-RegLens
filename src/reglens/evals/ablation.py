"""The retrieval ablation: naive RAG -> production pipeline, one technique at a time.

Every row is a ``RetrievalConfig``; every row is scored on the same golden questions
(those that should be answered). Retrieval needs no LLM, so the whole table is free to run.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from datetime import date
from typing import Any

from reglens.config import Settings, get_settings
from reglens.evals.golden import GoldItem, load
from reglens.evals.retrieval_metrics import ItemScores, aggregate, percentile, score_item
from reglens.log import configure_logging, get_logger
from reglens.retrieve.pipeline import RetrievalConfig, Retriever
from reglens.services import build_retriever

log = get_logger(__name__)


@dataclass(frozen=True)
class Row:
    key: str
    label: str
    config: RetrievalConfig
    limit: int | None = None  # slow experiments run on a fixed subset of questions


BASE = RetrievalConfig(
    collection="reglens_fixed",
    mode="dense",
    reranker="none",
    candidates=30,
    top_k=10,
    temporal_filter=False,
    regulator_filter=False,
    route=False,
    diversify_global=False,
)
ROWS = [
    Row("A", "Naive: fixed ~512-token chunks, dense only", BASE),
    Row("B", "+ paragraph chunks", replace(BASE, collection="reglens_para")),
    Row(
        "C",
        "+ hybrid search (BM25 + dense, RRF)",
        replace(BASE, collection="reglens_para", mode="hybrid"),
    ),
    Row(
        "D",
        "+ cross-encoder reranker (MiniLM-L6)",
        replace(BASE, collection="reglens_para", mode="hybrid", reranker="minilm"),
    ),
    Row(
        "E1",
        "+ structural context headers",
        replace(BASE, collection="reglens_para_ctx", mode="hybrid", reranker="minilm"),
    ),
    Row(
        "E2",
        "+ LLM document summaries in context",
        replace(BASE, collection="reglens_para_ctx_sum", mode="hybrid", reranker="minilm"),
    ),
    Row(
        "F",
        "+ router, as-of and regulator filters",
        replace(
            BASE,
            collection="reglens_para_ctx_sum",
            mode="hybrid",
            reranker="minilm",
            temporal_filter=True,
            regulator_filter=True,
            route=True,
        ),
    ),
    Row(
        "G",
        "+ document-diverse retrieval for global questions",
        replace(
            BASE,
            collection="reglens_para_ctx_sum",
            mode="hybrid",
            reranker="minilm",
            temporal_filter=True,
            regulator_filter=True,
            route=True,
            diversify_global=True,
        ),
    ),
]
SIDE_ROWS = [
    Row(
        "D-bge-m3",
        "D with bge-reranker-v2-m3 (30-question subset; ~36 s/question on CPU)",
        replace(BASE, collection="reglens_para", mode="hybrid", reranker="bge-m3"),
        limit=30,
    ),
    Row(
        "D-subset",
        "D with MiniLM on the same 30-question subset (for a fair comparison)",
        replace(BASE, collection="reglens_para", mode="hybrid", reranker="minilm"),
        limit=30,
    ),
    Row(
        "C-sparse",
        "BM25 only (paragraph chunks)",
        replace(BASE, collection="reglens_para", mode="sparse"),
    ),
]


def run_row(retriever: Retriever, row: Row, items: list[GoldItem], today: date) -> dict[str, Any]:
    by_category: dict[str, list[ItemScores]] = defaultdict(list)
    latencies: list[float] = []
    per_item = []
    for item in items:
        as_of = date.fromisoformat(item.as_of) if item.as_of else None
        started = time.perf_counter()
        result = retriever.retrieve(
            item.question, row.config, as_of=as_of if row.config.temporal_filter else None
        )
        latencies.append((time.perf_counter() - started) * 1000)
        ranked = [hit.chunk for hit in result.hits]
        scores = score_item(item, ranked, today)
        by_category[item.category].append(scores)
        per_item.append({"id": item.id, "route": result.route, **asdict(scores)})
    everything = [s for group in by_category.values() for s in group]
    return {
        "key": row.key,
        "label": row.label,
        "config": asdict(row.config),
        "overall": aggregate(everything),
        "by_category": {cat: aggregate(scores) for cat, scores in sorted(by_category.items())},
        "latency_ms": {
            "p50": round(percentile(latencies, 0.5)),
            "p95": round(percentile(latencies, 0.95)),
        },
        "items": per_item,
    }


def _fixed_subset(items: list[GoldItem], n: int, seed: int) -> list[GoldItem]:
    import random  # noqa: PLC0415

    chosen = sorted(items, key=lambda i: i.id)
    random.Random(seed).shuffle(chosen)
    return chosen[:n]


def answerable(items: list[GoldItem]) -> list[GoldItem]:
    return [i for i in items if i.expected == "answer" and (i.gold_groups or i.gold_docs)]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the retrieval ablation")
    parser.add_argument("--rows", nargs="*", help="row keys (default: all)")
    parser.add_argument("--today", type=date.fromisoformat, default=date(2026, 10, 24))
    args = parser.parse_args(argv)
    settings: Settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    items = answerable(load(settings.evals_dir / "golden" / "golden_v1.jsonl"))
    retriever = build_retriever(settings, today=lambda: args.today)
    rows = [r for r in ROWS + SIDE_ROWS if not args.rows or r.key in args.rows]
    results = []
    for row in rows:
        chosen = (
            items if row.limit is None else _fixed_subset(items, row.limit, settings.random_seed)
        )
        result = run_row(retriever, row, chosen, args.today)
        log.info("ablation_row", row=row.key, **result["overall"], **result["latency_ms"])
        results.append(result)
    out = settings.reports_dir / "ablation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    previous = json.loads(out.read_text(encoding="utf-8")) if out.exists() and args.rows else []
    merged = {r["key"]: r for r in previous} | {r["key"]: r for r in results}
    order = [r.key for r in ROWS + SIDE_ROWS]
    out.write_text(
        json.dumps([merged[k] for k in order if k in merged], indent=1), encoding="utf-8"
    )


if __name__ == "__main__":  # pragma: no cover
    main()
