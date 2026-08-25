from datetime import date

import pytest

from plainletter.locales.nl import NL


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Betaal voor 15 september 2026.", date(2026, 9, 15)),
        ("Datum beschikking: 4 augustus 2026", date(2026, 8, 4)),
        ("verzonden 1 mrt. 2027", date(2027, 3, 1)),
        ("15-09-2026", date(2026, 9, 15)),
        ("15/09/2026", date(2026, 9, 15)),
        ("15.09.2026", date(2026, 9, 15)),
    ],
)
def test_reads_the_dates_dutch_letters_print(text: str, expected: date) -> None:
    assert NL.parse_date(text) == expected


@pytest.mark.parametrize(
    "text",
    ["geen datum hier", "32 september 2026", "15-13-2026", "September 2026", "2026-09-15xyz"],
)
def test_refuses_rather_than_guesses_a_date(text: str) -> None:
    assert NL.parse_date(text) is None


def test_day_comes_first_the_dutch_way() -> None:
    # The whole point: 09-10-2026 is 9 October here and 10 September in the reading this product
    # must never fall back to.
    assert NL.parse_date("09-10-2026") == date(2026, 10, 9)


@pytest.mark.parametrize(
    ("text", "cents"),
    [
        ("Totaal te betalen: EUR 174,00", 17400),
        ("EUR 9,00", 900),
        ("€ 1.234,50", 123450),
        ("bedrag 2.000", 200000),
        ("165", 16500),
    ],
)
def test_reads_amounts_in_dutch_notation(text: str, cents: int) -> None:
    assert NL.parse_amount_cents(text) == cents


def test_refuses_a_dot_group_that_is_not_a_thousands_separator() -> None:
    # 174.00 is neither Dutch nor unambiguous, and reading it as 17400 euro would be a hundredfold
    # error on a bill somebody has to pay.
    assert NL.parse_amount_cents("EUR 174.00") is None


def test_formats_the_way_the_card_prints() -> None:
    assert NL.format_date(date(2026, 9, 15)) == "15 september 2026"
    assert NL.format_amount(123450) == "EUR 1.234,50"
    assert NL.format_amount(900) == "EUR 9,00"


def test_the_month_table_covers_the_names_and_the_abbreviations() -> None:
    words = NL.month_words()
    assert words["september"] == 9
    assert words["sept"] == 9
    assert words["mrt"] == 3


def test_the_easter_holidays_move_with_easter() -> None:
    holidays = NL.public_holidays(2026)
    assert date(2026, 1, 1) in holidays
    assert date(2026, 4, 6) in holidays  # Tweede Paasdag, Easter Monday 2026
    assert date(2026, 12, 26) in holidays
    assert date(2026, 6, 3) not in holidays


def test_kings_day_steps_back_off_a_sunday() -> None:
    assert date(2031, 4, 26) in NL.public_holidays(2031)
    assert date(2031, 4, 27) not in NL.public_holidays(2031)


def test_liberation_day_is_a_holiday_only_in_the_lustrum_years() -> None:
    assert date(2030, 5, 5) in NL.public_holidays(2030)
    assert date(2026, 5, 5) not in NL.public_holidays(2026)
