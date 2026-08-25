"""The Netherlands: the only country Plainletter reads today, and all of what makes it Dutch.

Dates, money, the citizen service number, the days the post does not move, every word the desk card
prints, and the body a volunteer sends the visitor to when the desk cannot finish. A second country
is a copy of this file with its own answers, plus its own knowledge base and samples.

Two traps this file exists for:

* 15-09-2026 is 15 September in the Netherlands and an invalid month elsewhere, and both readings
  parse silently in most date libraries.
* 1.234,50 is one thousand two hundred and thirty four euros fifty, while 1,234.50 is the same
  number written the other way round and 174.00 is neither. A dot group that is not exactly three
  digits is not a Dutch thousands separator, so it is rejected instead of read as one.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from dateutil.easter import EASTER_WESTERN, easter

from . import DeskWords

MONTHS: dict[str, int] = {
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
MONTH_ABBREVIATIONS: dict[str, int] = {
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

BSN_MASK = "BSN verborgen"

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

_BSN_LABELLED = re.compile(
    r"\b(?P<label>bsn|burgerservicenummer|sofinummer)\b(?P<gap>[\s:.]*)(?P<digits>\d[\d\s.-]{7,13}\d)",
    re.IGNORECASE,
)
_NINE_DIGITS = re.compile(r"(?<!\d)(\d{9})(?!\d)")

WORDS = DeskWords(
    language="nl",
    card_description=(
        "De baliekaart bij deze brief: wat het is, voor wanneer, wat er gebeurt als u niets doet, "
        "en wat u nu doet, in twee talen op een vel."
    ),
    question_what="Wat is dit?",
    question_if_nothing="Wat gebeurt er als u niets doet?",
    question_by_when="Voor wanneer?",
    actions_heading="Wat u nu doet",
    keys_heading="De markeringen op de brief",
    notes_heading="Aantekeningen aan de balie",
    handoff_heading="Als het ingewikkeld wordt.",
    reference="Kenmerk {reference}",
    reference_missing="Geen kenmerk in de brief",
    deadline_lead="Uiterste dag: {date}",
    deadline_missing="Deze brief noemt geen uiterste datum.",
    days_left="Nog {days} dagen.",
    days_overdue="{days} dagen te laat.",
    post_by=" Post uw brief uiterlijk {date}.",
    urgency_overdue="Te laat",
    urgency_due_soon="Bijna te laat",
    urgency_ample="Nog tijd",
    urgency_unknown="Geen datum",
    case_note="Zaaknummer {case_id}.",
    case_note_detail=(
        "Neem deze kaart mee als u terugkomt, dan gaat de balie verder waar u gebleven was."
    ),
    disclaimer=("Plainletter legt brieven uit en geeft geen juridisch advies. Gemaakt op {date}."),
    ai_disclosure=(
        "Deze tekst is gemaakt door een AI-systeem. Elke datum en elk bedrag is gecontroleerd "
        "tegen uw eigen brief. Laat een medewerker meekijken voordat u iets verstuurt."
    ),
    reminder_deadline="Uiterste dag: {date}.",
    reminder_alarm="nog {days} dagen",
    unknown_letter_type="Onbekende brief",
    unknown_sender_name="Onbekende afzender",
    referral_last_resort_name="Het Juridisch Loket",
    referral_last_resort="Het Juridisch Loket, 0800 8020",
    referral_not_grounded=(
        "Het Juridisch Loket, 0800 8020. Deze brief kon niet volledig gecontroleerd worden."
    ),
    referral_unknown_sender=(
        "Het Juridisch Loket, 0800 8020. De afzender van deze brief staat niet in de kennisbank."
    ),
)


class DutchLocale:
    """The Netherlands as the deterministic steps see it."""

    code = "nl"
    words = WORDS
    reminder_region = "NL"

    def month_words(self) -> dict[str, int]:
        return {**MONTHS, **MONTH_ABBREVIATIONS}

    def parse_date(self, text: str) -> date | None:
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

    def parse_amount_cents(self, text: str) -> int | None:
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

    def format_date(self, value: date) -> str:
        """15 september 2026, the way the letter and the desk card write it."""
        month_name = next(name for name, number in MONTHS.items() if number == value.month)
        return f"{value.day} {month_name} {value.year}"

    def format_amount(self, cents: int) -> str:
        """EUR 1.234,50, with the separators the visitor will see on the payment page."""
        whole, remainder = divmod(abs(cents), 100)
        grouped = f"{whole:,}".replace(",", ".")
        sign = "-" if cents < 0 else ""
        return f"{sign}EUR {grouped},{remainder:02d}"

    def mask_identifiers(self, text: str) -> str:
        """Mask the citizen service number, labelled or bare.

        The bank account number is masked in `redact.py` instead: an IBAN is the same object in
        every country that uses one, so masking it is not a fact about the Netherlands.
        """
        without_labelled = _BSN_LABELLED.sub(_mask_labelled_bsn, text)
        return _NINE_DIGITS.sub(_mask_bare_bsn, without_labelled)

    def public_holidays(self, year: int) -> frozenset[date]:
        """The national public holidays that close Dutch offices and post in a given year.

        Easter comes from python-dateutil rather than a hand-rolled computus: the holidays that
        shift each year all hang off it, and a calendar rule is not the place to be clever.
        """
        easter_sunday = easter(year, method=EASTER_WESTERN)
        holidays = {
            date(year, 1, 1),
            easter_sunday + timedelta(days=1),  # Tweede Paasdag
            easter_sunday + timedelta(days=39),  # Hemelvaartsdag
            easter_sunday + timedelta(days=50),  # Tweede Pinksterdag
            date(year, 12, 25),
            date(year, 12, 26),
            _kings_day(year),
        }
        if year % 5 == 0:
            # Bevrijdingsdag is a national day off in the lustrum years and an ordinary working day
            # in between.
            holidays.add(date(year, 5, 5))
        return frozenset(holidays)


NL = DutchLocale()


def looks_like_bsn(digits: str) -> bool:
    """The elfproef the Dutch government uses to validate a citizen service number.

    Nine digits weighted 9 down to 2, the last one subtracted, and the total divisible by eleven.
    A random nine-digit reference passes about one time in eleven, which is why a false mask is
    accepted here and a missed one is not.
    """
    bare = re.sub(r"\D", "", digits)
    if len(bare) != 9:
        return False
    weights = [9, 8, 7, 6, 5, 4, 3, 2, -1]
    total = sum(int(digit) * weight for digit, weight in zip(bare, weights, strict=True))
    return total % 11 == 0


def _mask_labelled_bsn(match: re.Match[str]) -> str:
    # A number sitting behind the words "BSN" or "burgerservicenummer" is masked whatever it is:
    # the label is stronger evidence than any checksum, and a mislabelled number is still personal.
    return f"{match.group('label')}{match.group('gap')}{BSN_MASK}"


def _mask_bare_bsn(match: re.Match[str]) -> str:
    digits = match.group(1)
    return BSN_MASK if looks_like_bsn(digits) else digits


def _month_number(word: str) -> int | None:
    key = word.casefold()
    if key in MONTHS:
        return MONTHS[key]
    return MONTH_ABBREVIATIONS.get(key)


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _kings_day(year: int) -> date:
    """27 April, or the Saturday before it when that falls on a Sunday."""
    day = date(year, 4, 27)
    return day - timedelta(days=1) if day.weekday() == 6 else day
