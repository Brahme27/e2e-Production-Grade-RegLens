"""Evaluation code: golden-set building, retrieval metrics, ablation, generation judge, impact."""

from __future__ import annotations

import json
import random
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml
from qdrant_client import QdrantClient

from reglens.config import PROJECT_ROOT
from reglens.evals import ablation, golden, impact_eval
from reglens.evals.generation import evaluate, format_sources_from_event, judge, subset, summarise
from reglens.evals.golden import Equivalents, GoldItem, handwritten_items, load, save
from reglens.evals.retrieval_metrics import aggregate, percentile, score_item
from reglens.impact.obligations import Obligation
from reglens.impact.policies import PolicySearch, index_policies, load_policies
from reglens.index.store import VectorStore
from reglens.llm.client import LLMClient, LLMResponse
from reglens.retrieve.pipeline import RetrievalConfig, RetrievalResult
from tests.fakes import FakeEmbedder, FakeReranker, make_chunk

TODAY = date(2026, 10, 24)


class Scripted:
    def __init__(self, reply: dict[str, Any] | str) -> None:
        self.reply = reply if isinstance(reply, str) else json.dumps(reply)
        self.calls = 0

    def __call__(
        self, alias: str, messages: list[dict[str, str]], *, json_mode: bool, max_tokens: int
    ) -> LLMResponse:
        self.calls += 1
        return LLMResponse(self.reply, model="fake")


# ---------------------------------------------------------------- golden
def test_equivalents_find_near_duplicates_valid_on_a_date() -> None:
    text = "The bank shall carry out periodic updation of KYC at least once in every two years for high risk customers."
    chunks = [
        make_chunk("a", text, doc_id="cb-kyc", ref="38"),
        make_chunk("b", text + " Updated.", doc_id="nbfc-kyc", ref="36"),
        make_chunk(
            "c",
            text,
            doc_id="old-kyc",
            ref="38",
            valid_from=date(2016, 1, 1),
            valid_to=date(2025, 11, 28),
        ),
        make_chunk(
            "d",
            "Something else entirely about outsourcing contracts and audits.",
            doc_id="out",
            ref="1",
        ),
    ]
    eq = Equivalents(chunks)
    group = eq.of(chunks[0], None)
    assert ["cb-kyc", "38"] in group and ["nbfc-kyc", "36"] in group and ["out", "1"] not in group
    assert ["old-kyc", "38"] not in eq.of(chunks[0], TODAY)  # repealed by then


def test_lookup_temporal_and_comparison_generation_with_fake_llm(tmp_path: Path) -> None:
    words = " ".join(["word"] * 45)
    chunks = [
        make_chunk(
            f"r{i}",
            f"The bank shall do thing {i} {words}.",
            regulator=reg,
            doc_id=f"{reg}-{i}",
            ref=str(i),
            topics=("outsourcing",),
        )
        for i, reg in enumerate(["RBI", "SEBI", "FCA", "PRA"] * 2)
    ] + [
        make_chunk(
            "old",
            f"Old rule wording {words}.",
            doc_id="ss",
            ref="1.1",
            valid_from=date(2021, 3, 1),
            valid_to=date(2024, 11, 1),
            status="superseded",
        )
    ]
    llm = LLMClient(
        Scripted({"question": "What must banks do?", "answer": "Thing.", "answerable": True}),
        tmp_path,
    )
    eq = Equivalents(chunks)
    rng = random.Random(1)
    lookups = golden.lookup_items(chunks, eq, llm, per_regulator=1, rng=rng)
    assert len(lookups) == 4 and {i.category for i in lookups} == {"lookup"}
    temporal = golden.temporal_items(chunks, eq, llm, n=2, rng=rng)
    assert len(temporal) == 1 and temporal[0].as_of == "2022-12-31"
    vectors = {c.chunk_id: np.ones(3) / np.sqrt(3) for c in chunks}
    comparisons = golden.comparison_items(chunks, vectors, eq, llm, n=2, rng=rng)
    assert comparisons and len(comparisons[0].gold_groups) == 2
    refusing = LLMClient(Scripted({"question": "", "answerable": False}), tmp_path / "x")
    assert golden.lookup_items(chunks, eq, refusing, per_regulator=1, rng=rng) == []


