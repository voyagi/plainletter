"""Reading Dutch dates and amounts, deterministically.

This module never asks a model anything. It is the half of the verifier that can be trusted
because it is only string handling, and every function here refuses rather than guesses.

The two traps it exists for:

* 15-09-2026 is 15 September in the Netherlands and an invalid month elsewhere, and both readings
  parse silently in most date libraries.
* 1.234,50 is one thousand two hundred and thirty four euros fifty, while 1,234.50 is the same
  number written the other way round and 174.00 is neither. A dot group that is not exactly three
  digits is not a Dutch thousands separator, so it is rejected instead of read as one.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

MONTHS_NL: dict[str, int] = {
    "januari": 1,
    "februari": 2,
    "maart": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "augustus": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "december": 12,
}

# The abbreviations Dutch letters actually print, including the four-letter "sept".
MONTH_ABBREVIATIONS_NL: dict[str, int] = {
    "jan": 1,
    "feb": 2,
    "mrt": 3,
    "apr": 4,
    "mei": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "okt": 10,
    "nov": 11,
    "dec": 12,
}

_WORD_DATE = re.compile(
    r"\b(?P<day>\d{1,2})\s+(?P<month>[a-z]+)\.?\s+(?P<year>\d{4})\b",
    re.IGNORECASE,
)
_NUMERIC_DATE = re.compile(r"\b(?P<day>\d{1,2})[-/.](?P<month>\d{1,2})[-/.](?P<year>\d{4})\b")
# Deliberately permissive about the digits it captures. A narrow pattern would match the "174" of
# "174.00" and quietly report a hundred and seventy four euro; capturing the whole run lets the
# separator check below refuse it instead.
_AMOUNT = re.compile(r"(?:eur|euro|€)?\s*(?P<number>\d[\d.]*(?:,\d{1,2})?)", re.IGNORECASE)
_DOT_GROUPS = re.compile(r"^\d{1,3}(?:\.\d{3})+$")


def normalise(text: str) -> str:
    """Fold a passage to the form the grounding check compares on.

    Photographed text arrives with soft hyphens, non-breaking spaces and line breaks in places the
    model does not reproduce, so a raw equality test fails on passages that are plainly the same.
    """
    folded = unicodedata.normalize("NFKC", text)
    folded = folded.replace("\u00ad", "").replace("\u2019", "'")
    return re.sub(r"\s+", " ", folded).strip().casefold()


def passage_is_in(letter_text: str, passage: str) -> bool:
    """True when the passage really stands in the letter, whitespace and hyphens aside."""
    needle = normalise(passage)
    return bool(needle) and needle in normalise(letter_text)


def parse_date(text: str) -> date | None:
    """The first Dutch date in the text, or None. Never raises on nonsense input."""
    word = _WORD_DATE.search(text)
    if word:
        month = _month_number(word.group("month"))
        if month is not None:
            return _safe_date(int(word.group("year")), month, int(word.group("day")))

    numeric = _NUMERIC_DATE.search(text)
    if numeric:
        return _safe_date(
            int(numeric.group("year")), int(numeric.group("month")), int(numeric.group("day"))
        )
    return None


def parse_amount_cents(text: str) -> int | None:
    """The first euro amount in the text as integer cents, or None when it is not readable."""
    match = _AMOUNT.search(text)
    if not match:
        return None

    number = match.group("number").rstrip(".,")
    whole, _, fraction = number.partition(",")

    if "." in whole and not _DOT_GROUPS.match(whole):
        # Not a Dutch thousands grouping, so the writer meant something this cannot resolve.
        return None
    whole = whole.replace(".", "")
    if not whole.isdigit():
        return None

    cents = int(whole) * 100
    if fraction:
        cents += int(fraction.ljust(2, "0"))
    return cents


def format_date(value: date) -> str:
    """15 september 2026, the way the letter and the desk card write it."""
    month_name = next(name for name, number in MONTHS_NL.items() if number == value.month)
    return f"{value.day} {month_name} {value.year}"


def format_amount(cents: int) -> str:
    """EUR 1.234,50, with the Dutch separators the visitor will see on the payment page."""
    whole, remainder = divmod(abs(cents), 100)
    grouped = f"{whole:,}".replace(",", ".")
    sign = "-" if cents < 0 else ""
    return f"{sign}EUR {grouped},{remainder:02d}"


def _month_number(word: str) -> int | None:
    key = word.casefold()
    if key in MONTHS_NL:
        return MONTHS_NL[key]
    return MONTH_ABBREVIATIONS_NL.get(key)


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None
