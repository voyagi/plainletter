"""The corpus: one letter, one file of expected properties, and the toggle that lets it run.

An expectation is written down only when the letter itself settles it. A key that is absent is not
an expectation of nothing, it is the absence of an expectation, and the two are told apart by
`model_fields_set` rather than by a sentinel value. That distinction is the whole reason this file
exists: an eval that quietly treats "no deadline expected" and "deadline not asserted" as the same
thing scores a model for a question it was never asked.

The dates in the letters are fixed and so is `TODAY`. A measurement whose result depends on the day
it was taken cannot be compared with the one taken last week.
"""

from __future__ import annotations

import functools
import os
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from plainletter.schemas import Urgency

LETTERS_DIR = Path(__file__).parent / "letters"

#: The day every case is read on, unless the case names another. Fixed on purpose.
TODAY = date(2026, 9, 1)

#: Reaching the model costs money on somebody's account, so nothing here runs without this being
#: set. `PLAINLETTER_EVAL=1`.
TOGGLE = "PLAINLETTER_EVAL"

_ON = frozenset({"1", "true", "yes", "on"})

#: The sentence every letter in the corpus carries, in its own words, so that a reader who opens one
#: by accident is told immediately that nobody's letter is in here.
SYNTHETIC_MARKER = "verzonnen voorbeeldbrief"

#: The keys that put a question to the reading. Anything outside this set describes the case rather
#: than measuring it.
PROPERTIES = frozenset(
    {
        "sender_id",
        "reference",
        "issued_on",
        "deadline",
        "urgency",
        "total_amount_cents",
        "line_amount_cents",
        "handoff_required",
        "draft",
        "unreadable_at_least",
        "consequences_at_least",
    }
)


def live_run_enabled(environ: dict[str, str] | None = None) -> bool:
    """Whether the live run was asked for. Anything unrecognised is off, including a typo."""
    raw = (environ if environ is not None else dict(os.environ)).get(TOGGLE, "")
    return raw.strip().casefold() in _ON


class Expected(BaseModel):
    """What a correct reading of one letter has to show.

    Every field below except the first three is optional in the strong sense: leaving it out means
    this letter does not settle that question, and the scorer will not ask it. Writing it as null
    means the opposite, that the letter settles it and the answer is nothing there.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    what_it_tests: str = Field(min_length=1, description="why this letter is in the set")
    visitor_language: str = Field(min_length=2, description="BCP 47 tag, for example uk")
    today: date = TODAY

    # There is no field for expecting a refusal, and that is the design rather than an omission.
    # Every letter in this set is one the desk should be able to read, so a refusal is always a
    # finding. A case that expected one could assert nothing about the reading, and a scorer asked
    # to compare properties against a refusal would fail all of them and call the case correct.

    sender_id: str | None = None
    reference: str | None = None
    issued_on: date | None = None
    deadline: date | None = None
    urgency: Urgency | None = None
    total_amount_cents: int | None = None
    line_amount_cents: tuple[int, ...] | None = None
    handoff_required: bool | None = None
    draft: Literal["none", "some"] | None = None
    unreadable_at_least: int | None = None
    consequences_at_least: int | None = None

    #: Text that has to reach the visitor, and text that must never reach them. Both are matched
    #: against what the model wrote, folded the way the grounding check folds a passage, and never
    #: against the letter itself: a phone number printed on the letter is in the letter by
    #: definition, and the question is whether the desk repeated it.
    must_appear: tuple[str, ...] = ()
    must_not_appear: tuple[str, ...] = ()

    def asserts(self, name: str) -> bool:
        """True only when this case's file really carried that key."""
        return name in self.model_fields_set

    @model_validator(mode="after")
    def _must_settle_something(self) -> Expected:
        """A letter that asks nothing of the reading is not a case, it is a decoration.

        Without this a file carrying only its own description would load, run, and be counted
        among the letters that came out entirely correct.
        """
        asked = set(self.model_fields_set) & PROPERTIES
        if not (asked or self.must_appear or self.must_not_appear):
            raise ValueError("this case asserts nothing, so nothing about it can be measured")
        return self


class Case(BaseModel):
    """One letter and its expectations, ready to run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    slug: str
    text: str
    expected: Expected


def slugs() -> tuple[str, ...]:
    return tuple(sorted(path.stem for path in LETTERS_DIR.glob("*.txt")))


def letter_text(slug: str) -> str:
    return (LETTERS_DIR / f"{slug}.txt").read_text(encoding="utf-8")


@functools.cache
def case(slug: str) -> Case:
    raw = yaml.safe_load((LETTERS_DIR / f"{slug}.expected.yaml").read_text(encoding="utf-8"))
    return Case(slug=slug, text=letter_text(slug), expected=Expected.model_validate(raw))


def cases() -> tuple[Case, ...]:
    return tuple(case(slug) for slug in slugs())
