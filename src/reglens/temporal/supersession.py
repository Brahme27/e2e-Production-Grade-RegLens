"""Which document replaced (or amended) which: the supersession graph.

Two extractors, evaluated against hand-labelled edges (``evals/supersession_gold.yaml``):

1. **Rules**: sentences with a repeal/rescind/supersede verb that *name* another document,
   by its number ("SEBI/HO/OIAE/IGRD/P/CIR/2022/0150") or its full title. Precise, but blind
   to the generic RBI 2025-26 style "the existing directions relating to KYC as applicable to
   Commercial Banks stand repealed", which names nothing.
2. **LLM**: for those generic repeal clauses only, the model sees the clause plus the older
   documents of the same regulator and picks which ones the clause repeals.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from typing import Literal

from reglens.llm.client import LLMClient, LLMUnavailableError
from reglens.log import get_logger
from reglens.parse.model import ParsedDocument
from reglens.parse.text import first_date

log = get_logger(__name__)

EdgeType = Literal["SUPERSEDES", "AMENDS"]
Method = Literal["rule", "llm", "title"]

SUPERSEDE_VERB = re.compile(
    r"\b(repeal\w*|rescind\w*|rescission|supersed\w*|supersession|stand\w* withdrawn|"
    r"hereby withdrawn|replace[sd]?|deprecat\w*)\b",
    re.I,
)
# a verb, not a noun: "is hereby amended" counts; "Modification in Cyber Security
# framework" (the title of a circular listed in a table) does not
AMEND_VERB = re.compile(
    r"\b(?:(?:is|are|stands?|shall be|hereby|has been|have been|stand)\s+(?:amended|modified)"
    r"|amends|amending)\b",
    re.I,
)
GENERIC_REPEAL = re.compile(
    r"existing\s+(directions|instructions|guidelines)[^.]{0,250}?\bstand\s+repealed", re.I
)
_DATE_TEXT = (
    r"[A-Za-z]+\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}"
    r"|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+\d{4}"
    r"|\d{1,2}[./-]\d{1,2}[./-]\d{4}"
)
WITH_EFFECT_FROM = re.compile(rf"with effect from\s+({_DATE_TEXT})", re.I)
AMENDING_TITLE = re.compile(r"^(clarifications?|amendments?|modifications?|extension)\b", re.I)
CIRCULAR_NUMBER = re.compile(
    r"\b(?:SEBI/HO/[A-Z0-9/_-]+/\d{4}/\d+(?:/\d+)?|CIR/[A-Z0-9/_-]+/\d{4}(?:/\d+)?"
    r"|RBI/[A-Z]*/?\d{4}-\d{2}/\d+)\b",
    re.I,
)
SENTENCE = re.compile(r"(?<=[.;])\s+(?=[A-Z(])")
LIST_INTRO = re.compile(r"(\bfollowing\b|\blist of\b|\btable\b|:\s*$|:\s*[ivx]+\.)", re.I)
MAX_TABLE_GAP = 1  # paragraphs without numbers allowed inside a listed table
MIN_TITLE_CHARS = 25


@dataclass(frozen=True)
class Edge:
    source: str  # the newer document's id
    target: str  # a corpus doc id, or "ext:<circular number>" for documents we don't hold
    type: EdgeType
    method: Method
    effective: date | None = None  # when the replacement took effect, if stated
    evidence: str = ""  # "<doc key> ¶<ref>"

    @property
    def pair(self) -> tuple[str, str, str]:
        return (self.source, self.target, self.type)


def _norm(text: str) -> str:
    text = text.lower().replace("–", "-").replace("—", "-")
    text = re.sub(r"\(updated as on[^)]*\)", "", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _norm_number(number: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", number.upper())


def latest_versions(documents: list[ParsedDocument]) -> dict[str, ParsedDocument]:
    """One document per id: the version with the latest effective date."""
    latest: dict[str, ParsedDocument] = {}
    for doc in documents:
        best = latest.get(doc.doc_id)
        if best is None or (doc.effective_from or date.min) > (best.effective_from or date.min):
            latest[doc.doc_id] = doc
    return latest


def start_date(doc_id: str, documents: list[ParsedDocument]) -> date | None:
    """When a document first applied: its issue date or its earliest version's start."""
    dates = [d.effective_from for d in documents if d.doc_id == doc_id and d.effective_from]
    issue = next((d.issue_date for d in documents if d.doc_id == doc_id and d.issue_date), None)
    candidates = [*dates, *([issue] if issue else [])]
    return min(candidates) if candidates else None


