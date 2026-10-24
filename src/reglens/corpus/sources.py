"""The curated source list (``configs/sources.yaml``): which regulatory documents we index.

A curated list (rather than "crawl everything") keeps the corpus small enough for a CPU
laptop and focused on six themes that all four regulators cover, so cross-regulator
questions ("RBI vs FCA on outsourcing") have answers on both sides.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

Regulator = Literal["RBI", "SEBI", "FCA", "PRA"]
SourceKind = Literal["html", "pdf", "sebi_circular", "fca_chapter", "pra_part"]


class Snapshot(BaseModel):
    """An older version of a document, kept at its own URL (official archive or Wayback)."""

    label: date  # the version's date, used as its version key
    url: str
    effective_from: date | None = None


class SourceDoc(BaseModel):
    """One regulatory document (and, optionally, older versions of it to snapshot)."""

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]+$")
    regulator: Regulator
    kind: SourceKind
    doc_type: str  # directions, master_direction, circular, rulebook_part, handbook_chapter, ...
    title: str
    topics: list[str]
    applies_to: list[str]
    url: str | None = None  # html / pdf / sebi_circular: the current version
    chapter: str | None = None  # fca_chapter, e.g. "prin2a"
    part: str | None = None  # pra_part slug, e.g. "outsourcing"
    as_of: list[date] = Field(default_factory=list)  # pra_part: dates to snapshot
    snapshots: list[Snapshot] = Field(default_factory=list)  # html / pdf: older versions
    issue_date: date | None = None
    effective_from: date | None = None  # when the current version took effect, if known

    @model_validator(mode="after")
    def _kind_fields(self) -> SourceDoc:
        needed = {"html": self.url, "pdf": self.url, "sebi_circular": self.url}
        needed["fca_chapter"] = self.chapter
        needed["pra_part"] = self.part if self.as_of else None
        if needed[self.kind] is None:
            raise ValueError(f"{self.id}: missing the fields that kind={self.kind} needs")
        return self


class SourceList(BaseModel):
    documents: list[SourceDoc]

    @model_validator(mode="after")
    def _unique_ids(self) -> SourceList:
        ids = [d.id for d in self.documents]
        duplicates = {i for i in ids if ids.count(i) > 1}
        if duplicates:
            raise ValueError(f"duplicate source ids: {sorted(duplicates)}")
        return self

    def by_id(self, doc_id: str) -> SourceDoc:
        for doc in self.documents:
            if doc.id == doc_id:
                return doc
        raise KeyError(doc_id)


def load_sources(path: Path) -> SourceList:
    return SourceList.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
