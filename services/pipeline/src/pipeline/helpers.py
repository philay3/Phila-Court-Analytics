"""Small, deterministic parsing helpers, unit tested before any PDF work."""

from __future__ import annotations

import re
from datetime import datetime

GRADES = {"F1", "F2", "F3", "F", "M1", "M2", "M3", "M", "S", "H1", "H2"}


class ParseError(Exception):
    """Raised when a docket cannot be parsed. Messages name the section or
    field only; they never quote docket text."""


def parse_date(text: str | None) -> str | None:
    if not text:
        return None
    text = text.strip()
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


_UNIT_DAYS = {"year": 360, "years": 360, "month": 30, "months": 30, "day": 1, "days": 1}


def to_days(length_text: str | None) -> int | None:
    """Convert '11 1/2 Months', '1 Year 6 Months', '90 Days' to days.

    Rule: year = 360, month = 30, half = 0.5 of the unit. Returns None when
    nothing parses (for example 'Life'); the caller keeps raw_text so
    nothing is lost.
    """
    if not length_text:
        return None
    length_text = length_text.replace("½", " 1/2")
    total = 0.0
    found = False
    pattern = re.compile(
        r"(\d+(?:\.\d+)?)(\s*1/2)?\s+(years?|months?|days?)", re.IGNORECASE
    )
    for m in pattern.finditer(length_text):
        qty = float(m.group(1))
        if m.group(2):
            qty += 0.5
        total += qty * _UNIT_DAYS[m.group(3).lower()]
        found = True
    return int(round(total)) if found else None