def test_handwritten_and_save_load(tmp_path: Path) -> None:
    items = handwritten_items(PROJECT_ROOT / "evals" / "golden" / "handwritten.yaml")
    assert {i.category for i in items} == {"global", "unanswerable", "adversarial"}
    assert all(i.provenance == "hand-written" for i in items)
    save(items[:3], tmp_path / "g.jsonl")
    assert load(tmp_path / "g.jsonl") == items[:3]


# ---------------------------------------------------------------- retrieval metrics
def test_score_item_recall_ndcg_mrr_and_temporal() -> None:
    item = GoldItem("x", "lookup", "q", "answer", gold_groups=[[["doc", "2"]]])
    ranked = [
        make_chunk("1", "a", ref="1"),
        make_chunk("2", "b", ref="2"),
        make_chunk("3", "c", ref="9", valid_to=date(2020, 1, 1), status="superseded"),
    ]
    scores = score_item(item, ranked, TODAY)
    assert scores.recall_at_5 == 1.0 and scores.mrr == 0.5
    assert scores.temporal_precision == pytest.approx(2 / 3) and scores.stale_in_top5
    fixed = make_chunk("f", "long", ref="1")
    fixed = fixed.__class__(**{**fixed.__dict__, "refs": ("1", "2")})
    assert score_item(item, [fixed], TODAY).mrr == 1.0  # a fixed chunk spanning para 2 counts
    global_item = GoldItem("g", "global", "q", "answer", gold_docs=["doc", "other"])
    assert score_item(global_item, ranked, TODAY).recall_at_10 == 0.5
    summary = aggregate([scores, scores])
    assert summary["n"] == 2 and summary["recall@10"] == 1.0
    assert aggregate([]) == {} and percentile([], 0.5) == 0.0
    assert percentile([1, 2, 3, 4], 0.95) == 4


class FakeRetriever:
    def retrieve(
        self,
        question: str,
        config: RetrievalConfig,
        *,
        as_of: date | None = None,
        regulators: tuple[str, ...] = (),
    ) -> RetrievalResult:
        return RetrievalResult(question, [], "lookup", as_of, ())


def test_ablation_row_runner_and_subset() -> None:
    items = [
        GoldItem(f"i{n}", "lookup", "q", "answer", gold_groups=[[["doc", "1"]]]) for n in range(5)
    ]
    result = ablation.run_row(FakeRetriever(), ablation.ROWS[0], items, TODAY)  # type: ignore[arg-type]
    assert result["overall"]["recall@10"] == 0.0 and result["overall"]["n"] == 5
    assert {"p50", "p95"} == set(result["latency_ms"])
    assert len(ablation._fixed_subset(items, 3, 42)) == 3
    assert ablation.answerable([*items, GoldItem("u", "unanswerable", "q", "abstain")]) == items
    assert [r.key for r in ablation.ROWS] == ["A", "B", "C", "D", "E1", "E2", "F", "G"]


# ---------------------------------------------------------------- generation eval
def test_subset_is_stratified_and_deterministic() -> None:
    items = [
        GoldItem(f"{c}-{n}", c, "q", "answer") for c in ("lookup", "global") for n in range(10)
    ]
    chosen = subset(items, 1, {"lookup": 3, "global": 2})
    assert [i.category for i in chosen] == ["lookup"] * 3 + ["global"] * 2
    assert chosen == subset(items, 1, {"lookup": 3, "global": 2})


def test_judge_scores_sentences(tmp_path: Path) -> None:
    verdict = {
        "sentences": [
            {"text": "a", "supported": True, "cited_supports": True},
            {"text": "b", "supported": True, "cited_supports": False},
        ],
        "relevancy": 4,
    }
    result = judge(LLMClient(Scripted(verdict), tmp_path), "q", "[1] src", "answer [1]")
    assert result == {
        "faithfulness": 1.0,
        "citation_precision": 0.5,
        "relevancy": 0.8,
        "sentences": verdict["sentences"],
    }
    assert judge(LLMClient(Scripted({"sentences": []}), tmp_path / "e"), "q", "s", "a") is None


