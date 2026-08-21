from datetime import date

from icalendar import Calendar

from plainletter.demo import cjib_model, sample_text
from plainletter.pipeline import Pipeline
from plainletter.render import desk_card_html, is_rtl, reminder_ics

LETTER = sample_text("cjib-verkeersboete")
TODAY = date(2026, 8, 21)


def reading(language: str = "ar"):
    return Pipeline(model=cjib_model()).run(LETTER, LETTER, visitor_language=language, today=TODAY)


def test_the_card_carries_the_deadline_the_days_and_the_posting_date() -> None:
    card = desk_card_html(reading(), TODAY)
    assert "15 september 2026" in card
    assert "Nog 25 dagen" in card
    assert "8 september 2026" in card


def test_the_urgency_state_is_a_word_and_not_only_a_colour() -> None:
    # The card is printed in black and white behind a library counter, so the state has to survive
    # losing every colour on the page.
    assert "Nog tijd" in desk_card_html(reading(), TODAY)


def test_a_right_to_left_visitor_language_sets_the_direction() -> None:
    card = desk_card_html(reading("ar"), TODAY)
    assert 'dir="rtl"' in card
    assert 'lang="ar"' in card
    assert is_rtl("ar") and is_rtl("fa") and is_rtl("he")
    assert not is_rtl("nl")


def test_a_left_to_right_visitor_language_does_not() -> None:
    card = desk_card_html(reading("nl"), TODAY)
    assert 'dir="rtl"' not in card


def test_the_reminder_is_a_calendar_a_phone_can_open() -> None:
    ics = reminder_ics(reading(), uid="test@plainletter")
    calendar = Calendar.from_ical(ics)
    events = [item for item in calendar.walk() if item.name == "VEVENT"]
    assert len(events) == 1
    assert events[0]["SUMMARY"].startswith("Centraal Justitieel Incassobureau")
    assert events[0].decoded("DTSTART") == date(2026, 9, 15)
    assert any(item.name == "VALARM" for item in calendar.walk())


def test_the_same_reading_renders_the_same_reminder_twice() -> None:
    first = reminder_ics(reading(), uid="test@plainletter")
    second = reminder_ics(reading(), uid="test@plainletter")
    assert first == second
