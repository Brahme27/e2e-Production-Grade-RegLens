"""Query router: lookup | temporal | comparison | global | out_of_scope.

A multinomial logistic regression over [question embedding, rule signals], trained offline
(``python -m reglens.retrieve.train_router``) on LLM-generated, labelled example queries
that are separate from the golden evaluation set. The weights are exported to JSON and
applied here with numpy: no scikit-learn and no LLM call at serving time (~1 ms).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from reglens.retrieve.query import QuerySignals

Route = Literal["lookup", "temporal", "comparison", "global", "out_of_scope"]
ROUTES: tuple[Route, ...] = ("lookup", "temporal", "comparison", "global", "out_of_scope")
SIGNAL_ORDER = ("has_date", "compare_words", "multi_regulator", "change_words", "theme_words")


def features(embedding: list[float], signals: QuerySignals) -> np.ndarray:
    flags = [1.0 if signals.signals.get(name) else 0.0 for name in SIGNAL_ORDER]
    return np.concatenate(
        [np.asarray(embedding, dtype=np.float32), np.asarray(flags, dtype=np.float32)]
    )


@dataclass(frozen=True)
class RouteDecision:
    route: Route
    confidence: float
    probabilities: dict[str, float]


class Router:
    def __init__(self, weights: np.ndarray, bias: np.ndarray, classes: list[str]) -> None:
        self.weights = weights  # (classes, features)
        self.bias = bias
        self.classes = classes

    @classmethod
    def load(cls, path: Path) -> Router:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(np.asarray(raw["weights"]), np.asarray(raw["bias"]), raw["classes"])

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "classes": self.classes,
            "weights": self.weights.tolist(),
            "bias": self.bias.tolist(),
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

    def classify(self, embedding: list[float], signals: QuerySignals) -> RouteDecision:
        logits = self.weights @ features(embedding, signals) + self.bias
        probs = np.exp(logits - logits.max())
        probs = probs / probs.sum()
        best = int(probs.argmax())
        route: Route = self.classes[best]  # type: ignore[assignment]
        # rules that are never wrong override the model
        if signals.signals.get("multi_regulator") and signals.signals.get("compare_words"):
            route = "comparison"
        elif signals.as_of is not None and route == "lookup":
            route = "temporal"
        return RouteDecision(
            route=route,
            confidence=float(probs[best]),
            probabilities={c: round(float(p), 4) for c, p in zip(self.classes, probs, strict=True)},
        )


def rule_only_route(signals: QuerySignals) -> Route:
    """Fallback when no trained router is available (and the 'rules' baseline row)."""
    flags = signals.signals
    if flags.get("multi_regulator") and flags.get("compare_words"):
        return "comparison"
    if signals.as_of is not None:
        return "temporal"
    if flags.get("theme_words"):
        return "global"
    return "lookup"
