"""The check that decides whether a reading is allowed to reach a person.

It reads nothing and infers nothing. For every fact the reading stage produced it asks two
questions with plain string handling:

1. Does the passage it cited really stand in the letter?
2. Does the value it claims actually follow from that passage?

Both have to hold. A deadline whose passage says 4 August fails, and so does a passage the letter
never contained, and the failure is visible rather than smoothed over. This is the module the whole
trust claim rests on, which is exactly why no model is involved in it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date

from .locales import active
from .schemas import (
    GroundedFact,
    LetterDate,
    LetterFacts,
    Money,
    NamedValue,
    SourceSpan,
    VerificationIssue,
    VerificationResult,
)
from .text import normalise, passage_is_in

_NOT_IN_LETTER = "the cited passage does not appear in the letter"
_VALUE_NOT_IN_PASSAGE = "the passage does not carry the value that was claimed"

# The month names a visitor-language sentence writes a date with. The guard reads the model's
# prose in every language it answers in, and a wrong date is no less wrong for being written in
# Ukrainian: on the first live run the plan wrote "15 вересня 2026" where the letter said
# "15 september 2026", and a Latin-only pattern would have let a wrong one through unread. The
# genitive forms are how a date is written in Ukrainian and Polish; the nominatives stay because a
# model writes either. Russian is here to be READ, never written: the same live run saw a draft
# drift into Russian halfway through a Ukrainian letter, and a date in it has to be checked too.
VISITOR_MONTHS: dict[str, int] = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "січня": 1,
    "лютого": 2,
    "березня": 3,
    "квітня": 4,
    "травня": 5,
    "червня": 6,
    "липня": 7,
    "серпня": 8,
    "вересня": 9,
    "жовтня": 10,
    "листопада": 11,
    "грудня": 12,
    "січень": 1,
    "лютий": 2,
    "березень": 3,
    "квітень": 4,
    "травень": 5,
    "червень": 6,
    "липень": 7,
    "серпень": 8,
    "вересень": 9,
    "жовтень": 10,
    "листопад": 11,
    "грудень": 12,
    "stycznia": 1,
    "lutego": 2,
    "marca": 3,
    "kwietnia": 4,
    "maja": 5,
    "czerwca": 6,
    "lipca": 7,
    "sierpnia": 8,
    "września": 9,
    "października": 10,
    "listopada": 11,
    "grudnia": 12,
    "styczeń": 1,
    "luty": 2,
    "marzec": 3,
    "kwiecień": 4,
    "maj": 5,
    "czerwiec": 6,
    "lipiec": 7,
    "sierpień": 8,
    "wrzesień": 9,
    "październik": 10,
    "listopad": 11,
    "grudzień": 12,
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
    "ocak": 1,
    "şubat": 2,
    "mart": 3,
    "nisan": 4,
    "mayıs": 5,
    "haziran": 6,
    "temmuz": 7,
    "ağustos": 8,
    "eylül": 9,
    "ekim": 10,
    "kasım": 11,
    "aralık": 12,
}

# Merged once per locale rather than per match: the guard runs this over every sentence a model
# writes, and the table is a hundred entries long.
_months_any: dict[str, dict[str, int]] = {}


def month_words() -> dict[str, int]:
    """Every month name this check will read: the letter's country plus the visitor languages."""
    locale = active()
    merged = _months_any.get(locale.code)
    if merged is None:
        merged = {**locale.month_words(), **VISITOR_MONTHS}
        _months_any[locale.code] = merged
    return merged


# A day, a month written as a word in any script, and a four-digit year. The word class is the
# Unicode letter class rather than A-Z, which is the whole point of the table above.
_WORDED_DATE = re.compile(r"(?<!\d)(\d{1,2})\s+([^\W\d_]+)\.?\s+(\d{4})(?!\d)")
_NUMERIC_DATE = re.compile(r"\b\d{1,2}[-/.]\d{1,2}[-/.]\d{4}\b")

# A year, a month and a day with hyphens, which is how a model writes a date field in JSON. The
# guard reads the tool call before anything has been validated, so `send_before` reaches it as
# "2026-10-01" and nothing else in this file would recognise that as a date. It is read
# year-first, deliberately: the day-first reader below would take 2026 for a day and give up.
_ISO_DATE = re.compile(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)")

