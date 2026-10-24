"""Answer generation: prompts, abstention, citation markers, verification, streaming."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from reglens.generate.answer import (
    ABSTAIN_TEXT,
    UNAVAILABLE_TEXT,
    Answer,
    Answerer,
    answer_text_without_markers,
    is_not_found,
    strip_invalid_markers,
)
from reglens.generate.prompts import answer_messages, format_sources
from reglens.generate.verify import lexical_support, verify
from reglens.index.store import Hit
from reglens.llm.client import LLMClient, LLMResponse, LLMUnavailableError
from reglens.retrieve.pipeline import RetrievalResult
from tests.fakes import make_chunk

HITS = [
    Hit(
        make_chunk(
            "a", "A bank shall review its outsourcing policy at least once a year.", ref="20"
        ),
        0.9,
    ),
    Hit(
        make_chunk("b", "Material outsourcing requires prior approval of the Board.", ref="21"), 0.7
    ),
]


def retrieval(hits: list[Hit] = HITS, route: str = "lookup") -> RetrievalResult:
    return RetrievalResult(
        "How often must the outsourcing policy be reviewed?", hits, route, date(2026, 10, 24), ()
    )  # type: ignore[arg-type]


class Scripted:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    def __call__(
        self, alias: str, messages: list[dict[str, str]], *, json_mode: bool, max_tokens: int
    ) -> LLMResponse:
        self.calls += 1
        return LLMResponse(self.text, model="fake")


def answerer(text: str, tmp_path: Path, threshold: float = 0.1) -> tuple[Answerer, Scripted]:
    backend = Scripted(text)
    return Answerer(LLMClient(backend, tmp_path), abstain_threshold=threshold), backend


def test_prompt_numbers_sources_and_adds_route_instructions() -> None:
    sources = format_sources(HITS)
    assert sources.startswith("[1] RBI | Title of doc (NUM/doc) | para 20 | status: current")
    messages = answer_messages("q?", HITS, date(2024, 3, 1), "comparison")
    assert "comparison question" in messages[0]["content"]
    assert "As of: 2024-03-01" in messages[1]["content"]
    overview = answer_messages("q?", HITS, None, "global", {"doc": "A summary."})
    assert "Document overviews" in overview[1]["content"] and "themes" in overview[0]["content"]


def test_answer_with_valid_citations(tmp_path: Path) -> None:
    ans, _ = answerer("The outsourcing policy must be reviewed at least once a year [1].", tmp_path)
    result = ans.answer(retrieval())
    assert not result.abstained
    assert [c.label for c in result.citations] == ["[NUM/doc §20]"]
    assert result.verification is not None and result.verification.ok


def test_low_score_abstains_without_calling_the_llm(tmp_path: Path) -> None:
    ans, backend = answerer("irrelevant", tmp_path, threshold=0.95)
    result = ans.answer(retrieval())
    assert (
        result.abstained and result.text == ABSTAIN_TEXT and result.reason == "low_retrieval_score"
    )
    assert backend.calls == 0
    assert ans.answer(retrieval(hits=[])).abstained
    assert ans.answer(retrieval(route="out_of_scope")).abstained


def test_model_not_found_becomes_abstention(tmp_path: Path) -> None:
    ans, _ = answerer("NOT_FOUND", tmp_path)
    result = ans.answer(retrieval())
    assert result.abstained and result.reason == "model_not_found"
    assert is_not_found("  NOT_FOUND.") and is_not_found("") and not is_not_found("Banks must...")


def test_invalid_markers_are_removed_and_flagged(tmp_path: Path) -> None:
    assert strip_invalid_markers("Rule [1][9].", 2) == "Rule [1]."
    ans, _ = answerer("The Board must approve material outsourcing [2][7].", tmp_path)
    result = ans.answer(retrieval())
    assert "[7]" not in result.text
    assert [c.number for c in result.citations] == [2]


def test_llm_outage_degrades_to_passages(tmp_path: Path) -> None:
    class Down:
        def __call__(self, *args: object, **kwargs: object) -> LLMResponse:
            raise LLMUnavailableError("down")

    result = Answerer(LLMClient(Down(), tmp_path), abstain_threshold=0.1).answer(retrieval())
    assert result.text == UNAVAILABLE_TEXT and len(result.citations) == 2


def test_verify_flags_uncited_unsupported_and_invalid() -> None:
    text = (
        "The outsourcing policy must be reviewed at least once a year [1]. "
        "Banks must also notify regulators within 30 days of any cyber incident [2]. "
        "Third parties need annual penetration testing by external auditors. "
        "Overview: [5]"
    )
    result = verify(text, HITS)
    states = [(s.cited, s.supported) for s in result.sentences]
    assert states[0] == (True, True)
    assert states[1] == (True, False)  # "30 days" is not in source 2
    assert states[2][0] is False  # no marker at all
    assert result.invalid_markers == (5,)
    assert result.uncited == 1 and result.unsupported == 1 and not result.ok
    assert lexical_support("[1]", "anything") == 1.0


def test_stream_yields_text_then_final_answer(tmp_path: Path) -> None:
    ans, _ = answerer("NBFCs must review the policy annually [1].", tmp_path)
    events = list(ans.stream(retrieval()))
    final = events[-1]
    assert isinstance(final, Answer)
    assert (
        "".join(e for e in events[:-1] if isinstance(e, str))
        == "NBFCs must review the policy annually [1]."
    )
    nf, _ = answerer("NOT_FOUND", tmp_path / "nf")
    nf_events = list(nf.stream(retrieval()))
    assert len(nf_events) == 1 and isinstance(nf_events[0], Answer) and nf_events[0].abstained
    low, _ = answerer("x", tmp_path / "low", threshold=0.99)
    assert next(iter(low.stream(retrieval()))).abstained  # type: ignore[union-attr]


def test_marker_removal_for_display() -> None:
    assert answer_text_without_markers("Rule applies [1][2]. Next [3].") == "Rule applies. Next."
