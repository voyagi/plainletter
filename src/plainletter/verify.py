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

from .dutch import (
    format_amount,
    format_date,
    normalise,
    parse_amount_cents,
    parse_date,
    passage_is_in,
)
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

_NOT_IN_LETTER = "the cited passage does not appear in the letter"
_VALUE_NOT_IN_PASSAGE = "the passage does not carry the value that was claimed"


def verify(facts: LetterFacts, letter_text: str) -> VerificationResult:
    """Ground every sourced fact against the letter text."""
    grounded: list[GroundedFact] = []
    issues: list[VerificationIssue] = []

    for name, value in (("issued_on", facts.issued_on), ("deadline", facts.deadline)):
        _check_date(name, value, letter_text, grounded, issues)

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
    claims: set[str] = set()
    for match in re.finditer(r"\b\d{1,2}[-/.]\d{1,2}[-/.]\d{4}\b", text):
        found = parse_date(match.group(0))
        if found is not None:
            claims.add(format_date(found))
    for match in re.finditer(r"\b\d{1,2}\s+[A-Za-z]+\.?\s+\d{4}\b", text):
        found = parse_date(match.group(0))
        if found is not None:
            claims.add(format_date(found))
    for match in re.finditer(r"(?:eur|euro|€)\s*\d[\d.]*(?:,\d{1,2})?", text, re.IGNORECASE):
        cents = parse_amount_cents(match.group(0))
        if cents is not None:
            claims.add(format_amount(cents))
    return frozenset(claims)


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
    claimed = value.to_date()
    if not passage_is_in(letter_text, value.source.text):
        issues.append(
            VerificationIssue(
                name=name,
                problem=_NOT_IN_LETTER,
                claimed=format_date(claimed),
                span_text=value.source.text,
            )
        )
        return
    found = parse_date(value.source.text)
    if found != claimed:
        issues.append(
            VerificationIssue(
                name=name,
                problem=_VALUE_NOT_IN_PASSAGE,
                claimed=format_date(claimed),
                span_text=value.source.text,
            )
        )
        return
    grounded.append(GroundedFact(name=name, display=format_date(claimed), span=value.source))


def _check_money(
    name: str,
    value: Money | None,
    letter_text: str,
    grounded: list[GroundedFact],
    issues: list[VerificationIssue],
) -> None:
    if value is None:
        return
    display = format_amount(value.cents)
    if not passage_is_in(letter_text, value.source.text):
        issues.append(
            VerificationIssue(
                name=name, problem=_NOT_IN_LETTER, claimed=display, span_text=value.source.text
            )
        )
        return
    if parse_amount_cents(value.source.text) != value.cents:
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
