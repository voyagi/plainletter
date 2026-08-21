from datetime import date

import pytest

from plainletter.demo import sample_input, sample_names, sample_text, scripted_model
from plainletter.dutch import canonical, fold_with_offsets, normalise
from plainletter.marks import mark_letter
from plainletter.pipeline import Pipeline
from plainletter.schemas import (
    GroundedFact,
    LetterFacts,
    SourceSpan,
    Unreadable,
    VerificationResult,
)

TODAY = date(2026, 8, 21)


def reading(name: str = "cjib-verkeersboete", language: str = "uk"):
    return Pipeline(model=scripted_model(name)).run(
        sample_input(name), visitor_language=language, today=TODAY
    )


def line_text(line) -> str:
    return "".join(run.text for run in line.runs)


def test_the_fold_and_its_offsets_agree_with_the_comparison_the_verifier_uses() -> None:
    # The point of the offset map is that marking cannot drift from grounding. If these two ever
    # disagree, a fact the verifier accepted would print with no numeral, and a missing numeral is
    # how this product says the letter does not contain the fact.
    for name in sample_names():
        text = canonical(sample_text(name))
        folded, offsets = fold_with_offsets(text)
        assert folded == normalise(text)
        assert len(folded) == len(offsets)
        assert all(0 <= index < len(text) for index in offsets)


def test_an_offset_slice_recovers_the_passage_it_marked() -> None:
    text = canonical("Regel een\n\n  Totaal te betalen:   EUR 174,00  \nRegel drie")
    folded, offsets = fold_with_offsets(text)
    needle = normalise("Totaal te betalen: EUR 174,00")
    at = folded.find(needle)
    assert at >= 0
    start, end = offsets[at], offsets[at + len(needle) - 1] + 1
    assert text[start:end] == "Totaal te betalen:   EUR 174,00"


@pytest.mark.parametrize("name", sample_names())
def test_every_grounded_passage_on_every_sample_finds_its_place(name: str) -> None:
    # unplaced is a bug channel, not a finding channel: a passage the verifier grounded and the
    # marker could not locate means the two disagree about what is in the letter.
    assert reading(name, "en").letter.unplaced == ()


def test_the_marks_are_numbered_down_the_letter_and_carry_their_own_words() -> None:
    marked = reading().letter
    assert [key.number for key in marked.keys] == list(range(1, len(marked.keys) + 1))
    assert marked.keys[0].facts == ("sender_name",)
    assert "Beschikkingsnummer" in marked.keys[2].text
    assert marked.keys[-1].facts == ("objection_route",)

    margins = [line.mark for line in marked.lines if line.mark is not None]
    assert margins == sorted(margins)


def test_a_passage_that_wraps_two_lines_washes_both_and_is_numbered_once() -> None:
    marked = reading().letter
    consequence = next(key for key in marked.keys if "verhoogd met 50 procent" in key.text)
    washed = [
        line for line in marked.lines if any(run.mark == consequence.number for run in line.runs)
    ]
    assert len(washed) == 2
    assert [line.mark for line in washed] == [consequence.number, None]


def test_a_passage_starting_mid_line_leaves_the_words_before_it_unmarked() -> None:
    marked = reading().letter
    line = next(line for line in marked.lines if line_text(line).startswith("Bent u het niet eens"))
    assert line.runs[0].mark is None
    assert line.runs[0].text.startswith("Bent u het niet eens met deze beschikking?")
    assert line.runs[1].mark == line.mark


def test_the_broken_key_sits_beside_the_line_the_desk_could_not_read() -> None:
    marked = reading().letter
    gapped = [line for line in marked.lines if line.gap]
    assert len(gapped) == 1
    assert line_text(gapped[0]).startswith("Kenteken:")
    assert gapped[0].mark is None
    assert marked.gaps[0].field == "kenteken"


def test_the_letter_reads_back_word_for_word_out_of_its_runs() -> None:
    # The console renders nothing but these runs, so anything lost here is lost from the letter the
    # volunteer is shown.
    marked = reading().letter
    rebuilt = "\n".join(line_text(line) for line in marked.lines)
    assert rebuilt == canonical(sample_text("cjib-verkeersboete"))


def test_a_citizen_service_number_is_masked_before_the_letter_is_ever_split() -> None:
    # Splitting first and masking the pieces would let a number that straddles a split survive.
    letter = "Belastingdienst\nBurgerservicenummer: 1234 56 780\nTotaal te betalen: EUR 10,00"
    facts = LetterFacts()
    result = VerificationResult(
        grounded=(
            GroundedFact(
                name="sender_name",
                display="Belastingdienst",
                span=SourceSpan(page=1, text="Belastingdienst"),
            ),
        )
    )
    marked = mark_letter(letter, facts, result)
    rebuilt = "\n".join(line_text(line) for line in marked.lines)
    assert "1234 56 780" not in rebuilt
    assert "BSN verborgen" in rebuilt


def test_a_passage_the_letter_does_not_carry_is_reported_rather_than_guessed_at() -> None:
    result = VerificationResult(
        grounded=(
            GroundedFact(
                name="deadline",
                display="15 september 2026",
                span=SourceSpan(page=1, text="Betaal voor 15 september 2026."),
            ),
        )
    )
    marked = mark_letter("Een brief zonder die zin.", LetterFacts(), result)
    assert marked.unplaced == ("deadline",)
    assert marked.keys == ()


def test_two_facts_citing_one_passage_share_a_single_mark() -> None:
    span = SourceSpan(page=1, text="Totaal te betalen: EUR 174,00")
    result = VerificationResult(
        grounded=(
            GroundedFact(name="total_amount", display="EUR 174,00", span=span),
            GroundedFact(name="line_amount_1", display="EUR 174,00", span=span),
        )
    )
    marked = mark_letter("Totaal te betalen: EUR 174,00", LetterFacts(), result)
    assert len(marked.keys) == 1
    assert marked.keys[0].facts == ("total_amount", "line_amount_1")


def test_a_passage_quoted_whole_and_in_part_keeps_one_unbroken_wash() -> None:
    letter = "Beschikkingsnummer: 8194 5523 7761"
    result = VerificationResult(
        grounded=(
            GroundedFact(
                name="reference",
                display="8194 5523 7761",
                span=SourceSpan(page=1, text="8194 5523 7761"),
            ),
            GroundedFact(
                name="letter_type",
                display="Beschikkingsnummer: 8194 5523 7761",
                span=SourceSpan(page=1, text=letter),
            ),
        )
    )
    marked = mark_letter(letter, LetterFacts(), result)
    assert len(marked.keys) == 1
    assert marked.lines[0].runs == (marked.lines[0].runs[0],)
    assert marked.lines[0].runs[0].text == letter


def test_an_unreadable_field_the_letter_never_names_still_reaches_the_desk() -> None:
    facts = LetterFacts(
        unreadable=(
            Unreadable(
                field="handtekening",
                reason="Het ondertekeningsblok staat niet op de foto.",
                ask_the_visitor="Vraag of de brief ondertekend is.",
            ),
        )
    )
    marked = mark_letter("Een korte brief.", facts, VerificationResult())
    assert marked.gaps[0].field == "handtekening"
    assert not any(line.gap for line in marked.lines)
