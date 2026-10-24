"""The parsed-document model every parser produces, whatever the regulator or format.

Regulatory text is naturally addressed by **paragraph number** ("para 38", "PRIN 2A.4.1R",
"rule 2.1"), so a paragraph, not a page or a fixed-size window, is our unit of meaning
and of citation.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

ParagraphKind = Literal["rule", "guidance", "evidential", "direction", "paragraph", "table"]


@dataclass(frozen=True)
class Paragraph:
    ref: str  # citation reference as the regulator writes it: "93", "PRIN 2A.1.3", "2.1"
    text: str
    section_path: tuple[str, ...] = ()  # headings above it, outermost first
    kind: ParagraphKind = "paragraph"
    effective_from: date | None = None  # when this paragraph's wording took effect, if stated
    notes: tuple[str, ...] = ()  # e.g. RBI amendment footnotes "Inserted vide ... dated ..."


@dataclass
class ParsedDocument:
    doc_id: str
    version: str  # "current", "v2025-11-28", "asof2025-06-30"
    regulator: str
    doc_type: str
    title: str
    url: str
    topics: list[str]
    applies_to: list[str]
    doc_number: str | None = None  # "RBI/DOR/2025-26/171", "SS1/23", ...
    issue_date: date | None = None
    version_date: date | None = None  # "Updated as on ..." / edition date / as-at date
    effective_from: date | None = None  # when this version started to apply
    paragraphs: list[Paragraph] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.doc_id}@{self.version}"

    def to_json(self) -> dict[str, Any]:
        record = asdict(self)
        for name in ("issue_date", "version_date", "effective_from"):
            value = record[name]
            record[name] = value.isoformat() if value else None
        for para in record["paragraphs"]:
            para["section_path"] = list(para["section_path"])
            para["notes"] = list(para["notes"])
            value = para["effective_from"]
            para["effective_from"] = value.isoformat() if value else None
        return record

    @classmethod
    def from_json(cls, record: dict[str, Any]) -> ParsedDocument:
        def as_date(value: str | None) -> date | None:
            return date.fromisoformat(value) if value else None

        paragraphs = [
            Paragraph(
                ref=p["ref"],
                text=p["text"],
                section_path=tuple(p["section_path"]),
                kind=p["kind"],
                effective_from=as_date(p["effective_from"]),
                notes=tuple(p.get("notes", ())),
            )
            for p in record["paragraphs"]
        ]
        fields = {k: v for k, v in record.items() if k != "paragraphs"}
        for name in ("issue_date", "version_date", "effective_from"):
            fields[name] = as_date(fields[name])
        return cls(paragraphs=paragraphs, **fields)


def save_documents(documents: list[ParsedDocument], folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for doc in documents:
        path = folder / f"{doc.doc_id}__{doc.version}.json"
        path.write_text(json.dumps(doc.to_json(), ensure_ascii=False, indent=1), encoding="utf-8")


def load_documents(folder: Path) -> list[ParsedDocument]:
    return [
        ParsedDocument.from_json(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(folder.glob("*.json"))
    ]