class FakeQA:
    def __init__(self, answers: dict[str, dict[str, Any]]) -> None:
        self.answers = answers

    def ask_stream(self, request: Any) -> Any:
        answer = self.answers[request.question]
        yield {
            "type": "sources",
            "sources": [
                {"number": 1, "regulator": "RBI", "title": "T", "ref": "1"},
                {"number": 2, "regulator": "RBI", "title": "T", "ref": "2"},
            ],
        }
        yield {"type": "final", "answer": answer}


def test_evaluate_and_summarise(tmp_path: Path) -> None:
    cited = {
        "number": 1,
        "text": "Banks must review annually.",
        "valid_from": "2020-01-01",
        "valid_to": None,
    }
    answers = {
        "answer me": {
            "abstained": False,
            "route": "lookup",
            "text": "Banks must review annually [1].",
            "citations": [cited],
            "verification": {"ok": True},
        },
        "unknown": {"abstained": True, "route": "lookup", "text": "not found", "citations": []},
        "attack": {"abstained": True, "route": "refused", "text": "no", "citations": []},
    }
    items = [
        GoldItem("l", "lookup", "answer me", "answer"),
        GoldItem("u", "unanswerable", "unknown", "abstain"),
        GoldItem("a", "adversarial", "attack", "refuse"),
    ]
    verdict = {
        "sentences": [{"text": "x", "supported": True, "cited_supports": True}],
        "relevancy": 5,
    }
    report = evaluate(FakeQA(answers), items, LLMClient(Scripted(verdict), tmp_path), TODAY)  # type: ignore[arg-type]
    s = report["summary"]
    assert (
        s["faithfulness"] == 1.0
        and s["abstention_accuracy"] == 1.0
        and s["refusal_accuracy"] == 1.0
    )
    assert (
        s["temporal_correctness"] == 1.0 and s["false_abstention_rate"] == 0.0 and s["judged"] == 1
    )
    numbered = format_sources_from_event(
        next(iter(FakeQA(answers).ask_stream(type("R", (), {"question": "answer me"})()))),
        answers["answer me"],
    )
    assert (
        numbered.startswith("[1] RBI | T | para 1\nBanks must review") and "not cited" in numbered
    )
    assert summarise([])["n"] == 0


# ---------------------------------------------------------------- impact eval
def test_cohen_kappa() -> None:
    labels = ("a", "b")
    assert impact_eval.cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"], labels) == 1.0
    assert impact_eval.cohen_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"], labels) == 0.0
    assert impact_eval.cohen_kappa([], [], labels) == 0.0


def test_match_and_stage_two(tmp_path: Path) -> None:
    embedder = FakeEmbedder()
    gold_items = [
        {"ref": "8", "text": "The bank must inform the RBI within 10 working days of a vacancy."}
    ]
    predicted = [
        Obligation("p1", "The bank must inform the RBI within 10 working days of a vacancy.", "8"),
        Obligation("p2", "Unrelated", "9"),
    ]
    assert impact_eval._match(gold_items, predicted, embedder) == 1  # type: ignore[arg-type]
    store = VectorStore(QdrantClient(":memory:"))
    index_policies(store, embedder, load_policies(PROJECT_ROOT / "data" / "policies"))  # type: ignore[arg-type]
    search = PolicySearch(store, embedder, FakeReranker())  # type: ignore[arg-type]
    gold = yaml.safe_load((PROJECT_ROOT / "evals" / "impact_gold.yaml").read_text(encoding="utf-8"))
    gold["obligations"] = gold["obligations"][:4]
    llm = LLMClient(
        Scripted({"status": "covered", "rationale": "ok", "policy_refs": [], "confidence": 0.9}),
        tmp_path,
    )
    result = impact_eval.stage_two(gold, search, llm)
    assert result["n"] == 4 and 0 <= result["accuracy"] <= 1
    assert sum(sum(row.values()) for row in result["confusion"].values()) == 4
