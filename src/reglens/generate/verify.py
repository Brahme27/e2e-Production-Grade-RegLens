"""Citation verification: is every claim cited, and does the cited text support it?

Cheap checks run on every answer (no LLM):
- markers must point at a retrieved source ([9] when there are 8 sources is invalid);
- each sentence that states something must carry at least one valid marker;
- **lexical support**: enough of the sentence's content words (and all its numbers) must
  appear in the cited source text. Paraphrases score lower than quotes, so this is a
  conservative flag, not a verdict. The LLM judge in the evaluation suite measures true
  support (citation precision).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from reglens.index.store import Hit

MARKER = re.compile(r"\[(\d{1,2})\]")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(*\-•])|\n+")
WORD = re.compile(r"[a-z][a-z\-]{2,}")
NUMBER = re.compile(r"\b\d+(?:\.\d+)?\b")
STOPWORDS = frozenset(
    (  # noqa: SIM905 - a word list is easier to edit as text
        "all also and any are been being can could did does doing each for from "
        "had has have into it's its may more most must nor not only other our "
        "over per shall should some such than that the their them then there "
        "these they this those under upon via was were what when where which "
        "while who whom will with would yes you your "
    ).split()
)
SUPPORT_THRESHOLD = 0.35
MIN_CLAIM_WORDS = 4


@dataclass(frozen=True)
class SentenceCheck:
    text: str
    markers: tuple[int, ...]
    cited: bool
    supported: bool
    support: float


@dataclass(frozen=True)
class Verification:
    sentences: tuple[SentenceCheck, ...]
    invalid_markers: tuple[int, ...]
    cited_sources: tuple[int, ...]

    @property
    def uncited(self) -> int:
        return sum(1 for s in self.sentences if not s.cited)

    @property
    def unsupported(self) -> int:
        return sum(1 for s in self.sentences if s.cited and not s.supported)

    @property
    def ok(self) -> bool:
        return not self.invalid_markers and self.uncited == 0 and self.unsupported == 0


def _content_words(text: str) -> set[str]:
    return {w for w in WORD.findall(text.lower()) if w not in STOPWORDS}


def lexical_support(sentence: str, source: str) -> float:
    words = _content_words(MARKER.sub("", sentence))
    if not words:
        return 1.0
    source_words = _content_words(source)
    # light stemming: "outsourced" ~ "outsourcing"
    stems = {w[:6] for w in source_words}
    overlap = sum(1 for w in words if w in source_words or w[:6] in stems) / len(words)
    numbers = set(NUMBER.findall(MARKER.sub("", sentence)))
    if numbers and not numbers <= set(NUMBER.findall(source)):
        overlap = min(overlap, SUPPORT_THRESHOLD - 0.01)  # a number we can't find = unsupported
    return overlap


def verify(answer: str, hits: list[Hit]) -> Verification:
    checks = []
    invalid: set[int] = set()
    cited_sources: set[int] = set()
    for raw in SENTENCE_SPLIT.split(answer.strip()):
        sentence = raw.strip()
        if not sentence:
            continue
        markers = tuple(int(m) for m in MARKER.findall(sentence))
        valid = tuple(m for m in markers if 1 <= m <= len(hits))
        invalid.update(m for m in markers if m not in valid)
        cited_sources.update(valid)
        claim = len(_content_words(MARKER.sub("", sentence))) >= MIN_CLAIM_WORDS
        if not claim:  # headings, "In summary:" and similar connective text
            checks.append(SentenceCheck(sentence, valid, True, True, 1.0))
            continue
        support = max(
            (lexical_support(sentence, hits[m - 1].chunk.text) for m in valid), default=0.0
        )
        checks.append(
            SentenceCheck(
                sentence, valid, bool(valid), support >= SUPPORT_THRESHOLD, round(support, 3)
            )
        )
    return Verification(tuple(checks), tuple(sorted(invalid)), tuple(sorted(cited_sources)))
