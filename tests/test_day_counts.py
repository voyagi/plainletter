"""Counting in a language that does not count the way a template does.

Dutch takes the singular at exactly one and the plural everywhere else, zero included. The desk
card printed "Nog 1 dagen" on the one day it is read hardest, the day before a deadline, and the
same fault stood in three sentences at once: the days left, the days overdue, and the alarm on the
calendar entry that leaves the desk with the visitor.

So what is pinned here is every counted sentence the country's words carry, found by walking the
words rather than by listing the three that were noticed. A fourth added later is swept the day it
is added, and a locale for a second country is swept the day it lands.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import date

from icalendar import Calendar

from plainletter.demo import sample_input, scripted_model
from plainletter.locales import CountedWords, active, counted
from plainletter.pipeline import Pipeline
from plainletter.render import REMINDER_LEAD_DAYS, desk_card_html, reminder_ics

SAMPLE = "cjib-verkeersboete"
LETTER = sample_input(SAMPLE)

# The sample letter's own deadline. Reading it on the days around this one is what puts a real
# count of one, and a real count of zero, through the whole renderer.
DEADLINE = date(2026, 9, 15)


def counted_sentences() -> list[tuple[str, CountedWords]]:
    """Every sentence in the country's words that takes a count."""
    words = active().words
    found = [
        (item.name, getattr(words, item.name))
        for item in fields(words)
        if isinstance(getattr(words, item.name), CountedWords)
    ]
    return found


def shape(phrase: CountedWords, count: int) -> str:
    """The sentence with the numeral taken out, so two counts compare as wordings and not as text.

    This is what lets the sweep state the rule without naming a word in any language: the wording
    at one has to differ from the wording at two, and the wordings at zero, two and twenty-one have
    to agree.
    """
    return counted(phrase, count).replace(str(count), "#")


def reading_on(today: date):
    return Pipeline(model=scripted_model(SAMPLE)).run(LETTER, visitor_language="uk", today=today)


def test_the_sweep_finds_the_counted_sentences_at_all() -> None:
    # Without this the whole file passes on a build where the walk returns nothing.
    found = dict(counted_sentences())
    assert {"days_left", "days_overdue", "reminder_alarm"} <= set(found)


def test_one_of_something_is_worded_differently_from_every_other_count() -> None:
    for name, phrase in counted_sentences():
        assert shape(phrase, 1) != shape(phrase, 2), f"{name} words one exactly like two"
        assert shape(phrase, 0) == shape(phrase, 2), f"{name} words zero as though it were one"
        assert shape(phrase, 21) == shape(phrase, 2), f"{name} words twenty-one apart from two"


def test_the_sweep_would_catch_a_sentence_that_forgot_the_singular() -> None:
    # The control. A comparison nobody has seen fail proves nothing about the sentences above, and
    # this is the exact shape all three of them had: one wording for every count there is.
    forgot = CountedWords(other="Nog {days} dagen.")
    assert shape(forgot, 1) == shape(forgot, 2)


def test_the_printed_card_counts_the_last_day_in_the_singular() -> None:
    day_before = DEADLINE.replace(day=DEADLINE.day - 1)
    card = desk_card_html(reading_on(day_before), day_before)
    assert "Nog 1 dag." in card
    assert "1 dagen" not in card


def test_the_printed_card_counts_the_deadline_itself_in_the_plural() -> None:
    # Zero is where a rule written from English intuition goes wrong the other way.
    card = desk_card_html(reading_on(DEADLINE), DEADLINE)
    assert "Nog 0 dagen." in card


def test_the_printed_card_counts_one_day_late_in_the_singular() -> None:
    day_after = DEADLINE.replace(day=DEADLINE.day + 1)
    card = desk_card_html(reading_on(day_after), day_after)
    assert "1 dag te laat." in card
    assert "1 dagen" not in card


def test_the_printed_card_still_counts_an_ordinary_run_in_the_plural() -> None:
    # The control on the other side: the fix must not have turned every count into a singular.
    card = desk_card_html(reading_on(date(2026, 8, 21)), date(2026, 8, 21))
    assert "Nog 25 dagen." in card


def test_the_calendar_alarm_counts_the_same_way_the_card_does() -> None:
    ics = reminder_ics(reading_on(date(2026, 8, 21)), uid="test@plainletter")
    alarm = next(item for item in Calendar.from_ical(ics).walk() if item.name == "VALARM")
    assert str(alarm["DESCRIPTION"]).endswith(f"nog {REMINDER_LEAD_DAYS} dagen")

    # The lead is three days, so the renderer cannot reach this sentence's singular today. It is
    # pinned directly instead, because the day somebody shortens the lead to one day is the day it
    # prints, and nothing else in the suite would be looking.
    assert counted(active().words.reminder_alarm, 1) == "nog 1 dag"
