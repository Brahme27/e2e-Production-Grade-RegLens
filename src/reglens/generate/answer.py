"""Answering: retrieval result -> (abstain?) -> LLM answer with citations -> verification.

Abstention happens twice:
1. **before** the LLM: if the best reranked passage scores below a calibrated threshold, the
   corpus almost certainly doesn't cover the question, so we answer "not found" without
   spending an API call;
2. **by** the LLM: the prompt tells it to reply NOT_FOUND when the sources don't answer.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import date

from reglens.generate.prompts import NOT_FOUND, PROMPT_VERSION, answer_messages
from reglens.generate.verify import MARKER, Verification, verify
from reglens.index.store import Hit
from reglens.llm.client import LLMClient, LLMUnavailableError
from reglens.retrieve.pipeline import RetrievalResult

ABSTAIN_TEXT = (
    "I could not find this in the indexed regulations (RBI, SEBI, FCA and PRA documents "
    "on KYC, outsourcing, cyber and operational resilience, complaints, governance and "
    "model risk). Please check the regulator's website or rephrase the question."
)
UNAVAILABLE_TEXT = (
    "The answer service is temporarily unavailable. The most relevant passages are listed below."
)
ANSWER_MAX_TOKENS = 900


@dataclass(frozen=True)
class Citation:
    number: int
    label: str  # "[SS1/23 §2.4]"
    chunk_id: str
    doc_id: str
    doc_key: str
    ref: str
    regulator: str
    title: str
    url: str
    status: str
    valid_from: str | None
    valid_to: str | None
    text: str


@dataclass
class Answer:
    question: str
    text: str
    abstained: bool
    route: str
    as_of: date | None
    citations: list[Citation] = field(default_factory=list)
    verification: Verification | None = None
    reason: str = ""  # why we abstained / degraded
    prompt_version: str = PROMPT_VERSION


def citation_for(number: int, hit: Hit) -> Citation:
    c = hit.chunk
    return Citation(
        number=number,
        label=c.citation,
        chunk_id=c.chunk_id,
        doc_id=c.doc_id,
        doc_key=c.doc_key,
        ref=c.ref,
        regulator=c.regulator,
        title=c.title,
        url=c.url,
        status=c.status,
        valid_from=c.valid_from.isoformat() if c.valid_from else None,
        valid_to=c.valid_to.isoformat() if c.valid_to else None,
        text=c.text,
    )


def is_not_found(text: str) -> bool:
    return NOT_FOUND in text.strip()[:40] or not text.strip()


# gpt-oss sometimes falls back to its native citation style: 【1】 or 【2†para 1.8】.
# It occasionally puts the PARAGRAPH number where the source number belongs (【12†para12(1)】
# with 8 sources); the label after † then tells us which source it meant.
FULLWIDTH_MARKER = re.compile(r"【(\d{1,3})(?:†\s*(?:para\s*)?([^】]*))?】")


def _source_for_label(label: str, refs: Sequence[str]) -> int | None:
    """The one source whose paragraph ref the label names ("12(1)(i)" names ref "12", not "1")."""
    label = label.replace("\u202f", " ").strip()
    matches = [
        (len(ref), number)
        for number, ref in enumerate(refs, start=1)
        if ref and label.startswith(ref) and not label[len(ref) : len(ref) + 1].isalnum()
    ]
    if not matches:
        return None
    longest = max(length for length, _ in matches)
    best = [number for length, number in matches if length == longest]
    return best[0] if len(best) == 1 else None  # ambiguous: leave it to the invalid-marker check


def normalise_markers(text: str, refs: Sequence[str] = ()) -> str:
    def to_bracket(match: re.Match[str]) -> str:
        number, label = int(match.group(1)), match.group(2)
        if refs and label and not 1 <= number <= len(refs):
            number = _source_for_label(label, refs) or number
        return f"[{number}]"

    return FULLWIDTH_MARKER.sub(to_bracket, text)


def strip_invalid_markers(text: str, sources: int) -> str:
    return MARKER.sub(lambda m: m.group(0) if 1 <= int(m.group(1)) <= sources else "", text)


class Answerer:
    def __init__(
        self,
        llm: LLMClient,
        abstain_threshold: float,
        alias: str = "reasoning-large",
        summaries: dict[str, str] | None = None,
    ) -> None:
        self.llm = llm
        self.abstain_threshold = abstain_threshold
        self.alias = alias
        self.summaries = summaries or {}

    def should_abstain(self, retrieval: RetrievalResult) -> bool:
        if not retrieval.hits:
            return True
        if retrieval.route == "out_of_scope":
            return True
        return retrieval.hits[0].score < self.abstain_threshold

    def _messages(self, retrieval: RetrievalResult) -> list[dict[str, str]]:
        summaries = self.summaries if retrieval.route == "global" else None
        return answer_messages(
            retrieval.question, retrieval.hits, retrieval.as_of, retrieval.route, summaries
        )

    def _finish(self, retrieval: RetrievalResult, text: str) -> Answer:
        if is_not_found(text):
            return Answer(
                retrieval.question,
                ABSTAIN_TEXT,
                True,
                retrieval.route,
                retrieval.as_of,
                reason="model_not_found",
            )
        refs = [hit.chunk.ref for hit in retrieval.hits]
        text = strip_invalid_markers(normalise_markers(text.strip(), refs), len(refs))
        used = sorted({int(m) for m in MARKER.findall(text)})
        citations = [citation_for(n, retrieval.hits[n - 1]) for n in used]
        return Answer(
            retrieval.question,
            text,
            False,
            retrieval.route,
            retrieval.as_of,
            citations=citations,
            verification=verify(text, retrieval.hits),
        )

    def answer(self, retrieval: RetrievalResult) -> Answer:
        if self.should_abstain(retrieval):
            return Answer(
                retrieval.question,
                ABSTAIN_TEXT,
                True,
                retrieval.route,
                retrieval.as_of,
                reason="low_retrieval_score",
            )
        try:
            response = self.llm.complete(
                self._messages(retrieval),
                alias=self.alias,
                max_tokens=ANSWER_MAX_TOKENS,
                purpose="answer",
            )
        except LLMUnavailableError:
            return self._unavailable(retrieval, "llm_unavailable")
        return self._finish(retrieval, response.text)

    @staticmethod
    def _unavailable(retrieval: RetrievalResult, reason: str) -> Answer:
        """No generated answer: say so and list the retrieved passages instead."""
        fallback = Answer(
            retrieval.question,
            UNAVAILABLE_TEXT,
            True,
            retrieval.route,
            retrieval.as_of,
            reason=reason,
        )
        fallback.citations = [citation_for(i, h) for i, h in enumerate(retrieval.hits, start=1)]
        return fallback

    def stream(self, retrieval: RetrievalResult) -> Iterator[str | Answer]:
        """Yield text deltas, then the final verified Answer as the last item."""
        if self.should_abstain(retrieval):
            yield Answer(
                retrieval.question,
                ABSTAIN_TEXT,
                True,
                retrieval.route,
                retrieval.as_of,
                reason="low_retrieval_score",
            )
            return
        parts: list[str] = []
        released = False  # hold the opening text until we know it isn't "NOT_FOUND"
        try:
            for delta in self.llm.stream(
                self._messages(retrieval),
                alias=self.alias,
                max_tokens=ANSWER_MAX_TOKENS,
                purpose="answer",
            ):
                parts.append(delta)
                if released:
                    yield delta
                    continue
                so_far = "".join(parts).lstrip()
                if NOT_FOUND.startswith(so_far) or so_far.startswith(NOT_FOUND):
                    continue  # still ambiguous, or a refusal we will replace
                released = True
                yield so_far
        except LLMUnavailableError:
            if released:  # the user saw part of an unverified answer: replace it, don't re-ask
                yield self._unavailable(retrieval, "llm_interrupted")
            else:  # nothing shown yet: one more (non-streaming) attempt, then passages
                yield self.answer(retrieval)
            return
        yield self._finish(retrieval, "".join(parts))


def answer_text_without_markers(text: str) -> str:
    return re.sub(r"\s*\[\d{1,2}\]", "", text)
