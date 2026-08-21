from datetime import date

import pytest

from plainletter.dutch import (
    format_amount,
    format_date,
    parse_amount_cents,
    parse_date,
    passage_is_in,
)


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
    assert parse_date(text) == expected


@pytest.mark.parametrize(
    "text",
    ["geen datum hier", "32 september 2026", "15-13-2026", "September 2026", "2026-09-15xyz"],
)
def test_refuses_rather_than_guesses_a_date(text: str) -> None:
    assert parse_date(text) is None


def test_day_comes_first_the_dutch_way() -> None:
    # The whole point: 09-10-2026 is 9 October here and 10 September in the reading this product
    # must never fall back to.
    assert parse_date("09-10-2026") == date(2026, 10, 9)


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
    assert parse_amount_cents(text) == cents


def test_refuses_a_dot_group_that_is_not_a_thousands_separator() -> None:
    # 174.00 is neither Dutch nor unambiguous, and reading it as 17400 euro would be a hundredfold
    # error on a bill somebody has to pay.
    assert parse_amount_cents("EUR 174.00") is None


def test_formats_the_way_the_card_prints() -> None:
    assert format_date(date(2026, 9, 15)) == "15 september 2026"
    assert format_amount(123450) == "EUR 1.234,50"
    assert format_amount(900) == "EUR 9,00"


def test_a_passage_is_found_across_line_breaks_and_soft_hyphens() -> None:
    letter = "Betaalt u niet op tijd,\ndan wordt het bedrag ver­hoogd met 50 procent."
    assert passage_is_in(
        letter, "Betaalt u niet op tijd, dan wordt het bedrag verhoogd met 50 procent."
    )


def test_a_passage_that_is_not_there_is_not_found() -> None:
    assert not passage_is_in("Betaal voor 15 september 2026.", "Betaal voor 1 oktober 2026.")
