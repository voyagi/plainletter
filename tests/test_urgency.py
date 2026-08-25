from datetime import date
from typing import cast

import pytest

from plainletter import urgency
from plainletter.locales import Locale, use
from plainletter.locales.nl import NL
from plainletter.schemas import Urgency


def test_the_calendar_comes_from_the_locale_not_from_this_module() -> None:
    # Which days are working days is the one thing here that depends on the country, so a locale
    # with no holidays at all must make a national holiday an ordinary working day.
    class NoHolidays:
        def public_holidays(self, year: int) -> frozenset[date]:
            return frozenset()

    easter_monday = date(2026, 4, 6)
    assert not urgency.is_working_day(easter_monday)
    use(cast(Locale, NoHolidays()))
    try:
        assert urgency.is_working_day(easter_monday)
    finally:
        use(NL)


def test_working_days_skip_weekends_and_holidays() -> None:
    assert not urgency.is_working_day(date(2026, 4, 6))  # Easter Monday
    assert not urgency.is_working_day(date(2026, 8, 22))  # Saturday
    assert urgency.is_working_day(date(2026, 8, 21))


def test_five_working_days_before_a_deadline() -> None:
    assert urgency.working_days_before(date(2026, 9, 15), 5) == date(2026, 9, 8)


def test_counting_backwards_by_zero_is_the_deadline_itself() -> None:
    assert urgency.working_days_before(date(2026, 9, 15), 0) == date(2026, 9, 15)


def test_a_negative_count_is_a_programming_error_not_a_silent_shrug() -> None:
    with pytest.raises(ValueError):
        urgency.working_days_before(date(2026, 9, 15), -1)


def test_the_bands_a_desk_reads() -> None:
    deadline = date(2026, 9, 15)
    assert urgency.view(deadline, date(2026, 9, 16)).urgency is Urgency.OVERDUE
    assert urgency.view(deadline, date(2026, 9, 1)).urgency is Urgency.DUE_SOON
    assert urgency.view(deadline, date(2026, 8, 1)).urgency is Urgency.AMPLE


def test_a_posting_date_already_past_is_dropped_rather_than_printed() -> None:
    # Telling somebody to have posted a letter last week reads as an accusation, not as help.
    view = urgency.view(date(2026, 9, 15), date(2026, 9, 12))
    assert view is not None
    assert view.post_by is None


def test_no_deadline_in_the_letter_means_no_view_at_all() -> None:
    assert urgency.view(None, date(2026, 8, 21)) is None
