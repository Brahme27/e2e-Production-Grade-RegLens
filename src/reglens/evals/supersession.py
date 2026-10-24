"""Score supersession extraction against the hand-labelled gold edges."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from reglens.temporal.supersession import Edge


def _key(source: str, target: str, kind: str) -> tuple[str, str, str]:
    if target.startswith("ext:"):  # "IMD-PoD-1" vs "IMD-POD-1", "/" vs "-": same circular
        target = "ext:" + re.sub(r"[^A-Z0-9]", "", target[4:].upper())
    return (source, target, kind)


@dataclass(frozen=True)
class Gold:
    labelled_sources: frozenset[str]
    edges: frozenset[tuple[str, str, str]]


def load_gold(path: Path) -> Gold:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    edges = frozenset(_key(e["source"], e["target"], e["type"]) for e in raw["edges"])
    return Gold(frozenset(raw["labelled_sources"]), edges)


def score(predicted: list[Edge], gold: Gold, *, internal_only: bool = False) -> dict[str, Any]:
    """Precision / recall / F1 over edges whose source document was labelled."""
    pred = {
        _key(e.source, e.target, e.type)
        for e in predicted
        if e.source in gold.labelled_sources and not (internal_only and e.target.startswith("ext:"))
    }
    truth = {g for g in gold.edges if not (internal_only and g[1].startswith("ext:"))}
    tp = len(pred & truth)
    precision = tp / len(pred) if pred else 0.0
    recall = tp / len(truth) if truth else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "true_positives": tp,
        "predicted": len(pred),
        "gold": len(truth),
        "false_positives": sorted("|".join(k) for k in pred - truth),
        "missed": sorted("|".join(k) for k in truth - pred),
    }
