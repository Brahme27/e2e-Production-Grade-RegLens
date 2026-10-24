"""PDF documents (SEBI circulars, PRA supervisory statements, RBI PDFs) -> paragraphs.

PDF text arrives as lines on pages. We remove running headers/footers (lines repeated on
many pages, page numbers), glue wrapped lines back together, and recognise numbered
paragraphs ("1.1", "4.2.3") and short numbered headings ("2 Model tiering").
"""

from __future__ import annotations

import re
from collections import Counter

import pypdfium2 as pdfium

from reglens.parse.blocks import LABELLED_NUMBER, PARA_NUMBER, Block, assemble
from reglens.parse.model import Paragraph
from reglens.parse.text import one_line

PAGE_NUMBER = re.compile(r"^(page\s+)?\d{1,4}(\s+(of|/)\s+\d{1,4})?$", re.I)
ITEM_START = re.compile(
    r"^(\(?[a-z]{1,2}\)|\(?[ivxlc]{1,6}\)|[ivxlc]{1,6}\.|[a-z]\.|\d{1,2}\)|[•▪●◦\-–]|\(\d{1,2}\))\s",
    re.I,
)
NUMBERED_HEADING = re.compile(r"^(\d{1,2}(?:\.\d{1,2})?)\.?\s+([A-Z][^.;:]{2,90})$")
WORD_HEADING = re.compile(
    r"^(annex(?:ure)?|appendix|schedule|part|chapter|section)\b.{0,80}$", re.I
)
SENTENCE_END = (".", ":", ";", "?", "!")
MAX_HEADING_WORDS = 14
MAX_PLAIN_HEADING_WORDS = 10
PLAIN_HEADING_LEVEL = 2
MAX_NUMBERED_HEADING_CHARS = 70
DOTTED_SHARE = 0.4
REPEAT_SHARE = 0.3  # a line on >=30% of pages is a running header/footer
MIN_PAGES_FOR_REPEATS = 3


def pdf_lines(content: bytes) -> list[list[str]]:
    """Text lines per page."""
    pdf = pdfium.PdfDocument(content)
    pages = []
    for index in range(len(pdf)):
        text = pdf[index].get_textpage().get_text_range()
        pages.append([one_line(line) for line in text.replace("\r", "\n").split("\n")])
    pdf.close()
    return pages


def _running_lines(pages: list[list[str]]) -> set[str]:
    if len(pages) < MIN_PAGES_FOR_REPEATS:
        return set()
    counts: Counter[str] = Counter()
    for lines in pages:
        counts.update({re.sub(r"\d+", "#", line) for line in lines if line})
    threshold = max(2, REPEAT_SHARE * len(pages))  # must repeat on at least two pages
    return {line for line, n in counts.items() if n >= threshold}


def _is_heading(line: str, following: str) -> bool:
    if line.endswith(SENTENCE_END) or len(line.split()) > MAX_HEADING_WORDS:
        return False
    if WORD_HEADING.match(line):
        return True
    # "2 Model tiering" is a heading; "1.7 Self-assessments should be updated at least
    # annually thereafter, and any remediation" is the wrapped first line of a paragraph
    return bool(
        NUMBERED_HEADING.match(line)
        and len(line) <= MAX_NUMBERED_HEADING_CHARS
        and "," not in line
        and not following[:1].islower()
    )


def _dotted_style(lines: list[str]) -> bool:
    """True when paragraphs are numbered "2.1", "2.2": then a bare "4 Model..." (no dot after
    the number) is a footnote. "4. The..." with a dot is still a paragraph (SEBI style)."""
    numbers = [m.group(1) for line in lines if (m := PARA_NUMBER.match(line))]
    dotted = sum("." in n for n in numbers)
    return bool(numbers) and dotted >= DOTTED_SHARE * len(numbers)


def _is_plain_heading(line: str, following: str, buffer: list[str]) -> bool:
    """An unnumbered heading: a short title line directly followed by a numbered paragraph."""
    previous_ended = not buffer or buffer[-1].endswith(SENTENCE_END)
    return (
        previous_ended
        and line[:1].isupper()
        and not line.endswith((*SENTENCE_END, ","))
        and len(line.split()) <= MAX_PLAIN_HEADING_WORDS
        and not ITEM_START.match(line)
        and bool(PARA_NUMBER.match(following))
    )


def _heading_level(line: str) -> int:
    match = NUMBERED_HEADING.match(line)
    if match:
        return 1 + match.group(1).count(".")
    return 1


def pdf_blocks(pages: list[list[str]]) -> list[Block]:
    running = _running_lines(pages)
    blocks: list[Block] = []
    buffer: list[str] = []

    footnote = False

    def flush() -> None:
        nonlocal footnote
        if buffer and not footnote:  # footnotes are dropped: they interrupt the main text
            blocks.append(Block("text", " ".join(buffer)))
        buffer.clear()
        footnote = False

    kept = [
        line
        for lines in pages
        for line in lines
        if line and not PAGE_NUMBER.match(line) and re.sub(r"\d+", "#", line) not in running
    ]
    dotted = _dotted_style(kept)
    for index, line in enumerate(kept):
        following = kept[index + 1] if index + 1 < len(kept) else ""
        number = PARA_NUMBER.match(line)
        is_footnote = bool(
            number and dotted and "." not in number.group(1) and line[len(number.group(1))] == " "
        )
        if _is_heading(line, following):
            flush()
            blocks.append(Block("heading", line, _heading_level(line)))
        elif _is_plain_heading(line, following, buffer):
            flush()  # unnumbered headings sit under the numbered section they appear in
            blocks.append(Block("heading", line, PLAIN_HEADING_LEVEL))
        elif number or LABELLED_NUMBER.match(line) or ITEM_START.match(line):
            flush()
            footnote = is_footnote  # "4 Model use is defined ..." is footnote 4, not para 4
            buffer.append(line)
        elif buffer and buffer[-1].endswith(SENTENCE_END) and line[:1].isupper():
            flush()  # a new sentence-paragraph that is not numbered
            buffer.append(line)
        else:
            buffer.append(line)  # a wrapped line continues the current block
    flush()
    return blocks


def parse_pdf(content: bytes) -> tuple[str, list[Paragraph]]:
    """Return (first-page text, paragraphs)."""
    pages = pdf_lines(content)
    first_page = "\n".join(pages[0]) if pages else ""
    return first_page, assemble(pdf_blocks(pages))
