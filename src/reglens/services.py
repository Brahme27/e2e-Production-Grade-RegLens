"""Object wiring shared by the API, the evaluation suite and the CLIs.

Everything that is expensive to create (ONNX models, the Qdrant client) is created here
once and passed around, so a test can swap any piece for a fake.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any, cast

from sqlalchemy.engine import Engine

from reglens.cache.semantic import build_cache
from reglens.config import Settings
from reglens.generate.answer import Answerer
from reglens.generate.prompts import PROMPT_VERSION
from reglens.impact.policies import POLICY_COLLECTION, PolicySearch, index_policies, load_policies
from reglens.impact.workflow import ImpactWorkflow, load_entities
from reglens.index.build import make_embedder
from reglens.index.store import VectorStore, connect
from reglens.llm.client import LLMClient, build_client
from reglens.obs.tracing import Tracer, build_tracer
from reglens.parse.model import ParsedDocument, load_documents
from reglens.qa import QAService
from reglens.retrieve.pipeline import RetrievalConfig, Retriever
from reglens.retrieve.rerank import Reranker, RerankerName
from reglens.retrieve.router import Router
from reglens.store.db import init_db, make_engine

DEFAULT_ABSTAIN_THRESHOLD = 0.02  # replaced by the calibrated value once evals have run


def router_path(settings: Settings) -> Path:
    return settings.artifacts_dir / "router.json"


def build_store(settings: Settings) -> VectorStore:
    return VectorStore(connect(settings.qdrant_url, settings.artifacts_dir / "qdrant"))


def build_retriever(
    settings: Settings,
    *,
    store: VectorStore | None = None,
    today: Callable[[], date] = date.today,
) -> Retriever:
    def reranker(name: RerankerName) -> Reranker:
        return Reranker(name, settings.models_cache_dir)

    path = router_path(settings)
    return Retriever(
        store or build_store(settings),
        make_embedder(settings),
        reranker,
        router=Router.load(path) if path.exists() else None,
        today=today,
    )


def abstain_threshold(settings: Settings) -> float:
    path = settings.reports_dir / "abstention.json"
    if path.exists():
        return float(json.loads(path.read_text(encoding="utf-8"))["threshold"])
    return DEFAULT_ABSTAIN_THRESHOLD


def doc_summaries(settings: Settings) -> dict[str, str]:
    path = settings.data_dir / "processed" / "doc_summaries.json"
    if not path.exists():
        return {}
    summaries: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
    return summaries


def build_answerer(settings: Settings, llm: LLMClient | None = None) -> Answerer:
    return Answerer(
        llm or build_client(settings),
        abstain_threshold=abstain_threshold(settings),
        summaries=doc_summaries(settings),
    )


# hybrid + MiniLM reranker + router + as-of/regulator filters, via alias "reglens" (ablation row F;
# row G's document diversification did not improve retrieval, so it is off)
SERVING_CONFIG = RetrievalConfig(diversify_global=False)


class Services:
    """Lazily built application services (the API starts fast; tests inject fakes)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cache: dict[str, Any] = {}

    def _get(self, name: str, factory: Callable[[], Any]) -> Any:
        if name not in self._cache:
            self._cache[name] = factory()
        return self._cache[name]

    def override(self, name: str, value: Any) -> None:
        self._cache[name] = value

    @property
    def engine(self) -> Engine:
        def make() -> Engine:
            engine = make_engine(self.settings.sqlalchemy_url)
            init_db(engine)
            return engine

        return cast(Engine, self._get("engine", make))

    @property
    def llm(self) -> LLMClient:
        return cast(LLMClient, self._get("llm", lambda: build_client(self.settings)))

    @property
    def documents(self) -> dict[str, ParsedDocument]:
        folder = self.settings.data_dir / "processed" / "documents"
        return cast(
            dict[str, ParsedDocument],
            self._get(
                "documents",
                lambda: {d.key: d for d in load_documents(folder)} if folder.exists() else {},
            ),
        )

    @property
    def retriever(self) -> Retriever:
        return cast(Retriever, self._get("retriever", lambda: build_retriever(self.settings)))

    @property
    def tracer(self) -> Tracer:
        return cast(Tracer, self._get("tracer", lambda: build_tracer(self.settings)))

    @property
    def qa(self) -> QAService:
        def make() -> QAService:
            version = f"{self.settings.serving_variant}|{PROMPT_VERSION}"
            return QAService(
                self.retriever,
                build_answerer(self.settings, self.llm),
                self.tracer,
                build_cache(self.settings.redis_url, version),
                SERVING_CONFIG,
                guard_llm=self.llm if self.settings.groq_api_key else None,
            )

        return cast(QAService, self._get("qa", make))

    @property
    def impact(self) -> ImpactWorkflow:
        def make() -> ImpactWorkflow:
            store = self.retriever.store
            embedder = self.retriever.embedder
            if not store.client.collection_exists(POLICY_COLLECTION):
                index_policies(store, embedder, load_policies(self.settings.data_dir / "policies"))
            search = PolicySearch(store, embedder, self.retriever.reranker("minilm"))
            return ImpactWorkflow(
                self.documents,
                load_entities(self.settings.configs_dir / "entities.yaml"),
                search,
                self.llm,
                self.settings.artifacts_dir / "tickets",
            )

        return cast(ImpactWorkflow, self._get("impact", make))