# The word for euro in the languages the desk answers in, and the sign. Written out for the same
# reason the month table is: a wrong amount is no less wrong for being written in Ukrainian.
_CURRENCY = r"eur|euros?|€|евро|євро|avro"

# The number itself, in the two ways an amount is grouped. The space-grouped form is tried first
# and its groups are exactly three digits, which is what a thousands separator is. That precision
# is what keeps a customer number out: "6512 3387" cannot be read as one number, because 6512 is
# not a group of three, while "1 234,56" can.
#
# The number has to END on a digit. A sentence closing on a customer number puts a full stop
# straight after the digits, and letting the number run over it leaves the pattern looking for a
# currency word across the sentence break. The next sentence in a plan opened with one, which read
# a customer number as three thousand euro and refused a sample letter that was correct.
# An ordinary space or a non-breaking one, the latter written as its codepoint: a rule that
# turns on a character nobody can see in an editor is a rule nobody can review.
_SPACE = f"[ {chr(0x00A0)}]"
_NUMBER = rf"\d{{1,3}}(?:{_SPACE}\d{{3}})+(?:,\d{{1,2}})?|\d(?:[\d.]*\d)?(?:,\d{{1,2}})?"

# An amount is a currency marker and a number, in either order. Both orders matter and only one
# of them used to be read: the letter prints "EUR 174,00" and prose in every one of these
# languages puts the word after the number instead. A bare number is deliberately NOT an amount,
# because every reference number, page count and day count in a reading is also a bare number.
#
# Both guards are letter lookarounds rather than \b, because the sign is not a word character:
# \b after it would refuse "540,00 €." while accepting "540,00 € x". The leading one is the reason
# "kleur 20" and "Debiteur 12345" are not amounts. They contain "eur 20" and "eur 12345", and
# without a letter check in front of the marker both became money claims that refused correct
# output over an ordinary Dutch word.
_AMOUNT = re.compile(
    rf"(?:(?<![^\W\d_])(?:{_CURRENCY})\s*(?:{_NUMBER})"
    rf"|(?:{_NUMBER})\s*(?:{_CURRENCY})(?![^\W\d_]))",
    re.IGNORECASE,
)

# A space between two digits inside a matched amount is a thousands separator, and the country's
# own parser reads the separator it prints rather than that one. Rewriting it here keeps the
# knowledge of what a grouped amount looks like in one place: "1 234,56" would otherwise parse as
# one euro, which is a wrong claim rather than a missed one.
_GROUPING_SPACE = re.compile(rf"(?<=\d){_SPACE}(?=\d)")


def verify(facts: LetterFacts, letter_text: str) -> VerificationResult:
    """Ground every sourced fact against the letter text."""
    grounded: list[GroundedFact] = []
    issues: list[VerificationIssue] = []

    for name, value in (("issued_on", facts.issued_on), ("deadline", facts.deadline)):
        _check_date(name, value, letter_text, grounded, issues)
    for index, dated in enumerate(facts.other_dates, start=1):
        _check_date(f"other_date_{index}", dated, letter_text, grounded, issues)

    _check_money("total_amount", facts.total_amount, letter_text, grounded, issues)
    for index, amount in enumerate(facts.line_amounts, start=1):
        _check_money(f"line_amount_{index}", amount, letter_text, grounded, issues)

    for name, named in (
        ("sender_name", facts.sender_name),
        ("letter_type", facts.letter_type),
        ("reference", facts.reference),
    ):
        _check_named(name, named, letter_text, grounded, issues)

    for index, span in enumerate(facts.consequences, start=1):
        _check_span(f"consequence_{index}", span, letter_text, grounded, issues)
    _check_span("objection_route", facts.objection_route, letter_text, grounded, issues)

    return VerificationResult(grounded=tuple(grounded), issues=tuple(issues))


def numeric_claims(text: str) -> frozenset[str]:
    """Every date and euro amount written in a piece of text, normalised for comparison.

    The guard uses this to ask whether a draft or an action step is carrying a number that never
    passed the check above.
    """
    locale = active()
    claims: set[str] = set()
    for match in _NUMERIC_DATE.finditer(text):
        found = locale.parse_date(match.group(0))
        if found is not None:
            claims.add(locale.format_date(found))
    for worded in _WORDED_DATE.finditer(text):
        found = _worded_date(worded.group(1), worded.group(2), worded.group(3))
        if found is not None:
            claims.add(locale.format_date(found))
    for iso in _ISO_DATE.finditer(text):
        found = _safe_date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        if found is not None:
            claims.add(locale.format_date(found))
    for match in _AMOUNT.finditer(text):
        cents = locale.parse_amount_cents(_GROUPING_SPACE.sub(".", match.group(0)))
        if cents is not None:
            claims.add(locale.format_amount(cents))
    return frozenset(claims)


