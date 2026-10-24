"""Understanding the question: which date, which regulators, which kind of question.

Cheap, deterministic signals extracted with rules (no LLM): an explicit "as of" date,
regulator names, firm types. The router (``router.py``) then decides the query type.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from reglens.parse.text import first_date

REGULATOR_PATTERNS = {
    "RBI": re.compile(r"\b(rbi|reserve bank)\b", re.I),
    "SEBI": re.compile(r"\b(sebi|securities and exchange board)\b", re.I),
    "FCA": re.compile(r"\b(fca|financial conduct authority|consumer duty|handbook)\b", re.I),
    "PRA": re.compile(r"\b(pra|prudential regulation authority|bank of england|rulebook)\b", re.I),
}
APPLIES_PATTERNS = {
    "nbfcs": re.compile(r"\b(nbfcs?|non-banking financial)\b", re.I),
    "commercial_banks": re.compile(r"\b(commercial banks?|scheduled banks?)\b", re.I),
}
# "as of 1 March 2024", "as at 30/06/2025", "on 1 Jan 2024", "in force in March 2023"
AS_OF = re.compile(
    r"\b(?:as\s+(?:of|at|on)|on|in\s+force\s+(?:on|in)|applicable\s+on|back\s+in|during)\s+"
    r"((?:\d{1,2}(?:st|nd|rd|th)?\s+)?[A-Za-z]+\.?,?\s+\d{4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4}"
    r"|\d{1,2}[/.-]\d{1,2}[/.-]\d{4}|\d{4}-\d{2}-\d{2})",
    re.I,
)
MONTH_YEAR = re.compile(r"^([A-Za-z]+)\.?,?\s+(\d{4})$")
IN_MONTH_YEAR = re.compile(
    r"\b(?:in|during|by|from|since|until)\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may"
    r"|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?,?"
    r"\s+((?:19|20)\d{2})\b",
    re.I,
)
YEAR_ONLY = re.compile(r"\b(?:in|during|as of|back in)\s+((?:19|20)\d{2})\b(?!-)", re.I)


@dataclass(frozen=True)
class QuerySignals:
    text: str
    as_of: date | None = None  # explicit date in the question
    regulators: tuple[str, ...] = ()
    applies_to: tuple[str, ...] = ()
    signals: dict[str, bool] = field(default_factory=dict)


def _parse_as_of(text: str) -> date | None:
    match = AS_OF.search(text)
    if match:
        value = match.group(1).strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return date.fromisoformat(value)
        parsed = first_date(value)
        if parsed:
            return parsed
        month_year = MONTH_YEAR.match(value)
        if month_year:  # "March 2024" -> the middle of that month
            parsed = first_date(f"15 {month_year.group(1)} {month_year.group(2)}")
            if parsed:
                return parsed
    month = IN_MONTH_YEAR.search(text)
    if month:  # "in March 2023" -> the middle of that month
        return first_date(f"15 {month.group(1)} {month.group(2)}")
    year = YEAR_ONLY.search(text)
    if year:  # "in 2023" -> mid-year
        return date(int(year.group(1)), 7, 1)
    return None


def analyse(text: str) -> QuerySignals:
    regulators = tuple(name for name, pattern in REGULATOR_PATTERNS.items() if pattern.search(text))
    applies = tuple(name for name, pattern in APPLIES_PATTERNS.items() if pattern.search(text))
    as_of = _parse_as_of(text)
    lowered = text.lower()
    signals = {
        "has_date": as_of is not None,
        "compare_words": bool(
            re.search(r"\b(compare|comparison|differ|difference|versus|vs\.?|both)\b", lowered)
        ),
        "multi_regulator": len(regulators) >= 2,  # noqa: PLR2004
        "change_words": bool(
            re.search(
                r"\b(changed?|changes|amend\w*|new|updated?|replaced?|superseded?|repeal\w*|before|previous|old)\b",
                lowered,
            )
        ),
        "theme_words": bool(
            re.search(
                r"\b(themes?|overview|summari[sz]e|main (points|requirements)|broadly|landscape|key (areas|requirements))\b",
                lowered,
            )
        ),
    }
    return QuerySignals(text, as_of, regulators, applies, signals)
