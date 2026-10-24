"""UK rulebooks: FCA Handbook sections and PRA Rulebook parts (both structured HTML).

Both publish every provision with its own reference and the date its current wording took
effect, so we get paragraph-level ``effective_from`` dates for free.
"""

from __future__ import annotations

import re
from datetime import date

from reglens.parse.html_text import node_text, parse_html
from reglens.parse.model import Paragraph, ParagraphKind
from reglens.parse.text import one_line, parse_day_first

FCA_KINDS: dict[str, ParagraphKind] = {
    "R": "rule",
    "G": "guidance",
    "E": "evidential",
    "D": "direction",
}
DELETED = re.compile(r"^\[?\s*deleted\.?\s*\]?$", re.I)


def parse_fca_section(content: bytes) -> list[Paragraph]:
    """One FCA Handbook section page ("PRIN 2A.1") -> its provisions."""
    tree = parse_html(content)
    container = tree.css_first("div.provisions-container")
    if container is None:
        return []
    paragraphs: list[Paragraph] = []
    section = ""
    subheading = ""
    for node in container.css("h2, h3, p-card"):
        if node.tag == "h2":
            section, subheading = one_line(node.text()), ""
            continue
        if node.tag == "h3":
            subheading = one_line(node.text())
            continue
        label = node.css_first("label span")
        body = node.css_first(".provision-meta")
        if label is None or body is None:
            continue
        header_spans = [one_line(s.text()) for s in node.css("div.header > span")]
        kind_letter = next((s for s in header_spans if s in FCA_KINDS), "")
        effective = next((d for s in header_spans if (d := parse_day_first(s))), None)
        text = node_text(body)
        if not text or DELETED.match(text):
            continue
        path = tuple(p for p in (section, subheading) if p)
        paragraphs.append(
            Paragraph(
                ref=one_line(label.text()) + kind_letter,  # "PRIN 2A.1.3G", as the FCA cites it
                text=text,
                section_path=path,
                kind=FCA_KINDS.get(kind_letter, "paragraph"),
                effective_from=effective,
            )
        )
    return paragraphs


def parse_pra_part(content: bytes) -> tuple[str, list[Paragraph]]:
    """A PRA Rulebook part page at a point in time -> (part title, rules)."""
    tree = parse_html(content)
    title_node = tree.css_first("h1")
    title = one_line(title_node.text()) if title_node else ""
    paragraphs: list[Paragraph] = []
    chapter = ""
    for node in tree.css("div.chapter-section, div.row-block"):
        if "chapter-section" in (node.attributes.get("class") or ""):
            number = node.css_first("span.chapter-number")
            heading = node.css_first("h3.chapter-heading")
            chapter = " ".join(
                one_line(n.text()) for n in (number, heading) if n is not None
            ).strip()
            continue
        number = node.css_first("span.rule-number")
        body = node.css_first("div.div-row__col-2")
        if number is None or body is None:
            continue
        text = node_text(body)
        if not text or DELETED.match(text):
            continue
        info = node.css_first("div.row-block__info li")
        effective: date | None = parse_day_first(one_line(info.text())) if info else None
        paragraphs.append(
            Paragraph(
                ref=one_line(number.text()),
                text=text,
                section_path=(chapter,) if chapter else (),
                kind="rule",
                effective_from=effective,
            )
        )
    return title, paragraphs
