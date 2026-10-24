"""Chunking, context, embedding cache, Qdrant store, query analysis, router, pipeline."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pytest
from qdrant_client import QdrantClient

from reglens.index.chunking import Chunk, chunk_corpus, fixed_chunks, paragraph_chunks, split_long
from reglens.index.context import add_context, document_summaries, structural_header
from reglens.index.embed import EmbeddingCache, _blob_to_sparse, _cached, _sparse_to_blob
from reglens.index.store import SearchFilter, VectorStore
from reglens.llm.client import LLMClient, LLMResponse
from reglens.parse.model import Paragraph, ParsedDocument
from reglens.retrieve.pipeline import RetrievalConfig, Retriever
from reglens.retrieve.query import analyse
from reglens.retrieve.router import ROUTES, Router, features, rule_only_route
from reglens.temporal.validity import Validity
from tests.fakes import DIM, FakeEmbedder, FakeReranker, make_chunk


# ---------------------------------------------------------------- chunking
def _doc(paragraphs: list[Paragraph], version: str = "current") -> ParsedDocument:
    return ParsedDocument(
        doc_id="kyc",
        version=version,
        regulator="RBI",
        doc_type="directions",
        title="KYC Directions",
        url="u",
        topics=["kyc"],
        applies_to=["commercial_banks"],
        doc_number="RBI/1",
        issue_date=date(2016, 2, 25),
        paragraphs=paragraphs,
    )


def _validity(key: str, start: date, end: date | None = None) -> Validity:
    doc_id, version = key.split("@")
    return Validity(key, doc_id, version, start, end, "current" if end is None else "superseded")


def test_split_long_respects_line_boundaries() -> None:
    text = "\n".join(f"({i}) item number {i} " + "word " * 40 for i in range(10))
    pieces = split_long(text, max_words=100)
    assert len(pieces) > 1
    assert all(len(p.split()) <= 100 for p in pieces)
    assert "\n".join(pieces).split() == text.split()
    giant = "w " * 250
    assert [len(p.split()) for p in split_long(giant, 100)] == [100, 100, 50]


def test_paragraph_chunks_carry_refs_parts_and_paragraph_dates() -> None:
    long_text = "\n".join(f"({i}) " + "obligation " * 60 for i in range(8))
    doc = _doc(
        [
            Paragraph("3", long_text, ("Chapter II",), effective_from=date(2020, 1, 9)),
            Paragraph("4", "4. Short rule here."),
        ]
    )
    validity = _validity("kyc@current", date(2025, 8, 14))
    chunks = paragraph_chunks(doc, validity, earliest=True)
    parts = [c for c in chunks if c.ref == "3"]
    assert len(parts) > 1 and {c.parts for c in parts} == {len(parts)}
    assert parts[0].valid_from == date(2020, 1, 9)  # its own amendment date
    assert chunks[-1].valid_from == date(2016, 2, 25)  # unamended: original issue date
    assert chunks[0].citation == "[RBI/1 §3]"
    later = paragraph_chunks(doc, validity, earliest=False)
    assert later[-1].valid_from == date(2025, 8, 14)
    assert len({c.chunk_id for c in chunks}) == len(chunks)


def test_fixed_chunks_span_paragraphs() -> None:
    doc = _doc([Paragraph(str(i), "word " * 150) for i in range(1, 6)])
    chunks = fixed_chunks(doc, _validity("kyc@current", date(2025, 1, 1)), earliest=True)
    assert len(chunks) == 2  # 750 words / 380
    assert chunks[0].refs == ("1", "2", "3")
    assert chunks[0].valid_from == date(2025, 1, 1)


def test_chunk_corpus_marks_only_the_oldest_version_as_earliest() -> None:
    old = _doc([Paragraph("1", "Old text of the rule.")], version="v2020")
    new = _doc([Paragraph("1", "New text of the rule.")], version="current")
    validity = {
        "kyc@v2020": _validity("kyc@v2020", date(2020, 1, 1), date(2024, 1, 1)),
        "kyc@current": _validity("kyc@current", date(2024, 1, 1)),
    }
    chunks = chunk_corpus([old, new], validity, "paragraph")
    by_version = {c.version: c for c in chunks}
    assert by_version["v2020"].valid_from == date(2016, 2, 25)  # oldest: paragraph/issue date
    assert by_version["current"].valid_from == date(2024, 1, 1)


def test_payload_round_trip() -> None:
    chunk = make_chunk("a", "text", valid_to=date(2025, 1, 1))
    payload = chunk.payload()
    assert payload["valid_to_day"] == date(2025, 1, 1).toordinal()
    assert make_chunk("b", "x").payload()["valid_to_day"] == date(9999, 12, 31).toordinal()
    assert Chunk.from_payload(payload) == chunk


# ---------------------------------------------------------------- context
class ScriptedLLM:
    def __call__(
        self, alias: str, messages: list[dict[str, str]], *, json_mode: bool, max_tokens: int
    ) -> LLMResponse:
        return LLMResponse('{"summary": "Covers customer due diligence for banks."}', model="fake")


def test_structural_header_and_summaries(tmp_path: Path) -> None:
    chunk = make_chunk("a", "The bank shall review it annually.", ref="38")
    assert (
        structural_header(chunk)
        == "RBI directions: Title of doc (NUM/doc). Section: Chapter I. Paragraph 38."
    )
    doc = _doc([Paragraph("1", "1. Customer due diligence rules.", ("Chapter I",))])
    doc.doc_id = "doc"
    summaries = document_summaries([doc], LLMClient(ScriptedLLM(), tmp_path))
    assert summaries == {"doc": "Covers customer due diligence for banks."}
    with_summary = add_context([chunk], "structural+summary", summaries)[0]
    assert with_summary.embed_text.startswith("RBI directions")
    assert "Document context: Covers customer" in with_summary.context
    assert add_context([chunk], "none") == [chunk]
    assert "Document context" not in add_context([chunk], "structural", summaries)[0].context


# ---------------------------------------------------------------- embedding cache
def test_embedding_cache_computes_only_missing(tmp_path: Path) -> None:
    cache = EmbeddingCache(tmp_path / "e.sqlite")
    computed: list[str] = []

    def compute(texts: list[str]) -> list[bytes]:
        computed.extend(texts)
        return [np.float32(len(t)).tobytes() for t in texts]

    first = _cached(["a", "bb"], "m", cache, compute)
    second = _cached(["bb", "ccc"], "m", cache, compute)
    assert computed == ["a", "bb", "ccc"]
    assert first[1] == second[0]
    blob = _sparse_to_blob(type("V", (), {"indices": [3, 7], "values": [0.5, 1.5]})())
    assert _blob_to_sparse(blob).indices == [3, 7]


# ---------------------------------------------------------------- store + pipeline
@pytest.fixture
def store() -> VectorStore:
    chunks = [
        make_chunk(
            "kyc-new",
            "Banks shall carry out periodic updation of KYC for high risk customers every two years.",
            doc_id="kyc-2025",
            ref="38",
        ),
        make_chunk(
            "kyc-old",
            "Banks shall carry out periodic updation of KYC for high risk customers every two years.",
            doc_id="kyc-2016",
            ref="38",
            valid_from=date(2016, 1, 1),
            valid_to=date(2025, 11, 28),
            status="superseded",
        ),
        make_chunk(
            "fca-out",
            "A firm must notify the FCA before outsourcing a critical or important operational function.",
            regulator="FCA",
            doc_id="sysc-8",
            ref="SYSC 8.1.12R",
            topics=("outsourcing",),
        ),
        make_chunk(
            "rbi-out",
            "A bank shall not outsource core management functions including internal audit.",
            doc_id="rbi-out",
            ref="15",
            topics=("outsourcing",),
        ),
        make_chunk(
            "pra-out",
            "A firm must not undertake outsourcing of important operational functions that impairs internal control.",
            regulator="PRA",
            doc_id="pra-out",
            ref="2.1",
            topics=("outsourcing",),
        ),
    ]
    embedder = FakeEmbedder()
    vs = VectorStore(QdrantClient(":memory:"))
    vs.recreate("test", DIM)
    texts = [c.text for c in chunks]
    vs.upsert("test", chunks, embedder.dense(texts), embedder.sparse(texts))
    vs.point_alias("serving", "test")
    vs.point_alias("serving", "test")  # re-pointing an existing alias works
    return vs


def test_store_searches_and_as_of_filter(store: VectorStore) -> None:
    embedder = FakeEmbedder()
    q = "periodic updation of KYC for high risk customers"
    dense = store.dense_search("serving", embedder.dense_query(q), 5)
    assert dense[0].chunk.doc_id.startswith("kyc")
    sparse = store.sparse_search("test", embedder.sparse_query(q), 5)
    assert sparse[0].chunk.ref == "38"
    hybrid = store.hybrid_search("test", embedder.dense_query(q), embedder.sparse_query(q), 5)
    assert {h.chunk.doc_id for h in hybrid[:2]} == {"kyc-2025", "kyc-2016"}
    then = SearchFilter(as_of=date(2024, 1, 1))
    assert {
        h.chunk.doc_id for h in store.dense_search("test", embedder.dense_query(q), 5, then)
    } >= {"kyc-2016"}
    now = SearchFilter(as_of=date(2026, 1, 1), regulators=("RBI",))
    found = store.dense_search("test", embedder.dense_query(q), 5, now)
    assert "kyc-2016" not in {h.chunk.doc_id for h in found}
    assert {h.chunk.regulator for h in found} == {"RBI"}
    assert store.count("test") == 5
    assert store.fetch("test", [found[0].chunk.chunk_id])[0].ref == found[0].chunk.ref
    assert SearchFilter().to_qdrant() is None


def _retriever(store: VectorStore, router: Router | None = None) -> Retriever:
    return Retriever(
        store,
        FakeEmbedder(),
        lambda name: FakeReranker(),
        router=router,
        today=lambda: date(2026, 10, 24),
    )  # type: ignore[arg-type,return-value]


def test_pipeline_temporal_filter_and_routes(store: VectorStore) -> None:
    retriever = _retriever(store)
    config = RetrievalConfig(collection="test", top_k=3)
    now = retriever.retrieve(
        "How often must banks do periodic updation of KYC for high risk customers?", config
    )
    assert now.route == "lookup" and now.as_of == date(2026, 10, 24)
    assert "kyc-2016" not in {h.chunk.doc_id for h in now.hits}
    past = retriever.retrieve(
        "As of 1 March 2024, how often was periodic updation of KYC for high risk customers required?",
        config,
    )
    assert past.route == "temporal" and past.as_of == date(2024, 3, 1)
    assert "kyc-2016" in {h.chunk.doc_id for h in past.hits}
    naive = retriever.retrieve(
        "periodic updation of KYC",
        RetrievalConfig(collection="test", temporal_filter=False, route=False, mode="dense"),
    )
    assert naive.as_of is None and naive.route == "lookup"
    assert {"route", "search", "rerank", "total"} <= set(now.timings_ms)


def test_pipeline_comparison_keeps_both_regulators(store: VectorStore) -> None:
    retriever = _retriever(store)
    result = retriever.retrieve(
        "Compare how the FCA and the PRA treat outsourcing of important operational functions",
        RetrievalConfig(collection="test", top_k=2, mode="sparse"),
    )
    assert result.route == "comparison"
    assert {"FCA", "PRA"} <= {h.chunk.regulator for h in result.hits}
    assert len(result.sub_queries) == 2
    overview = retriever.retrieve(
        "Give an overview of the main themes in outsourcing rules",
        RetrievalConfig(collection="test", top_k=4),
    )
    assert overview.route == "global"
    doc_counts: dict[str, int] = {}
    for hit in overview.hits:
        doc_counts[hit.chunk.doc_id] = doc_counts.get(hit.chunk.doc_id, 0) + 1
    assert max(doc_counts.values()) <= 2


# ---------------------------------------------------------------- query analysis + router
@pytest.mark.parametrize(
    ("text", "as_of"),
    [
        ("What applied as of 1 March 2024?", date(2024, 3, 1)),
        ("What was required as at 30/06/2025?", date(2025, 6, 30)),
        ("What was the rule in March 2023?", date(2023, 3, 15)),
        ("What did the PRA expect in 2022?", date(2022, 7, 1)),
        ("on 2025-11-28 what changed", date(2025, 11, 28)),
        ("What must banks do?", None),
    ],
)
def test_as_of_extraction(text: str, as_of: date | None) -> None:
    assert analyse(text).as_of == as_of


def test_signals_regulators_and_rules() -> None:
    s = analyse("How do RBI and FCA rules on outsourcing differ for NBFCs?")
    assert s.regulators == ("RBI", "FCA")
    assert s.applies_to == ("nbfcs",)
    assert s.signals["compare_words"] and s.signals["multi_regulator"]
    assert rule_only_route(s) == "comparison"
    assert rule_only_route(analyse("Summarise the main themes of the Consumer Duty")) == "global"
    assert rule_only_route(analyse("What did SEBI require in 2023?")) == "temporal"


def test_router_classify_and_overrides(tmp_path: Path) -> None:
    dim = DIM + 5
    weights = np.zeros((len(ROUTES), dim))
    weights[ROUTES.index("out_of_scope"), :] = 0.0
    bias = np.array([1.0 if r == "lookup" else 0.0 for r in ROUTES])
    router = Router(weights, bias, list(ROUTES))
    router.save(tmp_path / "r.json")
    loaded = Router.load(tmp_path / "r.json")
    emb = FakeEmbedder().dense_query("x")
    assert loaded.classify(emb, analyse("What must banks do?")).route == "lookup"
    assert loaded.classify(emb, analyse("What applied as of 1 March 2024?")).route == "temporal"
    assert loaded.classify(emb, analyse("Compare RBI and FCA rules")).route == "comparison"
    assert len(features(emb, analyse("x"))) == dim
