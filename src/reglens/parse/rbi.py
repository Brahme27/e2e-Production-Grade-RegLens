"""RBI master directions / directions published as HTML on rbi.org.in."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from reglens.parse.blocks import Block, assemble
from reglens.parse.html_text import node_text, parse_html
from reglens.parse.model import Paragraph
from reglens.parse.text import find_dates, first_date, one_line

DOC_NUMBER = re.compile(r"\bRBI/[A-Za-z]*/?\d{4}-\d{2}/\d+\b")
UPDATED_AS_ON = re.compile(r"\(\s*updated\s+as\s+on\s+([^)]+)\)", re.I)
CHAPTER = re.compile(r"^(chapter|part|annex(?:ure)?|appendix|schedule)\b", re.I)
SECTION = re.compile(r"^[A-Z]\.\s")  # "B. Key Responsibilities"
SUBSECTION = re.compile(r"^[A-Z]\.\d+\s")  # "D.1 Outsourcing Policy"
MAX_HEADING_CHARS = 160
NUMBERED = re.compile(r"^\d{1,3}\.\s")
FOOTNOTE_LINE = re.compile(
    r"^(inserted|amended|substituted|deleted|added|modified)\s+(vide|by|w\.e\.f)", re.I
)
AMENDMENT_NOTE = re.compile(r"\b(inserted|amended|substituted|deleted|added|modified)\b", re.I)


@dataclass(frozen=True)
class RbiHeader:
    title: str
    doc_number: str | None
    issue_date: date | None
    version_date: date | None


def _heading_level(text: str) -> int:
    if CHAPTER.match(text):
        return 1
    if SUBSECTION.match(text):
        return 3
    return 2


def _is_bold_heading(node: Any, text: str) -> bool:
    """Older directions mark headings with bold text instead of class="head"."""
    if len(text) > MAX_HEADING_CHARS or text.endswith((".", ";", ",", ":")):
        return False
    bold = "".join(b.text() for b in node.css("b, strong"))
    return bool(bold) and len(one_line(bold)) >= len(text) * 0.9


def _is_data_table(table: Any) -> bool:
    """RBI pages use tables for layout too; a data table has columns and no nested tables."""
    # css() also matches the node itself, so a table with a nested table has 2+ matches
    if len(table.css("table")) > 1 or table.css_first("p.head") is not None:
        return False
    rows = table.css("tr")
    return bool(rows) and max(len(row.css("td, th")) for row in rows) >= 2  # noqa: PLR2004


def _nested(node: Any, root: Any) -> bool:
    parent = node.parent
    while parent is not None and parent is not root:
        if parent.tag in ("p", "li") or (parent.tag == "table" and _is_data_table(parent)):
            return True
        parent = parent.parent
    return False


def _blocks(content_node: Any) -> list[Block]:
    blocks: list[Block] = []
    for node in content_node.css("p, table, li"):
        if (node.tag == "table" and not _is_data_table(node)) or _nested(node, content_node):
            continue
        notes = []
        for sup in node.css("sup"):  # footnote markers carry the amendment history
            note = sup.attributes.get("title")
            if note and AMENDMENT_NOTE.search(note):
                notes.append(one_line(note))
            sup.decompose()
        text = node_text(node)
        if not text or FOOTNOTE_LINE.match(text):  # footnote list entries at the end
            continue
        if node.tag == "table":
            if "Table of Contents" in text[:40]:
                continue
            blocks.append(Block("table", text, notes=tuple(notes)))
        elif (
            node.tag == "p"
            and not NUMBERED.match(text)  # "41. Accounts of PEPs" opens paragraph 41
            and ("head" in (node.attributes.get("class") or "") or _is_bold_heading(node, text))
        ):
            line = one_line(text)
            blocks.append(Block("heading", line, _heading_level(line), tuple(notes)))
        else:
            blocks.append(Block("text", text, notes=tuple(notes)))
    return blocks


def parse_rbi_html(content: bytes) -> tuple[RbiHeader, list[Paragraph]]:
    tree = parse_html(content)
    title_node = tree.css_first("td.tableheader b")
    raw_title = one_line(title_node.text()) if title_node else ""
    updated = UPDATED_AS_ON.search(raw_title)
    title = UPDATED_AS_ON.sub("", raw_title).strip(" ,")
    body = tree.css_first("tr.tablecontent2")
    if body is None:
        raise ValueError("no RBI content block (tr.tablecontent2) found")
    for link in body.css("a"):
        if one_line(link.text()) == "Previous Versions":
            link.decompose()
    head_text = node_text(body)[:600]
    number = DOC_NUMBER.search(head_text)
    dates = find_dates(head_text)
    header = RbiHeader(
        title=title,
        doc_number=number.group(0) if number else None,
        issue_date=dates[0] if dates else None,
        version_date=first_date(updated.group(1)) if updated else None,
    )
    paragraphs = [p for p in assemble(_blocks(body)) if not _is_boilerplate(p, header)]
    return header, with_amendment_dates(paragraphs)


def _is_boilerplate(para: Paragraph, header: RbiHeader) -> bool:
    """The letter head (number / date lines) and end-of-document footnote lists."""
    if header.doc_number and header.doc_number in para.text and len(para.text) < 400:  # noqa: PLR2004
        return True
    lines = para.text.splitlines()
    return sum(bool(FOOTNOTE_LINE.match(line)) for line in lines) > len(lines) / 2


def with_amendment_dates(paragraphs: list[Paragraph]) -> list[Paragraph]:
    """A paragraph's wording took effect at its latest dated amendment (if footnoted)."""
    updated = []
    for para in paragraphs:
        dates = [d for note in para.notes for d in find_dates(note)]
        updated.append(replace(para, effective_from=max(dates)) if dates else para)
    return updated
