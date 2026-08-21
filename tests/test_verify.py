from plainletter.demo import sample_text, scripted_reading
from plainletter.schemas import LetterDate, Money, SourceSpan
from plainletter.verify import numeric_claims, ungrounded_claims, verify

SAMPLE = "cjib-verkeersboete"
LETTER = sample_text(SAMPLE)


def cjib_facts():
    return scripted_reading(SAMPLE).facts


def test_a_correct_reading_grounds_every_fact() -> None:
    result = verify(cjib_facts(), LETTER)
    assert result.issues == ()
    assert result.is_grounded
    assert "15 september 2026" in result.display_values()
    assert "EUR 174,00" in result.display_values()


def test_an_empty_reading_is_not_a_passing_reading() -> None:
    from plainletter.schemas import LetterFacts

    assert not verify(LetterFacts(), LETTER).is_grounded


def test_a_date_the_passage_does_not_carry_is_refused() -> None:
    facts = cjib_facts()
    wrong = facts.model_copy(
        update={
            "deadline": LetterDate(
                day=1,
                month=10,
                year=2026,
                source=SourceSpan(page=1, text="Betaal voor 15 september 2026."),
            )
        }
    )
    result = verify(wrong, LETTER)
    assert not result.is_grounded
    assert [issue.name for issue in result.issues] == ["deadline"]


def test_a_passage_that_is_not_in_the_letter_is_refused() -> None:
    facts = cjib_facts()
    invented = facts.model_copy(
        update={
            "deadline": LetterDate(
                day=1,
                month=10,
                year=2026,
                source=SourceSpan(page=1, text="Betaal voor 1 oktober 2026."),
            )
        }
    )
    result = verify(invented, LETTER)
    assert [issue.problem for issue in result.issues] == [
        "the cited passage does not appear in the letter"
    ]


def test_an_amount_that_does_not_match_its_passage_is_refused() -> None:
    facts = cjib_facts()
    wrong = facts.model_copy(
        update={
            "total_amount": Money(
                cents=99900,
                label="Totaal te betalen",
                source=SourceSpan(page=1, text="Totaal te betalen: EUR 174,00"),
            )
        }
    )
    assert not verify(wrong, LETTER).is_grounded


def test_a_reference_written_without_its_spaces_still_matches() -> None:
    facts = cjib_facts()
    closed_up = facts.model_copy(
        update={
            "reference": facts.reference.model_copy(update={"value": "819455237761"})
            if facts.reference
            else None
        }
    )
    result = verify(closed_up, LETTER)
    assert result.is_grounded


def test_numeric_claims_finds_dates_and_amounts_in_free_text() -> None:
    claims = numeric_claims("Betaal EUR 174,00 voor 15 september 2026 of 01-10-2026.")
    assert claims == {"EUR 174,00", "15 september 2026", "1 oktober 2026"}


def test_ungrounded_claims_reports_only_what_was_never_allowed() -> None:
    stray = ungrounded_claims(
        "Betaal EUR 174,00 voor 1 oktober 2026.", ["EUR 174,00", "15 september 2026"]
    )
    assert stray == {"1 oktober 2026"}
