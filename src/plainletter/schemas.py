"""The contracts every stage of the reading passes through.

Two rules shape all of these models and both come from the same failure: a model asked for a
deadline will produce a plausible one rather than admit it could not read the page.

1. Every fact a person acts on carries the passage it came from. A value with no `source` cannot
   be grounded, and anything that is not grounded never reaches the visitor.
2. Every such field is optional, and `unreadable` exists so that "I could not read it" is a value
   the extractor can return. A schema that demands a date is a schema that gets an invented one.

Dates are day, month and year integers and amounts are integer cents, never strings. A Dutch
letter writes 15-09-2026 and 1.234,50 where an English one writes 09/15/2026 and 1,234.50, so an
ambiguous string surviving into the pipeline is a wrong answer waiting to happen.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Frozen(BaseModel):
    """Base for every contract: immutable, and an unknown key is an error rather than a shrug."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceSpan(Frozen):
    """Text copied verbatim out of the letter, and the page it sits on."""

    page: int = Field(ge=1, description="1-based page number the passage appears on")
    text: str = Field(min_length=1, description="the passage exactly as it stands in the letter")


class Unreadable(Frozen):
    """A field the letter should carry but the photograph does not show clearly enough to use."""

    field: str
    reason: str
    ask_the_visitor: str = Field(description="what the volunteer should ask, in plain English")


class NamedValue(Frozen):
    value: str = Field(min_length=1)
    source: SourceSpan


class LetterDate(Frozen):
    day: int = Field(ge=1, le=31)
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2100)
    source: SourceSpan

    def to_date(self) -> date:
        return date(self.year, self.month, self.day)


class LabelledDate(LetterDate):
    """A date that is neither the letter's own date nor its deadline, with what the letter calls it.

    An immigration letter says the permit runs out on one date and the application has to be in by
    another. Both are load bearing, and a schema with room for only one of them forces a reading to
    drop whichever it thinks matters less.
    """

    label: str = Field(min_length=1, description="what this date is, in the letter's own words")


class Money(Frozen):
    currency: Literal["EUR"] = "EUR"
    cents: int = Field(ge=0)
    label: str = Field(
        min_length=1, description="what the amount is for, in the letter's own words"
    )
    source: SourceSpan


class LetterFacts(Frozen):
    """What the reading stage returns. Everything optional, everything sourced."""

    sender_id: str | None = Field(
        default=None, description="knowledge-base id of the sender, for example cjib"
    )
    sender_name: NamedValue | None = None
    letter_type: NamedValue | None = None
    reference: NamedValue | None = None
    issued_on: LetterDate | None = None
    deadline: LetterDate | None = None
    other_dates: tuple[LabelledDate, ...] = ()
    total_amount: Money | None = None
    line_amounts: tuple[Money, ...] = ()
    consequences: tuple[SourceSpan, ...] = Field(
        default=(), description="passages saying what happens if nothing is done"
    )
    objection_route: SourceSpan | None = Field(
        default=None, description="the passage describing how to object or appeal"
    )
    unreadable: tuple[Unreadable, ...] = ()


class GroundedFact(Frozen):
    """One fact the verifier matched against the letter text, keyed by the name downstream uses."""

    name: str
    display: str = Field(description="how the fact is written for a reader, already normalised")
    span: SourceSpan


class VerificationIssue(Frozen):
    name: str
    problem: str
    claimed: str
    span_text: str | None = None


class VerificationResult(Frozen):
    grounded: tuple[GroundedFact, ...] = ()
    issues: tuple[VerificationIssue, ...] = ()

    @property
    def is_grounded(self) -> bool:
        """True only when nothing failed the check. An empty reading is not a passing reading."""
        return not self.issues and bool(self.grounded)

    def display_values(self) -> frozenset[str]:
        return frozenset(fact.display for fact in self.grounded)


class Urgency(StrEnum):
    OVERDUE = "overdue"
    DUE_SOON = "due_soon"
    AMPLE = "ample"
    UNKNOWN = "unknown"


class DeadlineView(Frozen):
    """The deadline as the desk needs it: the date, the count, and the day to post by."""

    on: date
    days_left: int
    urgency: Urgency
    post_by: date | None = Field(
        default=None,
        description="last working day a posted reply still arrives in time, None when it is moot",
    )


class Explanation(Frozen):
    """The same four answers, in one language."""

    language: str = Field(min_length=2, description="BCP 47 tag, for example nl or ar")
    what_is_this: str = Field(min_length=1)
    by_when: str = Field(min_length=1)
    if_you_do_nothing: str = Field(min_length=1)


class ActionStep(Frozen):
    order: int = Field(ge=1)
    dutch: str = Field(min_length=1)
    visitor: str = Field(min_length=1)
    official_route: str | None = Field(
        default=None, description="the phone number, website or postal address for this step"
    )


class DraftLetter(Frozen):
    kind: Literal["objection", "payment_plan", "reply"]
    addressed_to: str
    send_before: date | None
    dutch: str
    visitor: str


class Handoff(Frozen):
    """Where this stops being a letter to explain and becomes a case for a professional."""

    required: bool
    referral: str
    reason: str


class DeskReading(Frozen):
    """Everything the desk shows, prints and saves for one letter."""

    facts: LetterFacts
    verification: VerificationResult
    deadline: DeadlineView | None
    sender_name: str
    letter_type: str
    visitor_language: str
    explanations: tuple[Explanation, ...]
    steps: tuple[ActionStep, ...]
    draft: DraftLetter | None
    handoff: Handoff
    sources: tuple[str, ...] = Field(
        default=(), description="official URLs behind the routes and consequences shown"
    )