class _Resolver:
    """Finds mentions of corpus documents (by number or title) inside a sentence."""

    def __init__(self, docs: dict[str, ParsedDocument]) -> None:
        self.by_number = {
            _norm_number(d.doc_number): d.doc_id for d in docs.values() if d.doc_number
        }
        self.by_title = {
            _norm(d.title): d.doc_id for d in docs.values() if len(d.title) >= MIN_TITLE_CHARS
        }

    def mentions(self, sentence: str) -> set[str]:
        found: set[str] = set()
        for number in CIRCULAR_NUMBER.findall(repair_numbers(sentence)):
            found.add(self.by_number.get(_norm_number(number), f"ext:{number.upper()}"))
        normalized = _norm(sentence)
        found.update(doc_id for title, doc_id in self.by_title.items() if title in normalized)
        return found


def repair_numbers(text: str) -> str:
    """Undo PDF line-wrapping inside circular numbers: 'CIR/2 022/68' -> 'CIR/2022/68'.

    PDF tables break long numbers across lines; once rejoined with a space they no longer
    match. Inside something that already looks like a circular number we drop spaces next
    to '/' and between digits.
    """
    text = text.replace("￾", "-")  # PDF soft hyphen at a line break
    text = re.sub(r"\s*/[\s/]*", "/", text)  # "2019 / /28528" -> "2019/28528"
    return re.sub(r"(?<=/\d)\s+(?=\d)|(?<=/\d\d)\s+(?=\d)|(?<=/\d\d\d)\s+(?=\d)", "", text)


def _kind_of(sentence: str) -> EdgeType | None:
    if SUPERSEDE_VERB.search(sentence):
        return "SUPERSEDES"
    if AMEND_VERB.search(sentence):
        return "AMENDS"
    return None


def rule_edges(documents: list[ParsedDocument]) -> list[Edge]:
    docs = latest_versions(documents)
    resolver = _Resolver(docs)
    edges: dict[tuple[str, str, str], Edge] = {}
    for doc in docs.values():
        table_kind: EdgeType | None = None  # "Table 1: List of circulars to get superseded"
        table_gap = 0
        for para in doc.paragraphs:
            text = para.text.replace("\n", " ")
            has_numbers = bool(CIRCULAR_NUMBER.search(repair_numbers(text)))
            if table_kind is not None and not has_numbers:
                table_gap += 1
                if table_gap > MAX_TABLE_GAP:
                    table_kind = None
            elif has_numbers:
                table_gap = 0
            inherited: EdgeType | None = table_kind  # "rescinds the following: i. ... ii."
            for sentence in SENTENCE.split(text):
                kind = _kind_of(sentence) or inherited
                if kind is not None and LIST_INTRO.search(sentence):
                    inherited = kind
                    table_kind, table_gap = kind, 0
                if kind is None:
                    continue
                stated = WITH_EFFECT_FROM.search(sentence)
                for target in resolver.mentions(sentence) - {doc.doc_id}:
                    edge = Edge(
                        source=doc.doc_id,
                        target=target,
                        type=kind,
                        method="rule",
                        effective=first_date(stated.group(1)) if stated else None,
                        evidence=f"{doc.key} ¶{para.ref}",
                    )
                    edges.setdefault(edge.pair, edge)
    return [*edges.values(), *_title_edges(docs)]


