"""Build the golden evaluation set: questions with known answers and known source paragraphs.

Categories (target counts):
- lookup (80): an LLM writes a question that one real paragraph answers (20 per regulator)
- temporal (30): the same, from paragraphs of *superseded* versions, asked "as of" a date
  when that wording applied
- comparison (25): two paragraphs on the same topic from two regulators
- global (15), unanswerable (30), adversarial (20): hand-written (``evals/golden/handwritten.yaml``)

A retrieved chunk counts as correct if it is the source paragraph **or a near-duplicate**
valid on the question's date: the same KYC rule appears in the bank and the NBFC
directions, and unchanged rules appear in every PRA snapshot.
"""

from __future__ import annotations

import json
import random
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from reglens.index.chunking import Chunk
from reglens.llm.client import LLMClient, LLMUnavailableError
from reglens.log import get_logger

log = get_logger(__name__)

MIN_WORDS, MAX_WORDS = 40, 220
NEAR_DUPLICATE = 0.7
SHINGLE = 5
EARLIEST_AS_OF = date(2019, 1, 1)

QUESTION_SYSTEM = """You write evaluation questions for a regulatory-compliance search engine.
Given ONE paragraph of financial regulation, write ONE question that a compliance officer
would realistically ask and that this paragraph answers. Rules:
- paraphrase: do not copy phrases of more than 4 words from the paragraph;
- do not mention paragraph numbers or the document title; you MAY name the regulator;
- the question must be answerable from this paragraph alone;
- also give a 1-2 sentence reference answer based only on the paragraph.
Reply as JSON: {"question": "...", "answer": "...", "answerable": true|false}"""

TEMPORAL_HINT = (
    "The question must ask what applied AS OF {day} (write the date in the question, e.g. "
    '"As of {day_text}, ..."), because the rule has since changed.'
)

COMPARE_SYSTEM = """You write evaluation questions for a regulatory-compliance search engine.
Given two paragraphs on the same topic from two different regulators, write ONE question that
asks how the two regulators' requirements compare, naming both regulators. Also give a 2-3
sentence reference answer that uses both paragraphs.
Reply as JSON: {"question": "...", "answer": "...", "answerable": true|false}"""


@dataclass
class GoldItem:
    id: str
    category: str  # lookup | temporal | comparison | global | unanswerable | adversarial
    question: str
    expected: str  # answer | abstain | refuse
    as_of: str | None = None
    # each group is a list of acceptable (doc_id, ref) pairs; recall = groups hit / groups
    gold_groups: list[list[list[str]]] = field(default_factory=list)
    gold_docs: list[str] = field(default_factory=list)  # global questions: documents expected
    reference_answer: str = ""
    provenance: str = "generated"  # generated | hand-written
    source_chunk: str = ""


