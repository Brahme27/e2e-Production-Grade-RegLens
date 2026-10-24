"""Validity intervals: from when to when each document version applied.

    valid_from = when the version took effect (stated commencement > edition date > issue)
    valid_to   = the next version's valid_from, or the date a newer document repealed it
                 (null = still in force)

Retrieval later filters on ``valid_from <= as_of < valid_to``, so a question "as of
1 March 2024" only ever sees the text that applied on that day.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from reglens.parse.model import Paragraph, ParsedDocument
from reglens.parse.text import first_date
from reglens.temporal.supersession import Edge, start_date

Status = Literal["current", "superseded", "future"]

COMMENCEMENT = re.compile(
    r"(?:come|came|comes)\s+into\s+(?:force|effect)\s+(?:from|on|with effect from)\s+"
    r"([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+[A-Za-z]+,?\s+\d{4})",
    re.I,
)
COMMENCEMENT_SEARCH_PARAGRAPHS = 8


@dataclass(frozen=True)
class Validity:
    key: str  # "<doc_id>@<version>"
    doc_id: str
    version: str
    valid_from: date | None
    valid_to: date | None  # exclusive; None = open-ended
    status: Status
    superseded_by: str | None = None  # doc id that repealed it, if any

    def applies_on(self, day: date) -> bool:
        started = self.valid_from is None or self.valid_from <= day
        not_ended = self.valid_to is None or day < self.valid_to
        return started and not_ended


def paragraph_interval(
    doc: ParsedDocument, para: Paragraph, validity: Validity, earliest: bool
) -> tuple[date | None, date | None]:
    """When one paragraph's wording applied.

    For the *oldest* version we hold, a paragraph applied from its own stated date (FCA/PRA
    provision date, RBI amendment footnote) or, failing that, the document's issue date:
    we hold the 2025 text of the 2016 KYC direction, but its unamended paragraphs date
    from 2016. For later versions, older wording lives in the earlier snapshot, so the
    paragraph applies from the version start. Every paragraph ends with its version.
    """
    if not earliest:
        return validity.valid_from, validity.valid_to
    start = para.effective_from or doc.issue_date or validity.valid_from
    if validity.valid_from and start and start > validity.valid_from:
        start = validity.valid_from  # never later than the version itself
    return start, validity.valid_to


def load_validity(path: Path) -> dict[str, Validity]:
    """Read ``data/processed/validity.json`` written by the temporal run."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    result = {}
    for key, row in raw.items():
        doc_id, version = key.split("@", 1)
        result[key] = Validity(
            key=key,
            doc_id=doc_id,
            version=version,
            valid_from=date.fromisoformat(row["valid_from"]) if row["valid_from"] else None,
            valid_to=date.fromisoformat(row["valid_to"]) if row["valid_to"] else None,
            status=row["status"],
            superseded_by=row["superseded_by"],
        )
    return result


def stated_commencement(doc: ParsedDocument) -> date | None:
    """'These Directions shall come into effect from April 1, 2024' (first paragraphs only)."""
    for para in doc.paragraphs[:COMMENCEMENT_SEARCH_PARAGRAPHS]:
        match = COMMENCEMENT.search(para.text.replace("\n", " "))
        if match:
            return first_date(match.group(1))
    return None


def _repeal_dates(
    documents: list[ParsedDocument], edges: list[Edge], known: set[str]
) -> dict[str, tuple[date, str]]:
    """When (and by whom) each corpus document was repealed: the earliest repeal wins."""
    repealed: dict[str, tuple[date, str]] = {}
    for edge in edges:
        if edge.type != "SUPERSEDES" or edge.target not in known:
            continue
        when = edge.effective or start_date(edge.source, documents)
        if when is not None and (edge.target not in repealed or when < repealed[edge.target][0]):
            repealed[edge.target] = (when, edge.source)
    return repealed


def _status(start: date | None, end: date | None, today: date) -> Status:
    if start is not None and start > today:
        return "future"
    if end is not None and end <= today:
        return "superseded"
    return "current"


def compute_validity(
    documents: list[ParsedDocument], edges: list[Edge], today: date
) -> dict[str, Validity]:
    by_doc: dict[str, list[ParsedDocument]] = {}
    for doc in documents:
        by_doc.setdefault(doc.doc_id, []).append(doc)
    repealed = _repeal_dates(documents, edges, set(by_doc))

    result: dict[str, Validity] = {}
    for doc_id, versions in by_doc.items():
        # a stated commencement beats the issue date for an un-versioned document
        starts = [
            (
                (stated_commencement(v) or v.effective_from)
                if len(versions) == 1
                else v.effective_from,
                v,
            )
            for v in versions
        ]
        starts.sort(key=lambda item: item[0] or date.min)
        for index, (start, version) in enumerate(starts):
            end = starts[index + 1][0] if index + 1 < len(starts) else None
            superseded_by = None
            if index == len(starts) - 1 and doc_id in repealed:
                end, superseded_by = repealed[doc_id]
            result[version.key] = Validity(
                key=version.key,
                doc_id=doc_id,
                version=version.version,
                valid_from=start,
                valid_to=end,
                status=_status(start, end, today),
                superseded_by=superseded_by,
            )
    return result
