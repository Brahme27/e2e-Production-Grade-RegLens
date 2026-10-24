"""Small text helpers shared by every parser: whitespace, dates, numbering patterns."""

from __future__ import annotations

import re
from datetime import date, datetime

MONTHS = {
    m: i + 1
    for i, names in enumerate(
        [
            ("january", "jan"),
            ("february", "feb"),
            ("march", "mar"),
            ("april", "apr"),
            ("may",),
            ("june", "jun"),
            ("july", "jul"),
            ("august", "aug"),
            ("september", "sep", "sept"),
            ("october", "oct"),
            ("november", "nov"),
            ("december", "dec"),
        ]
    )
    for m in names
}
_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
# "November 28, 2025" / "Nov 28 2025"
_MDY = re.compile(rf"\b({_MONTH})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", re.I)
# "28 November 2025" / "28th Nov, 2025"
_DMY = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH})\.?,?\s+(\d{{4}})\b", re.I)
# "28/11/2025", "28-11-2025", "28.11.2025"
_NUMERIC = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")

_SPACES = re.compile(r"[ \t\u00a0\u2002\u2003\u2009\u200b\ufeff]+")
_BLANK_LINES = re.compile(r"\n\s*\n+")


def clean(text: str) -> str:
    """Collapse runs of spaces (incl. non-breaking) and blank lines; trim each line."""
    text = text.replace("\r", "")
    lines = [_SPACES.sub(" ", line).strip() for line in text.split("\n")]
    return _BLANK_LINES.sub("\n", "\n".join(lines)).strip()


def one_line(text: str) -> str:
    return _SPACES.sub(" ", text.replace("\n", " ")).strip()


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def find_dates(text: str) -> list[date]:
    """Every date written in a common regulatory style, in order of appearance."""
    found: list[tuple[int, date]] = []
    for m in _MDY.finditer(text):
        d = _safe_date(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2)))
        if d:
            found.append((m.start(), d))
    for m in _DMY.finditer(text):
        d = _safe_date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
        if d:
            found.append((m.start(), d))
    for m in _NUMERIC.finditer(text):  # UK / India write day first
        d = _safe_date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if d:
            found.append((m.start(), d))
    return [d for _, d in sorted(found, key=lambda item: item[0])]


def first_date(text: str) -> date | None:
    dates = find_dates(text)
    return dates[0] if dates else None


def parse_day_first(text: str) -> date | None:
    """Parse '26/06/2026' or '30-06-2025' exactly (FCA / PRA style)."""
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None
