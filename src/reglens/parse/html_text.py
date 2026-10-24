"""HTML node -> readable text that keeps block boundaries (paragraphs, list items, rows)."""

from __future__ import annotations

import re
from typing import Any

from selectolax.lexbor import LexborHTMLParser

from reglens.parse.text import clean, one_line

_BLOCK = re.compile(r"<(p|div|li|tr|br|h[1-6]|ol|ul|table|caption|figure)\b", re.I)
_LONE_MARKER = re.compile(r"^\(?([0-9]{1,3}|[a-z]{1,2}|[ivxlc]{1,6})[).]$", re.I)


def _cell_text(cell: Any) -> str:
    """Cell text where <br> and inner paragraphs become spaces ("171<br>DOR" -> "171 DOR")."""
    html = _BLOCK.sub(lambda m: " <" + m.group(1), cell.html or "")
    parsed = LexborHTMLParser(f"<html><body>{html}</body></html>")
    return parsed.body.text(separator="") if parsed.body is not None else ""


def _flatten_tables(tree: LexborHTMLParser) -> None:
    """Replace each table with plain text: one line per row, cells joined by ' | '.

    (Inserting separator text between <td> tags does not work: HTML parsers move stray
    text out of tables, so the separators silently vanish.)
    """
    for table in reversed(tree.css("table")):  # innermost first
        rows = []
        for row in table.css("tr"):
            cells = [one_line(_cell_text(cell)) for cell in row.css("td, th")]
            if any(cells):
                rows.append(" | ".join(c for c in cells if c))
        table.replace_with("\n" + "\n".join(rows) + "\n")


def _join_lone_markers(lines: list[str]) -> list[str]:
    """'(1)' on its own line belongs to the line after it: '(1) the rules apply ...'."""
    joined: list[str] = []
    pending = ""
    for line in lines:
        if _LONE_MARKER.match(line):
            pending = f"{pending} {line}".strip()
            continue
        joined.append(f"{pending} {line}".strip() if pending else line)
        pending = ""
    if pending:
        joined.append(pending)
    return joined


def node_text(node: Any) -> str:
    """Text of an HTML node with a newline at every block element.

    selectolax's ``text()`` either glues blocks together ("table below:SubjectApplicable")
    or splits at every inline link ("the\\nConsumer Duty\\napplies"); inserting newlines only
    at block tags gives what a human reader sees.
    """
    tree = LexborHTMLParser(f"<html><body>{node.html or ''}</body></html>")
    _flatten_tables(tree)
    body = tree.body
    html = body.html if body is not None else ""
    html = _BLOCK.sub(lambda m: "\n<" + m.group(1), html or "")
    parsed = LexborHTMLParser(f"<html><body>{html}</body></html>")
    text = parsed.body.text(separator="") if parsed.body is not None else ""
    lines = [line.strip() for line in clean(text).split("\n")]
    return "\n".join(_join_lone_markers([line for line in lines if line]))


def parse_html(content: bytes) -> LexborHTMLParser:
    tree = LexborHTMLParser(content)
    for junk in tree.css("script, style, noscript"):
        junk.decompose()
    return tree
