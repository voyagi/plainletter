"""The boundary between what Plainletter does and where it does it.

Every letter is an official letter from somewhere, and the somewhere decides a short, closed list
of things: how a date and an amount are written, which national number has to be masked, which days
are not working days, the words the desk card prints, and who a volunteer sends the visitor to when
the desk cannot finish. Everything else in this package is the same wherever the letter came from.

That list is this module's protocol, and one file implements it per country. `locales/nl.py` is the
Netherlands, the only one shipped, and it is the file a second country would be a copy of. Nothing
outside `locales/` may hold a fact about a country: `tests/test_locale_boundary.py` fails the build
when it does, because a boundary asserted in a README is a boundary nobody is keeping.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable

FORMS = frozenset({"zero", "one", "two", "few", "many", "other"})
"""The names a language may give the forms of a counted sentence, from the Unicode plural rules."""


@dataclass(frozen=True)
class CountedWords:
    """One sentence in every form its language needs for a count.

    Languages disagree both about how many forms there are and about which count takes which one.
    English and Dutch have two and put only exactly one in the singular, so a count of zero takes
    the same form as a count of nine. Polish has four. Turkish has one. So the forms are named
    rather than numbered, and the locale decides which name a count reaches, in `plural_form`.

    `other` is the only form that must be filled. A language that needs no more fills that alone,
    and a form left out falls back to it, so a locale can never crash on a count it did not think
    about.
    """

    other: str
    zero: str | None = None
    one: str | None = None
    two: str | None = None
    few: str | None = None
    many: str | None = None

    def form(self, name: str) -> str:
        """The named form, or `other` where this language does not fill that one."""
        if name not in FORMS:
            raise ValueError(f"{name!r} is not one of the plural forms: {sorted(FORMS)}")
        filled: str | None = getattr(self, name)
        return filled if filled is not None else self.other


def counted(phrase: CountedWords, days: int) -> str:
    """A counted sentence in the form the country's language gives this count.

    Every caller goes through here rather than formatting a template itself, because picking the
    form is a fact about a language and this is the one place allowed to ask the locale for it.
    """
    return phrase.form(active().plural_form(days)).format(days=days)


@dataclass(frozen=True)
class DeskWords:
    """Every word the printed card and the calendar reminder say, in the country's own language.

    Templates take named fields and are formatted where they are used, so a translator can see the
    whole sentence rather than a fragment with a variable bolted on.
    """

    language: str
    """BCP 47 tag of the language these words are written in, and of the letter itself."""

    card_description: str
    """The card's meta description, one sentence."""

    question_what: str
    question_if_nothing: str
    question_by_when: str

    actions_heading: str
    keys_heading: str
    notes_heading: str
    handoff_heading: str

    reference: str
    """Template with `reference`."""
    reference_missing: str

    deadline_lead: str
    """Template with `date`."""
    deadline_missing: str
    days_left: CountedWords
    """Counted sentence with `days`, for a deadline still ahead."""
    days_overdue: CountedWords
    """Counted sentence with `days`, for one already passed."""
    post_by: str
    """Template with `date`, printed after the days line, so it starts with its own space."""

    urgency_overdue: str
    urgency_due_soon: str
    urgency_ample: str
    urgency_unknown: str

    case_note: str
    """Template with `case_id`. Printed emphasised, with `case_note_detail` running on after it."""
    case_note_detail: str
    disclaimer: str
    """Template with `date`."""
    ai_disclosure: str
    """The EU AI Act Article 50 disclosure, printed on the card and shown at the desk.

    It says two things in one breath, and both are the obligation rather than a nicety: that the
    person is dealing with an AI system, and that the text in front of them was written by one.
    """

    reminder_deadline: str
    """Template with `date`, the first sentence of the calendar entry."""
    reminder_alarm: CountedWords
    """Counted sentence with `days`, what the alarm says when it fires."""

    unknown_letter_type: str
    unknown_sender_name: str

    referral_last_resort_name: str
    """Who a volunteer sends the visitor to when nothing else applies."""
    referral_last_resort: str
    """The same body with how to reach it, for the places that print one line and no more."""
    referral_not_grounded: str
    referral_unknown_sender: str


@runtime_checkable
class Locale(Protocol):
    """What the rest of the package is allowed to ask about the country a letter came from."""

    @property
    def code(self) -> str:
        """The country's code, and the name of the file implementing it."""

    @property
    def words(self) -> DeskWords: ...

    @property
    def reminder_region(self) -> str:
        """The region tag in the calendar file's product id."""

    def plural_form(self, count: int) -> str:
        """Which form of a counted sentence this count takes, named as in `CountedWords`."""

    def month_words(self) -> dict[str, int]:
        """Month names and abbreviations as the country's letters print them."""

    def parse_date(self, text: str) -> date | None:
        """The first date in the text as the country writes dates, or None."""

    def parse_amount_cents(self, text: str) -> int | None:
        """The first money amount in the text as integer cents, or None when it is not readable."""

    def format_date(self, value: date) -> str:
        """A date the way the letter and the desk card write it."""

    def format_amount(self, cents: int) -> str:
        """An amount the way the letter and the payment page write it."""

    def mask_identifiers(self, text: str) -> str:
        """Mask the national identifiers this country's letters carry."""

    def public_holidays(self, year: int) -> frozenset[date]:
        """The days on which offices are closed and post does not move."""


_active: Locale | None = None


def active() -> Locale:
    """The locale every deterministic step reads from.

    Resolved on first use rather than at import, so a module can be imported without deciding which
    country it is running in, and so `use()` in a test cannot lose a race with an import.
    """
    global _active
    if _active is None:
        from .nl import NL

        _active = NL
    return _active


def use(locale: Locale) -> None:
    """Run the deterministic steps against another country. Nothing but tests calls this today."""
    global _active
    _active = locale
