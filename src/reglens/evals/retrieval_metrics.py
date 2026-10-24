"""Retrieval metrics against the golden set (no LLM needed, so every ablation row is free).

- recall@k: share of gold groups with at least one acceptable chunk in the top k
- nDCG@10: rewards finding gold paragraphs near the top
- MRR: 1 / rank of the first acceptable chunk
- doc recall@k (global questions): share of expected documents present in the top k
- temporal precision: share of returned chunks that were actually in force on the
  question's date (a superseded rule presented as current is the worst failure)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from reglens.evals.golden import GoldItem
from reglens.index.chunking import Chunk


@dataclass(frozen=True)
class ItemScores:
    recall_at_5: float
    recall_at_10: float
    ndcg_at_10: float
    mrr: float
    temporal_precision: float
    stale_in_top5: bool


def _keys(chunk: Chunk) -> set[tuple[str, str]]:
    """Every (document, paragraph) a chunk contains: fixed-size chunks span several."""
    return {(chunk.doc_id, ref) for ref in (chunk.refs or (chunk.ref,))}


def _first_hit_ranks(item: GoldItem, ranked: list[Chunk]) -> list[int | None]:
    """For each gold group: 1-based rank of its first acceptable chunk (None if absent)."""
    ranks: list[int | None] = []
    for group in item.gold_groups:
        acceptable = {(pair[0], pair[1]) for pair in group}
        rank = next((i + 1 for i, c in enumerate(ranked) if _keys(c) & acceptable), None)
        ranks.append(rank)
    return ranks


def _valid_on(chunk: Chunk, day: date) -> bool:
    return (chunk.valid_from is None or chunk.valid_from <= day) and (
        chunk.valid_to is None or day < chunk.valid_to
    )


def score_item(item: GoldItem, ranked: list[Chunk], today: date) -> ItemScores:
    day = date.fromisoformat(item.as_of) if item.as_of else today
    valid = [_valid_on(c, day) for c in ranked[:10]]
    temporal_precision = sum(valid) / len(valid) if valid else 1.0
    stale = not all(valid[:5])
    if item.gold_docs:  # global question: document-level recall
        docs5 = {c.doc_id for c in ranked[:5]}
        docs10 = {c.doc_id for c in ranked[:10]}
        r5 = len(docs5 & set(item.gold_docs)) / len(item.gold_docs)
        r10 = len(docs10 & set(item.gold_docs)) / len(item.gold_docs)
        first = next((i + 1 for i, c in enumerate(ranked) if c.doc_id in item.gold_docs), None)
        return ItemScores(r5, r10, r10, 1 / first if first else 0.0, temporal_precision, stale)
    ranks = _first_hit_ranks(item, ranked)
    groups = len(ranks) or 1
    r5 = sum(1 for r in ranks if r is not None and r <= 5) / groups  # noqa: PLR2004
    r10 = sum(1 for r in ranks if r is not None and r <= 10) / groups  # noqa: PLR2004
    dcg = sum(1 / math.log2(r + 1) for r in ranks if r is not None and r <= 10)  # noqa: PLR2004
    ideal = sum(1 / math.log2(i + 2) for i in range(min(groups, 10)))
    found = [r for r in ranks if r is not None]
    mrr = 1 / min(found) if found else 0.0
    return ItemScores(r5, r10, dcg / ideal if ideal else 0.0, mrr, temporal_precision, stale)


def aggregate(scores: list[ItemScores]) -> dict[str, float]:
    if not scores:
        return {}
    n = len(scores)
    return {
        "recall@5": round(sum(s.recall_at_5 for s in scores) / n, 3),
        "recall@10": round(sum(s.recall_at_10 for s in scores) / n, 3),
        "ndcg@10": round(sum(s.ndcg_at_10 for s in scores) / n, 3),
        "mrr": round(sum(s.mrr for s in scores) / n, 3),
        "temporal_precision": round(sum(s.temporal_precision for s in scores) / n, 3),
        "stale_in_top5_rate": round(sum(s.stale_in_top5 for s in scores) / n, 3),
        "n": n,
    }


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))
    return ordered[index]