def _title_edges(docs: dict[str, ParsedDocument]) -> list[Edge]:
    """'Clarifications to <title of another document>' amends that document."""
    edges = []
    for doc in docs.values():
        match = AMENDING_TITLE.match(doc.title)
        if not match:
            continue
        rest = _norm(doc.title[match.end() :]).removeprefix("to ").removeprefix("of ")
        for other in docs.values():
            if other.doc_id != doc.doc_id and _norm(other.title).startswith(rest[:60]):
                edges.append(
                    Edge(doc.doc_id, other.doc_id, "AMENDS", "title", evidence=f"{doc.key} title")
                )
    return edges


# ---------------------------------------------------------------- LLM for generic repeals
LLM_SYSTEM = """You map repeal clauses in financial regulation to the documents they repeal.
You are given one repeal clause from a NEW document and a list of OLDER candidate documents
from the same regulator. A candidate is repealed only if the clause's subject matter AND the
entities it applies to cover that candidate (fully or for those entities).
Match on subject matter, not on shared words: corporate governance is a different subject
from IT governance; outsourcing is a different subject from cybersecurity.
Return JSON: {"repealed": ["<candidate id>", ...], "reason": "<one sentence>"}.
Return an empty list when no candidate is covered. Never invent ids."""


def generic_repeal_clauses(doc: ParsedDocument) -> list[tuple[str, str]]:
    """(paragraph ref, clause) for repeals that don't name what they repeal."""
    return [
        (p.ref, match.group(0))
        for p in doc.paragraphs
        if (match := GENERIC_REPEAL.search(p.text.replace("\n", " ")))
    ]


def llm_edges(
    documents: list[ParsedDocument], llm: LLMClient, alias: str = "reasoning-large"
) -> list[Edge]:
    docs = latest_versions(documents)
    edges = []
    for doc in docs.values():
        clauses = generic_repeal_clauses(doc)
        if not clauses:
            continue
        doc_start = start_date(doc.doc_id, documents) or date.max
        candidates = [
            other
            for other in docs.values()
            if other.doc_id != doc.doc_id
            and other.regulator == doc.regulator
            and (start_date(other.doc_id, documents) or date.max) < doc_start
        ]
        if not candidates:
            continue
        listing = "\n".join(
            f"- id: {c.doc_id} | title: {c.title} | applies to: {', '.join(c.applies_to)}"
            f" | issued: {start_date(c.doc_id, documents)}"
            for c in sorted(candidates, key=lambda c: c.doc_id)
        )
        for ref, clause in clauses:
            user = (
                f"NEW document: {doc.title} (applies to: {', '.join(doc.applies_to)})\n"
                f"Repeal clause (para {ref}): {clause}\n\nOLDER candidates:\n{listing}"
            )
            try:
                answer = llm.complete_json(
                    [{"role": "system", "content": LLM_SYSTEM}, {"role": "user", "content": user}],
                    alias=alias,
                    max_tokens=600,
                    purpose="supersession",
                )
            except (LLMUnavailableError, ValueError) as exc:
                log.warning("supersession_llm_failed", doc=doc.doc_id, error=str(exc))
                continue
            valid = {c.doc_id for c in candidates}
            for target in answer.get("repealed", []):
                if target in valid:  # guard against invented ids
                    edges.append(
                        Edge(doc.doc_id, target, "SUPERSEDES", "llm", evidence=f"{doc.key} ¶{ref}")
                    )
    return edges


def merge_edges(*groups: list[Edge]) -> list[Edge]:
    """Union by (source, target, type); the first extractor that found an edge wins."""
    merged: dict[tuple[str, str, str], Edge] = {}
    for group in groups:
        for edge in group:
            merged.setdefault(edge.pair, edge)
    return sorted(merged.values(), key=lambda e: e.pair)


def edges_to_json(edges: list[Edge]) -> str:
    rows = [
        asdict(e) | {"effective": e.effective.isoformat() if e.effective else None} for e in edges
    ]
    return json.dumps(rows, indent=1)


def edges_from_json(text: str) -> list[Edge]:
    return [
        Edge(
            **{
                **row,
                "effective": date.fromisoformat(row["effective"]) if row["effective"] else None,
            }
        )
        for row in json.loads(text)
    ]