def _safe_date(year: int, month: int, day: int) -> date | None:
    """A date, or None when those three numbers are not one. Never raises on nonsense input.

    A model writes 31 February and 2026-13-45 as readily as it writes a real date, and this runs
    over every sentence a model produces, so an impossible date has to be no claim rather than an
    exception on the reading path.
    """
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _worded_date(day: str, month_word: str, year: str) -> date | None:
    month = month_words().get(month_word.casefold())
    if month is None:
        return None
    return _safe_date(int(year), month, int(day))


def ungrounded_claims(text: str, allowed: Iterable[str]) -> frozenset[str]:
    """The dates and amounts in the text that are not in the allowed set."""
    return frozenset(numeric_claims(text) - frozenset(allowed))


def _check_date(
    name: str,
    value: LetterDate | None,
    letter_text: str,
    grounded: list[GroundedFact],
    issues: list[VerificationIssue],
) -> None:
    if value is None:
        return
    locale = active()
    claimed = value.to_date()
    written = locale.format_date(claimed)
    if not passage_is_in(letter_text, value.source.text):
        issues.append(
            VerificationIssue(
                name=name,
                problem=_NOT_IN_LETTER,
                claimed=written,
                span_text=value.source.text,
            )
        )
        return
    found = locale.parse_date(value.source.text)
    if found != claimed:
        issues.append(
            VerificationIssue(
                name=name,
                problem=_VALUE_NOT_IN_PASSAGE,
                claimed=written,
                span_text=value.source.text,
            )
        )
        return
    grounded.append(GroundedFact(name=name, display=written, span=value.source))


def _check_money(
    name: str,
    value: Money | None,
    letter_text: str,
    grounded: list[GroundedFact],
    issues: list[VerificationIssue],
) -> None:
    if value is None:
        return
    locale = active()
    display = locale.format_amount(value.cents)
    if not passage_is_in(letter_text, value.source.text):
        issues.append(
            VerificationIssue(
                name=name, problem=_NOT_IN_LETTER, claimed=display, span_text=value.source.text
            )
        )
        return
    if locale.parse_amount_cents(value.source.text) != value.cents:
        issues.append(
            VerificationIssue(
                name=name,
                problem=_VALUE_NOT_IN_PASSAGE,
                claimed=display,
                span_text=value.source.text,
            )
        )
        return
    grounded.append(GroundedFact(name=name, display=display, span=value.source))


def _check_named(
    name: str,
    value: NamedValue | None,
    letter_text: str,
    grounded: list[GroundedFact],
    issues: list[VerificationIssue],
) -> None:
    if value is None:
        return
    if not passage_is_in(letter_text, value.source.text):
        issues.append(
            VerificationIssue(
                name=name,
                problem=_NOT_IN_LETTER,
                claimed=value.value,
                span_text=value.source.text,
            )
        )
        return
    if not _value_in_passage(value.value, value.source.text):
        issues.append(
            VerificationIssue(
                name=name,
                problem=_VALUE_NOT_IN_PASSAGE,
                claimed=value.value,
                span_text=value.source.text,
            )
        )
        return
    grounded.append(GroundedFact(name=name, display=value.value, span=value.source))


def _check_span(
    name: str,
    span: SourceSpan | None,
    letter_text: str,
    grounded: list[GroundedFact],
    issues: list[VerificationIssue],
) -> None:
    if span is None:
        return
    if not passage_is_in(letter_text, span.text):
        issues.append(
            VerificationIssue(
                name=name, problem=_NOT_IN_LETTER, claimed=span.text, span_text=span.text
            )
        )
        return
    grounded.append(GroundedFact(name=name, display=span.text, span=span))


def _value_in_passage(value: str, passage: str) -> bool:
    """A named value counts as carried when the passage holds it, spacing aside.

    Reference numbers are the reason for the digits-only fallback: a letter prints 8194 5523 7761
    and a reading may return it closed up, and those are the same number.
    """
    if normalise(value) in normalise(passage):
        return True
    digits = re.sub(r"\D", "", value)
    return bool(digits) and digits in re.sub(r"\D", "", passage)
