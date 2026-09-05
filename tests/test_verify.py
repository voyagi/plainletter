import pytest

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


@pytest.mark.parametrize(
    "sentence",
    [
        "Сплатіть до 15 вересня 2026 року.",
        "Zapłać przed 15 września 2026 r.",
        "15 Eylül 2026 tarihine kadar ödeyin.",
        "Pay before 15 September 2026.",
        "Betaal voor 15 sept. 2026.",
        "Оплатите до 15 сентября 2026 года.",
    ],
)
def test_a_date_written_with_a_visitor_language_month_is_read_as_the_same_date(
    sentence: str,
) -> None:
    assert numeric_claims(sentence) == {"15 september 2026"}


def test_a_wrong_date_in_a_visitor_language_is_still_caught() -> None:
    # The first live plan wrote its dates with Ukrainian month names. A guard that only reads
    # Latin month names would have passed an invented one unread.
    stray = ungrounded_claims(
        "Відправте листа не пізніше 8 вересня 2026 року.", ["15 september 2026"]
    )
    assert stray == {"8 september 2026"}


def test_a_word_that_is_not_a_month_is_not_a_date() -> None:
    assert numeric_claims("15 stuks 2026 bestellingen, 3 keer 2025 pakketten") == set()


@pytest.mark.parametrize(
    "sentence",
    [
        "U moet EUR 540,00 betalen.",
        "U moet 540,00 euro betalen.",
        "You must pay 540,00 euros.",
        "Заплатіть 540,00 євро.",
        "Zaplac 540,00 euro.",
        "540,00 avro odeyin.",
        "Het bedrag is 540,00 €.",
    ],
)
def test_an_amount_is_read_whichever_side_the_currency_is_written_on(sentence: str) -> None:
    # The letter prints "EUR 540,00" and prose in every language this desk answers in puts the
    # word after the number instead. Only the first of these used to be read, so an invented
    # amount written the ordinary way passed the guard unseen.
    assert numeric_claims(sentence) == {"EUR 540,00"}


def test_a_bare_number_is_still_not_an_amount() -> None:
    # The control for the line above. Every reference number, page count and day count in a
    # reading is a bare number, so reading one as money would refuse nearly every letter.
    assert numeric_claims("Kenmerk 8194 5523 7761, pagina 2 van 3, nog 14 dagen.") == set()


def test_a_date_written_the_way_a_json_field_writes_one_is_read() -> None:
    # The guard reads the tool call before anything is validated, so a date field arrives as
    # "2026-10-01". Nothing else in this module recognises that shape.
    assert numeric_claims('{"send_before": "2026-10-01"}') == {"1 oktober 2026"}


def test_an_impossible_iso_date_is_not_a_claim() -> None:
    assert numeric_claims('{"send_before": "2026-13-45"}') == set()


def test_a_number_ending_a_sentence_does_not_borrow_the_next_sentences_currency() -> None:
    # The svb sample closes a step on a customer number and opens the next one on an amount. A
    # pattern that lets the number run over the full stop welds the two into an amount neither
    # step wrote, and refuses a reading that was right.
    welded = "bel de SVB met klantnummer 6512 3387. EUR 299,86 komt op uw rekening."
    assert numeric_claims(welded) == {"EUR 299,86"}
