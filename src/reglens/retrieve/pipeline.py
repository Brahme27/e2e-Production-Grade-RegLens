"""The retrieval pipeline: one configurable object, so every ablation row is a config.

question ─▶ signals (date, regulators) ─▶ route ─▶ [sub-queries] ─▶ first-stage search
         ─▶ (as-of + regulator filters) ─▶ rerank ─▶ top-k chunks
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from reglens.index.embed import Embedder
from reglens.index.store import Hit, SearchFilter, VectorStore
from reglens.retrieve.query import QuerySignals, analyse
from reglens.retrieve.rerank import Reranker, RerankerName
from reglens.retrieve.router import Route, Router, rule_only_route

SearchMode = Literal["dense", "sparse", "hybrid"]


@dataclass(frozen=True)
class RetrievalConfig:
    collection: str = "reglens"
    mode: SearchMode = "hybrid"
    # bge-reranker-v2-m3 takes ~36 s per question on this CPU; MiniLM ~1.5 s (see ADR 0004)
    reranker: RerankerName = "minilm"
    candidates: int = 30  # first-stage depth (what the reranker sees)
    top_k: int = 8  # what the generator sees
    temporal_filter: bool = True  # filter on "valid on the as-of date"
    regulator_filter: bool = True  # a question naming one regulator searches only it
    route: bool = True  # router + comparison decomposition
    diversify_global: bool = True  # broad questions: best passages from several documents


@dataclass
class RetrievalResult:
    question: str
    hits: list[Hit]
    route: Route
    as_of: date | None
    regulators: tuple[str, ...]
    sub_queries: list[str] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)


class Retriever:
    def __init__(
        self,
        store: VectorStore,
        embedder: Embedder,
        reranker_factory: Callable[[RerankerName], Reranker],
        router: Router | None = None,
        today: Callable[[], date] = date.today,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.router = router
        self._reranker_factory = reranker_factory
        self._rerankers: dict[str, Reranker] = {}
        self._today = today

    def reranker(self, name: RerankerName) -> Reranker:
        if name not in self._rerankers:
            self._rerankers[name] = self._reranker_factory(name)
        return self._rerankers[name]

    def _route(self, question: str, signals: QuerySignals, config: RetrievalConfig) -> Route:
        if not config.route:
            return "lookup"
        if self.router is None:
            return rule_only_route(signals)
        return self.router.classify(self.embedder.dense_query(question), signals).route

    def _first_stage(
        self, question: str, config: RetrievalConfig, flt: SearchFilter, k: int
    ) -> list[Hit]:
        if config.mode == "dense":
            return self.store.dense_search(
                config.collection, self.embedder.dense_query(question), k, flt
            )
        if config.mode == "sparse":
            return self.store.sparse_search(
                config.collection, self.embedder.sparse_query(question), k, flt
            )
        return self.store.hybrid_search(
            config.collection,
            self.embedder.dense_query(question),
            self.embedder.sparse_query(question),
            k,
            flt,
            prefetch=k,
        )

    def retrieve(
        self,
        question: str,
        config: RetrievalConfig,
        *,
        as_of: date | None = None,
        regulators: tuple[str, ...] = (),
    ) -> RetrievalResult:
        timings: dict[str, float] = {}
        started = time.perf_counter()
        signals = analyse(question)
        route = self._route(question, signals, config)
        effective_as_of = (
            (as_of or signals.as_of or self._today()) if config.temporal_filter else None
        )
        mentioned = regulators or (signals.regulators if config.regulator_filter else ())
        timings["route"] = (time.perf_counter() - started) * 1000

        stage = time.perf_counter()
        sub_queries: list[str] = []
        if route == "comparison" and len(mentioned) >= 2:  # noqa: PLR2004 - one search per side
            per_side = max(config.candidates // len(mentioned), 5)
            candidates: list[Hit] = []
            for regulator in mentioned:
                sub_queries.append(f"{question} [{regulator}]")
                flt = SearchFilter(as_of=effective_as_of, regulators=(regulator,))
                candidates.extend(self._first_stage(question, config, flt, per_side))
        else:
            single = mentioned if len(mentioned) == 1 else ()
            flt = SearchFilter(as_of=effective_as_of, regulators=single)
            candidates = self._first_stage(question, config, flt, config.candidates)
        timings["search"] = (time.perf_counter() - stage) * 1000

        stage = time.perf_counter()
        if route == "global" and config.diversify_global:
            hits = _diversify(
                self.reranker(config.reranker).rerank(question, candidates, len(candidates)), config
            )
        else:
            hits = self.reranker(config.reranker).rerank(question, candidates, config.top_k)
        if route == "comparison" and len(mentioned) >= 2:  # noqa: PLR2004 - keep both sides
            hits = _balance(hits, candidates, mentioned, config)
        timings["rerank"] = (time.perf_counter() - stage) * 1000
        timings["total"] = (time.perf_counter() - started) * 1000
        return RetrievalResult(
            question, hits, route, effective_as_of, mentioned, sub_queries, timings
        )


GLOBAL_PER_DOC = 2


def _diversify(ranked: list[Hit], config: RetrievalConfig) -> list[Hit]:
    """A thematic answer needs breadth: at most two passages per document."""
    per_doc: dict[str, int] = {}
    chosen = []
    for hit in ranked:
        if per_doc.get(hit.chunk.doc_id, 0) < GLOBAL_PER_DOC:
            chosen.append(hit)
            per_doc[hit.chunk.doc_id] = per_doc.get(hit.chunk.doc_id, 0) + 1
        if len(chosen) == config.top_k:
            break
    return chosen


def _balance(
    hits: list[Hit], candidates: list[Hit], regulators: tuple[str, ...], config: RetrievalConfig
) -> list[Hit]:
    """A comparison needs evidence from every side: guarantee at least two hits each."""
    chosen = list(hits)
    for regulator in regulators:
        have = [h for h in chosen if h.chunk.regulator == regulator]
        needed = 2 - len(have)
        extra = [h for h in candidates if h.chunk.regulator == regulator and h not in chosen]
        chosen.extend(extra[: max(needed, 0)])
    return chosen[: config.top_k + len(regulators)]