def _shingles(text: str) -> set[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {tuple(words[i : i + SHINGLE]) for i in range(max(len(words) - SHINGLE + 1, 1))}


def _jaccard(a: set[tuple[str, ...]], b: set[tuple[str, ...]]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


class Equivalents:
    """Finds near-duplicate paragraphs (any document / version) of a source paragraph."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = [c for c in chunks if c.part == 1]
        self.shingles = [_shingles(c.text) for c in self.chunks]
        self.index: dict[tuple[str, ...], list[int]] = defaultdict(list)
        for i, sh in enumerate(self.shingles):
            for s in list(sh)[:: max(len(sh) // 8, 1)]:  # a sample of shingles as keys
                self.index[s].append(i)

    def of(self, chunk: Chunk, as_of: date | None) -> list[list[str]]:
        source = _shingles(chunk.text)
        candidates = {i for s in source for i in self.index.get(s, [])}
        group = {(chunk.doc_id, chunk.ref)}
        for i in candidates:
            other = self.chunks[i]
            if as_of is not None and not _valid_on(other, as_of):
                continue
            if _jaccard(source, self.shingles[i]) >= NEAR_DUPLICATE:
                group.add((other.doc_id, other.ref))
        return [list(pair) for pair in sorted(group)]


def _valid_on(chunk: Chunk, day: date) -> bool:
    return (chunk.valid_from is None or chunk.valid_from <= day) and (
        chunk.valid_to is None or day < chunk.valid_to
    )


def _eligible(chunk: Chunk) -> bool:
    words = len(chunk.text.split())
    return (
        chunk.parts == 1
        and MIN_WORDS <= words <= MAX_WORDS
        and "¶" not in chunk.ref
        and " | " not in chunk.text
        and not re.search(r"\b(repeal|notwithstanding such|shall be called)\b", chunk.text, re.I)
    )


def _spread(chunks: list[Chunk], n: int, rng: random.Random) -> list[Chunk]:
    """n chunks spread across documents (round-robin), random within each document."""
    by_doc: dict[str, list[Chunk]] = defaultdict(list)
    for c in chunks:
        by_doc[c.doc_id].append(c)
    for items in by_doc.values():
        rng.shuffle(items)
    docs = sorted(by_doc)
    rng.shuffle(docs)
    picked: list[Chunk] = []
    while len(picked) < n and any(by_doc.values()):
        for doc_id in docs:
            if by_doc[doc_id] and len(picked) < n:
                picked.append(by_doc[doc_id].pop())
    return picked


def _ask(llm: LLMClient, system: str, user: str, purpose: str) -> dict[str, Any] | None:
    try:
        answer = llm.complete_json(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            alias="reasoning-large",
            max_tokens=700,
            purpose=purpose,
        )
    except (LLMUnavailableError, ValueError) as exc:
        log.warning("golden_llm_failed", purpose=purpose, error=str(exc))
        return None
    if not answer.get("answerable", True) or not str(answer.get("question", "")).strip():
        return None
    return answer


def _describe(chunk: Chunk) -> str:
    return (
        f"Regulator: {chunk.regulator}\nApplies to: {', '.join(chunk.applies_to)}\n"
        f"Section: {' > '.join(chunk.section_path)}\nParagraph:\n{chunk.text}"
    )


def lookup_items(
    chunks: list[Chunk], eq: Equivalents, llm: LLMClient, per_regulator: int, rng: random.Random
) -> list[GoldItem]:
    items: list[GoldItem] = []
    current = [c for c in chunks if c.status == "current" and _eligible(c)]
    for regulator in ("RBI", "SEBI", "FCA", "PRA"):
        pool = [c for c in current if c.regulator == regulator]
        for chunk in _spread(pool, per_regulator, rng):
            answer = _ask(llm, QUESTION_SYSTEM, _describe(chunk), "golden_lookup")
            if answer is None:
                continue
            items.append(
                GoldItem(
                    id=f"lookup-{len(items) + 1:03d}",
                    category="lookup",
                    question=str(answer["question"]).strip(),
                    expected="answer",
                    gold_groups=[eq.of(chunk, None)],
                    reference_answer=str(answer.get("answer", "")),
                    source_chunk=chunk.chunk_id,
                )
            )
    return items


def _midpoint(chunk: Chunk) -> date | None:
    if chunk.valid_to is None:
        return None
    start = max(chunk.valid_from or EARLIEST_AS_OF, EARLIEST_AS_OF)
    if start >= chunk.valid_to:
        return None
    return start + timedelta(days=(chunk.valid_to - start).days // 2)


def temporal_items(
    chunks: list[Chunk], eq: Equivalents, llm: LLMClient, n: int, rng: random.Random
) -> list[GoldItem]:
    """Paragraphs whose wording no longer applies (superseded version or repealed doc)."""
    current_text = {(c.doc_id, c.ref): c.text for c in chunks if c.status == "current"}
    pool = [
        c
        for c in chunks
        if c.status == "superseded"
        and _eligible(c)
        and _midpoint(c) is not None
        and current_text.get((c.doc_id, c.ref)) != c.text  # the wording really changed
    ]
    items: list[GoldItem] = []
    for chunk in _spread(pool, n, rng):
        day = _midpoint(chunk)
        if day is None:  # filtered above; keeps the type checker honest
            continue
        hint = TEMPORAL_HINT.format(day=day.isoformat(), day_text=day.strftime("%d %B %Y"))
        answer = _ask(llm, QUESTION_SYSTEM + "\n" + hint, _describe(chunk), "golden_temporal")
        if answer is None:
            continue
        items.append(
            GoldItem(
                id=f"temporal-{len(items) + 1:03d}",
                category="temporal",
                question=str(answer["question"]).strip(),
                expected="answer",
                as_of=day.isoformat(),
                gold_groups=[eq.of(chunk, day)],
                reference_answer=str(answer.get("answer", "")),
                source_chunk=chunk.chunk_id,
            )
        )
    return items


def comparison_items(
    chunks: list[Chunk],
    vectors: dict[str, np.ndarray],
    eq: Equivalents,
    llm: LLMClient,
    n: int,
    *,
    rng: random.Random,
) -> list[GoldItem]:
    """Pairs of similar paragraphs from different regulators sharing a topic."""
    current = [
        c for c in chunks if c.status == "current" and _eligible(c) and c.chunk_id in vectors
    ]
    pairs = [
        ("RBI", "FCA"),
        ("RBI", "PRA"),
        ("SEBI", "FCA"),
        ("SEBI", "PRA"),
        ("RBI", "SEBI"),
        ("FCA", "PRA"),
    ]
    items: list[GoldItem] = []
    used: set[str] = set()
    for round_ in range(n):
        left_reg, right_reg = pairs[round_ % len(pairs)]
        lefts = [c for c in current if c.regulator == left_reg and c.chunk_id not in used]
        rng.shuffle(lefts)
        for left in lefts[:20]:
            rights = [
                c
                for c in current
                if c.regulator == right_reg
                and set(c.topics) & set(left.topics)
                and c.chunk_id not in used
            ]
            if not rights:
                continue
            sims = [float(vectors[left.chunk_id] @ vectors[r.chunk_id]) for r in rights]
            best = int(np.argmax(sims))
            if sims[best] < 0.75:  # noqa: PLR2004 - must genuinely be about the same thing
                continue
            right = rights[best]
            user = f"PARAGRAPH 1\n{_describe(left)}\n\nPARAGRAPH 2\n{_describe(right)}"
            answer = _ask(llm, COMPARE_SYSTEM, user, "golden_comparison")
            if answer is None:
                continue
            used.update({left.chunk_id, right.chunk_id})
            items.append(
                GoldItem(
                    id=f"comparison-{len(items) + 1:03d}",
                    category="comparison",
                    question=str(answer["question"]).strip(),
                    expected="answer",
                    gold_groups=[eq.of(left, None), eq.of(right, None)],
                    reference_answer=str(answer.get("answer", "")),
                    source_chunk=f"{left.chunk_id},{right.chunk_id}",
                )
            )
            break
    return items


def handwritten_items(path: Path) -> list[GoldItem]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    items = []
    for category, entries in raw.items():
        for number, entry in enumerate(entries, start=1):
            items.append(
                GoldItem(
                    id=f"{category}-{number:03d}",
                    category=category,
                    question=entry["question"],
                    expected=entry["expected"],
                    as_of=entry.get("as_of"),
                    gold_docs=entry.get("gold_docs", []),
                    reference_answer=entry.get("note", ""),
                    provenance="hand-written",
                )
            )
    return items


def save(items: list[GoldItem], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")


def load(path: Path) -> list[GoldItem]:
    return [GoldItem(**json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines()]
