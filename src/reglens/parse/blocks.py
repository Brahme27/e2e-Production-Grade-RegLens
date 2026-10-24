"""Turn a stream of headings / text blocks into numbered paragraphs.

Both RBI HTML pages and PDF documents (RBI, SEBI, PRA supervisory statements) arrive as a
flat sequence of blocks in reading order. Regulatory documents number their paragraphs
("12.", "2.1", "4.2.3"); everything until the next number belongs to the current paragraph:
sub-items "(i)", provisos "Provided that ...", tables.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from reglens.parse.model import Paragraph
from reglens.parse.text import clean

BlockKind = Literal["heading", "text", "table"]

# "12. A bank shall"  /  "2.1 This SS"  /  "4.2.3. The RE"   (number, then a capital or quote)
PARA_NUMBER = re.compile(r"^(\d{1,3}(?:\.\d{1,3}){0,3})\.?\s+(?=[A-Z(\"'‘“\[])")
# "Principle 1.2 Model inventory" / "Rule 4 ..." / "Standard 3.1": a labelled number
LABELLED_NUMBER = re.compile(
    r"^((?:Principle|Rule|Regulation|Article|Standard|Guideline)\s+\d{1,3}(?:\.\d{1,3}){0,2})\b"
)
ANNEX_HEADING = re.compile(r"^(annex(?:ure)?|appendix|schedule)\b[\s\-–—:]*([A-Z0-9IVX]*)", re.I)
MAX_HEADING_DEPTH = 4
SHORT_HEADING_CHARS = 48


@dataclass(frozen=True)
class Block:
    kind: BlockKind
    text: str
    level: int = 1  # headings only: 1 = chapter, 2 = section, 3 = sub-section
    notes: tuple[str, ...] = ()  # e.g. amendment footnotes found inside this block
    numbered: bool = True  # False: a leading number is not a paragraph number (a footnote)


@dataclass
class _Open:
    ref: str
    section_path: tuple[str, ...]
    lines: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _annex_prefix(section_path: tuple[str, ...]) -> str:
    """Paragraph numbers restart inside annexes: "Annex II, 3" keeps refs unique."""
    for heading in section_path:
        match = ANNEX_HEADING.match(heading)
        if match:
            label = match.group(1).title()
            return f"{label} {match.group(2)}".strip() + ", "
    return ""


def _unnumbered_ref(section_path: tuple[str, ...], n: int) -> str:
    if not section_path:
        return f"Preamble ¶{n}"
    heading = section_path[-1]
    short = heading if len(heading) <= SHORT_HEADING_CHARS else heading[:SHORT_HEADING_CHARS] + "…"
    return f"{short} ¶{n}"


def assemble(blocks: list[Block], min_chars: int = 25) -> list[Paragraph]:
    """Group blocks into numbered paragraphs, each with its heading path and notes."""
    stack: list[str] = []
    paragraphs: list[Paragraph] = []
    current: _Open | None = None
    unnumbered: dict[tuple[str, ...], int] = {}

    def close() -> None:
        nonlocal current
        if current is None:
            return
        text = clean("\n".join(current.lines))
        if len(text) >= min_chars and text.lower().strip(" .[]") != "deleted":
            paragraphs.append(
                Paragraph(
                    ref=current.ref,
                    text=text,
                    section_path=current.section_path,
                    notes=tuple(current.notes),
                )
            )
        current = None

    for block in blocks:
        if block.kind == "heading":
            close()
            depth = max(1, min(block.level, MAX_HEADING_DEPTH))
            del stack[depth - 1 :]
            stack.append(block.text.strip())
            continue
        match = None
        if block.kind == "text" and block.numbered:
            match = PARA_NUMBER.match(block.text) or LABELLED_NUMBER.match(block.text)
        if match:
            close()
            path = tuple(stack)
            current = _Open(ref=_annex_prefix(path) + match.group(1), section_path=path)
        elif current is None:  # unnumbered text: name it after its heading, "Annex II ¶3"
            unnumbered[tuple(stack)] = unnumbered.get(tuple(stack), 0) + 1
            current = _Open(
                ref=_unnumbered_ref(tuple(stack), unnumbered[tuple(stack)]),
                section_path=tuple(stack),
            )
        current.lines.append(block.text)
        current.notes.extend(block.notes)
    close()
    return paragraphs
