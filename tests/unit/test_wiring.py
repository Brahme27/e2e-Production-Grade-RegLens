"""Model wrappers, index build, services wiring, router training and LLM streaming (fakes)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from qdrant_client import QdrantClient

from reglens.config import PROJECT_ROOT, Settings
from reglens.index import build as build_mod
from reglens.index.embed import Embedder
from reglens.index.store import Hit, VectorStore
from reglens.llm.client import LiteLLMBackend, LLMClient, LLMResponse, LLMUnavailableError
from reglens.parse.model import Paragraph, ParsedDocument, save_documents
from reglens.retrieve import train_router
from reglens.retrieve.rerank import Reranker
from reglens.services import Services, abstain_threshold, doc_summaries
from tests.fakes import FakeEmbedder, make_chunk


# ---------------------------------------------------------------- model wrappers
class FakeDenseModel:
    def embed(self, texts: list[str], batch_size: int = 16) -> list[np.ndarray]:
        return [np.full(4, len(t), dtype=np.float32) for t in texts]


class FakeSparseModel:
    def embed(self, texts: list[str], batch_size: int = 16) -> list[Any]:
        return [SimpleNamespace(indices=[1, 2], values=[0.5, float(len(t))]) for t in texts]

    def query_embed(self, text: str) -> Any:
        return iter([SimpleNamespace(indices=np.array([7]), values=np.array([1.0]))])


def test_embedder_uses_cache_and_query_prefix(tmp_path: Path) -> None:
    embedder = Embedder("BAAI/bge-small-en-v1.5", "Qdrant/bm25", tmp_path / "e.sqlite")
    embedder._dense, embedder._sparse = FakeDenseModel(), FakeSparseModel()
    assert embedder.dense(["ab"]) == [[2.0, 2.0, 2.0, 2.0]]
    assert embedder.dense_dim == 4
    assert embedder.dense_query("q")[0] == len(
        "Represent this sentence for searching relevant passages: q"
    )
    assert embedder.sparse(["abc"])[0].values == [0.5, 3.0]
    assert embedder.sparse_query("q").indices == [7]
    again = Embedder("BAAI/bge-small-en-v1.5", "Qdrant/bm25", tmp_path / "e.sqlite")
    again._dense = None  # would load a real model if the cache missed
    assert again.dense(["ab"]) == [[2.0, 2.0, 2.0, 2.0]]


def test_reranker_orders_by_model_scores() -> None:
    reranker = Reranker("minilm")
    reranker._model = SimpleNamespace(rerank=lambda q, docs, batch_size: [len(d) for d in docs])
    hits = [Hit(make_chunk("a", "short"), 0.0), Hit(make_chunk("b", "a much longer passage"), 0.0)]
    ranked = reranker.rerank("q", hits, 1)
    assert ranked[0].chunk.text == "a much longer passage" and ranked[0].score == len(
        Reranker.passage(hits[1])
    )
    assert Reranker("none").rerank("q", hits, 1) == hits[:1]


# ---------------------------------------------------------------- index build
def _setup_processed(settings: Settings) -> None:
    doc = ParsedDocument(
        "kyc",
        "current",
        "RBI",
        "directions",
        "KYC Directions",
        "u",
        ["kyc"],
        ["commercial_banks"],
        doc_number="RBI/1",
        issue_date=date(2025, 1, 1),
        effective_from=date(2025, 1, 1),
        paragraphs=[
            Paragraph("1", "1. Banks shall verify customers."),
            Paragraph("2", "2. Banks shall update KYC."),
        ],
    )
    processed = settings.data_dir / "processed"
    save_documents([doc], processed / "documents")
    (processed / "validity.json").write_text(
        json.dumps(
            {
                "kyc@current": {
                    "valid_from": "2025-01-01",
                    "valid_to": None,
                    "status": "current",
                    "superseded_by": None,
                }
            }
        )
    )
    summaries_llm_dir = settings.llm_cache_dir
    summaries_llm_dir.mkdir(parents=True, exist_ok=True)


def test_build_all_variants_and_alias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        data_dir=tmp_path / "data",
        artifacts_dir=tmp_path / "art",
        llm_cache_dir=tmp_path / "llm",
        groq_api_key=None,
    )
    _setup_processed(settings)
    client = QdrantClient(":memory:")
    monkeypatch.setattr(build_mod, "make_embedder", lambda s: FakeEmbedder())
    monkeypatch.setattr(build_mod, "connect", lambda url, path: client)
    monkeypatch.setattr(client, "close", lambda: None)
    counts = build_mod.build(settings, list(build_mod.VARIANTS.values()), use_llm=False)
    assert counts == {"fixed": 1, "para": 2, "para_ctx": 2, "para_ctx_sum": 2}
    assert {a.alias_name for a in client.get_aliases().aliases} == {"reglens"}
    chunks = build_mod.read_chunks(settings.data_dir / "processed" / "chunks" / "para_ctx.jsonl")
    assert chunks[0].context.startswith("RBI directions: KYC Directions (RBI/1)")
    assert (settings.data_dir / "processed" / "doc_summaries.json").exists()


# ---------------------------------------------------------------- services
def test_services_defaults_and_lazy_objects(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path / "data", artifacts_dir=tmp_path / "art", groq_api_key=None
    )
    assert abstain_threshold(settings) == pytest.approx(0.02)
    settings.reports_dir.mkdir(parents=True)
    (settings.reports_dir / "abstention.json").write_text('{"threshold": -3.5}')
    assert abstain_threshold(settings) == -3.5
    assert doc_summaries(settings) == {}
    services = Services(settings)
    assert services.documents == {}
    assert services.engine is services.engine  # built once
    assert services.llm.backend is None  # no key: cache-only
    assert services.tracer.exporter is None


# ---------------------------------------------------------------- router training
def test_train_router_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(artifacts_dir=tmp_path / "art", data_dir=tmp_path / "data")
    monkeypatch.setattr(train_router, "get_settings", lambda: settings)
    monkeypatch.setattr(train_router, "make_embedder", lambda s: FakeEmbedder())
    train_router.main([])
    report = json.loads((settings.reports_dir / "router_eval.json").read_text())
    assert report["train_examples"] > 100 and 0 <= report["golden_accuracy"] <= 1
    assert set(report["classes"]) == {"lookup", "temporal", "comparison", "global"}
    assert (settings.artifacts_dir / "router.json").exists()


def test_generate_router_examples(tmp_path: Path) -> None:
    class Gen:
        def __call__(
            self, alias: str, messages: list[dict[str, str]], *, json_mode: bool, max_tokens: int
        ) -> LLMResponse:
            return LLMResponse('{"questions": ["q1", "q2"]}', model="fake")

    rows = train_router.generate_examples(
        LLMClient(Gen(), tmp_path / "c"), tmp_path / "train.jsonl"
    )
    assert len(rows) == 2 * len(train_router.DESCRIPTIONS)
    assert (tmp_path / "train.jsonl").read_text().count("\n") == len(rows)


# ---------------------------------------------------------------- LLM streaming
class StreamingBackend:
    def __init__(self) -> None:
        self.streamed = 0

    def __call__(
        self, alias: str, messages: list[dict[str, str]], *, json_mode: bool, max_tokens: int
    ) -> LLMResponse:
        return LLMResponse("full", model="m")

    def stream(self, alias: str, messages: list[dict[str, str]], *, max_tokens: int) -> Any:
        self.streamed += 1
        yield from ["Hel", "lo ", "world"]


def test_client_streams_then_replays_from_cache(tmp_path: Path) -> None:
    backend = StreamingBackend()
    client = LLMClient(backend, tmp_path, usage_log=tmp_path / "u.jsonl")
    msgs = [{"role": "user", "content": "q"}]
    assert "".join(client.stream(msgs)) == "Hello world"
    assert "".join(client.stream(msgs)) == "Hello world"  # replayed in pieces from the cache
    assert backend.streamed == 1
    assert client.complete(msgs, alias="reasoning-large").text == "Hello world"


def test_backend_stream_parses_deltas(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = LiteLLMBackend(PROJECT_ROOT / "configs" / "litellm.yaml", "k")
    chunks = [
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=t))])
        for t in ("a", None, "b")
    ]
    monkeypatch.setattr(
        backend._router, "completion", lambda **kw: iter([*chunks, SimpleNamespace(choices=[])])
    )
    assert "".join(backend.stream("fast-small", [], max_tokens=5)) == "ab"

    def boom(**kw: Any) -> Any:
        raise RuntimeError("down")

    monkeypatch.setattr(backend._router, "completion", boom)
    with pytest.raises(LLMUnavailableError):
        list(backend.stream("fast-small", [], max_tokens=5))


def test_vector_store_local_path_connect(tmp_path: Path) -> None:
    from reglens.index.store import connect  # noqa: PLC0415

    client = connect(None, tmp_path / "q")
    store = VectorStore(client)
    store.recreate("c", 4)
    assert store.count("c") == 0
    client.close()
