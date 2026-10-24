"""Chunking: how documents are cut into the pieces we search over.

Two strategies, compared in the ablation (phase 08):

- ``fixed``: the naive baseline. Concatenate a document's text and cut every ~512 tokens,
  ignoring structure. A chunk can start mid-rule and end mid-rule.
- ``paragraph``: one chunk per numbered paragraph (the unit regulators cite). Very long
  paragraphs (the 22,000-character KYC definitions) are split at sub-item boundaries,
  each piece keeping the paragraph ref ("3", part 2 of 9).
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Literal

from reglens.parse.model import Paragraph, ParsedDocument
from reglens.temporal.validity import Validity, paragraph_interval

Strategy = Literal["fixed", "paragraph"]

FIXED_WORDS = 380  # ~512 tokens of English legal text
PARAGRAPH_MAX_WORDS = 300  # leaves room for the context header within bge-small's 512 tokens
SUB_ITEM = re.compile(r"^\(?([a-z]{1,2}|[ivxlc]{1,6}|\d{1,2})[).]\s", re.I)
OPEN_ENDED = date(9999, 12, 31)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_key: str
    doc_id: str
    version: str
    regulator: str
    doc_type: str
    title: str
    doc_number: str | None
    url: str
    ref: str  # citation reference of the (first) paragraph
    refs: tuple[str, ...]  # every paragraph this chunk overlaps (fixed chunks span several)
    part: int  # 1-based piece number for split paragraphs
    parts: int
    section_path: tuple[str, ...]
    text: str
    kind: str
    valid_from: date | None
    valid_to: date | None
    status: str
    topics: tuple[str, ...] = ()
    applies_to: tuple[str, ...] = ()
    context: str = ""  # header prepended before embedding (contextual retrieval)

    @property
    def citation(self) -> str:
        """How the answer cites this chunk: [SS1/23 §2.4]"""
        name = self.doc_number or self.title
        return f"[{name} §{self.ref}]"

    @property
    def embed_text(self) -> str:
        return f"{self.context}\n{self.text}" if self.context else self.text

    def payload(self) -> dict[str, Any]:
        record = asdict(self)
        for name in ("valid_from", "valid_to"):
            value = record[name]
            record[name] = value.isoformat() if value else None
        # integer day numbers make "as of" range filters cheap in the vector store
        record["valid_from_day"] = (self.valid_from or date.min).toordinal()
        record["valid_to_day"] = (self.valid_to or OPEN_ENDED).toordinal()
        record["section_path"] = list(self.section_path)
        record["refs"] = list(self.refs)
        record["topics"] = list(self.topics)
        record["applies_to"] = list(self.applies_to)
        return record

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> Chunk:
        fields = {k: v for k, v in payload.items() if k in cls.__dataclass_fields__}
        for name in ("valid_from", "valid_to"):
            fields[name] = date.fromisoformat(fields[name]) if fields.get(name) else None
        for name in ("section_path", "refs", "topics", "applies_to"):
            fields[name] = tuple(fields.get(name) or ())
        return cls(**fields)


def chunk_uuid(*parts: object) -> str:
    """Stable ids: re-indexing the same text yields the same point ids (idempotent upserts)."""
    digest = hashlib.sha1("|".join(map(str, parts)).encode("utf-8")).hexdigest()  # noqa: S324
    return str(uuid.UUID(digest[:32]))


def _words(text: str) -> int:
    return len(text.split())


def split_long(text: str, max_words: int = PARAGRAPH_MAX_WORDS) -> list[str]:
    """Split at line (sub-item) boundaries into pieces of at most ~max_words."""
    if _words(text) <= max_words:
        return [text]
    pieces: list[str] = []
    current: list[str] = []
    for line in text.split("\n"):
        if current and _words("\n".join([*current, line])) > max_words:
            pieces.append("\n".join(current))
            current = []
        if _words(line) > max_words:  # a single huge line: cut by words
            words = line.split()
            for start in range(0, len(words), max_words):
                pieces.append(" ".join(words[start : start + max_words]))
            continue
        current.append(line)
    if current:
        pieces.append("\n".join(current))
    return pieces


@dataclass
class _Base:
    doc: ParsedDocument
    validity: Validity

    def common(self) -> dict[str, Any]:
        return {
            "doc_key": self.doc.key,
            "doc_id": self.doc.doc_id,
            "version": self.doc.version,
            "regulator": self.doc.regulator,
            "doc_type": self.doc.doc_type,
            "title": self.doc.title,
            "doc_number": self.doc.doc_number,
            "url": self.doc.url,
            "status": self.validity.status,
            "topics": tuple(self.doc.topics),
            "applies_to": tuple(self.doc.applies_to),
        }


def paragraph_chunks(doc: ParsedDocument, validity: Validity, earliest: bool) -> list[Chunk]:
    base = _Base(doc, validity)
    chunks: list[Chunk] = []
    for order, para in enumerate(doc.paragraphs):
        start, end = paragraph_interval(doc, para, validity, earliest)
        pieces = split_long(para.text)
        for index, piece in enumerate(pieces, start=1):
            chunks.append(
                Chunk(
                    chunk_id=chunk_uuid("paragraph", doc.key, order, para.ref, index),
                    ref=para.ref,
                    refs=(para.ref,),
                    part=index,
                    parts=len(pieces),
                    section_path=para.section_path,
                    text=piece,
                    kind=para.kind,
                    valid_from=start,
                    valid_to=end,
                    **base.common(),
                )
            )
    return chunks


def fixed_chunks(doc: ParsedDocument, validity: Validity, earliest: bool) -> list[Chunk]:
    """The naive baseline: ~512-token windows over the whole document, structure ignored."""
    base = _Base(doc, validity)
    tokens: list[tuple[str, Paragraph]] = [
        (word, para) for para in doc.paragraphs for word in para.text.split()
    ]
    chunks: list[Chunk] = []
    for index, start in enumerate(range(0, len(tokens), FIXED_WORDS), start=1):
        window = tokens[start : start + FIXED_WORDS]
        refs = tuple(dict.fromkeys(para.ref for _, para in window))
        first = window[0][1]
        chunks.append(
            Chunk(
                chunk_id=chunk_uuid("fixed", doc.key, index),
                ref=refs[0],
                refs=refs,
                part=index,
                parts=0,
                section_path=first.section_path,
                text=" ".join(word for word, _ in window),
                kind="paragraph",
                valid_from=validity.valid_from,
                valid_to=validity.valid_to,
                **base.common(),
            )
        )
    return chunks


def chunk_corpus(
    documents: list[ParsedDocument], validity: dict[str, Validity], strategy: Strategy
) -> list[Chunk]:
    earliest_version: dict[str, ParsedDocument] = {}
    for doc in documents:
        start = validity[doc.key].valid_from or date.min
        best = earliest_version.get(doc.doc_id)
        if best is None or start < (validity[best.key].valid_from or date.min):
            earliest_version[doc.doc_id] = doc
    make = paragraph_chunks if strategy == "paragraph" else fixed_chunks
    chunks: list[Chunk] = []
    for doc in documents:
        earliest = earliest_version[doc.doc_id].key == doc.key
        chunks.extend(make(doc, validity[doc.key], earliest))
    return chunks
