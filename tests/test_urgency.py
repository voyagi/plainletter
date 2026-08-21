from datetime import date, timedelta

import pytest

from plainletter import urgency
from plainletter.schemas import Urgency


def test_the_shifting_holidays_hang_off_easter() -> None:
    holidays = urgency.dutch_public_holidays(2026)
    easter_monday = date(2026, 4, 6)
    assert easter_monday in holidays
    assert easter_monday + timedelta(days=38) in holidays  # Hemelvaartsdag
    assert date(2026, 1, 1) in holidays
    assert date(2026, 12, 26) in holidays


def test_kings_day_steps_back_when_it_lands_on_a_sunday() -> None:
    # 27 April 2031 is a Sunday, so the day off is the Saturday before it.
    assert date(2031, 4, 27).weekday() == 6
    assert date(2031, 4, 26) in urgency.dutch_public_holidays(2031)
    assert date(2031, 4, 27) not in urgency.dutch_public_holidays(2031)


def test_liberation_day_is_only_a_day_off_in_the_lustrum_years() -> None:
    assert date(2030, 5, 5) in urgency.dutch_public_holidays(2030)
    assert date(2026, 5, 5) not in urgency.dutch_public_holidays(2026)


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
