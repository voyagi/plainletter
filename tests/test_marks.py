import itertools
from datetime import date

import pytest

from plainletter.demo import sample_input, sample_names, sample_text, scripted_model
from plainletter.marks import mark_letter
from plainletter.pipeline import Pipeline
from plainletter.schemas import (
    GroundedFact,
    LetterFacts,
    SourceSpan,
    Unreadable,
    VerificationResult,
)
from plainletter.text import canonical, fold_with_offsets, normalise

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


OVERLAP_LETTER = "Betaal voor 15 september 2026 het bedrag van EUR 174,00 aan het CJIB.\n"


def two_grounded(first: str, second: str):
    return VerificationResult(
        grounded=(
            GroundedFact(
                name="deadline",
                display="15 september 2026",
                span=SourceSpan(page=1, text=first),
            ),
            GroundedFact(
                name="total_amount",
                display="EUR 174,00",
                span=SourceSpan(page=1, text=second),
            ),
        )
    )


def washed(marked) -> str:
    return "".join(run.text for line in marked.lines for run in line.runs if run.mark is not None)


@pytest.mark.parametrize(
    ("label", "first", "second"),
    [
        ("apart", "Betaal voor 15 september 2026", "EUR 174,00 aan het CJIB"),
        (
            "nested",
            "Betaal voor 15 september 2026 het bedrag van EUR 174,00",
            "15 september 2026",
        ),
        (
            "overlapping",
            "Betaal voor 15 september 2026 het bedrag",
            "2026 het bedrag van EUR 174,00",
        ),
    ],
)
def test_every_fact_under_a_numeral_is_really_inside_the_words_it_marks(
    label: str, first: str, second: str
) -> None:
    # The key tells a volunteer "number four is where this came from", so the words under that
    # numeral have to contain the value. Two spans that merely overlap used to keep only the
    # first one's end, leaving the second value outside the wash with its name still listed
    # under the numeral, and unplaced stayed empty because the passage had been found.
    marked = mark_letter(OVERLAP_LETTER, LetterFacts(), two_grounded(first, second))
    assert marked.unplaced == ()
    text = washed(marked)
    assert "15 september 2026" in text, label
    assert "EUR 174,00" in text, label

    named = {name for key in marked.keys for name in key.facts}
    assert named == {"deadline", "total_amount"}, label
    for key in marked.keys:
        for name, value in (("deadline", "15 september 2026"), ("total_amount", "EUR 174,00")):
            if name in key.facts:
                assert value in key.text, f"{label}: {name} not in the key text it is filed under"


# ---------------------------------------------------------------------------------------------
# The swept property.
#
# Everything above picks its overlapping pairs. This generates them, because the merge that joins
# two touching passages was wrong for one shape and right for every shape anyone had thought to
# write down: two spans that merely overlap kept only the first one's end, so the second value
# fell outside the wash while its name stayed filed under that numeral, and `unplaced` stayed
# empty because the passage had been found.
# ---------------------------------------------------------------------------------------------

SWEPT_LETTER = (
    "Betaal voor 15 september 2026 het bedrag van EUR 174,00 aan het CJIB te Leeuwarden.\n"
)

# Start and end points spread across the letter, so the pairs below cover nesting, partial
# overlap, touching and disjoint without anyone having to enumerate those cases by hand.
_CUTS = [0, 6, 12, 19, 29, 33, 40, 44, 55, 62, len(SWEPT_LETTER) - 1]
_SWEPT_SPANS = [
    (start, end)
    for start, end in itertools.combinations(_CUTS, 2)
    if 4 <= end - start <= 60 and len(SWEPT_LETTER[start:end].strip()) >= 4
]


def two_passages(first: tuple[int, int], second: tuple[int, int]) -> VerificationResult:
    return VerificationResult(
        grounded=tuple(
            GroundedFact(
                name=name,
                display=SWEPT_LETTER[span[0] : span[1]].strip(),
                span=SourceSpan(page=1, text=SWEPT_LETTER[span[0] : span[1]].strip()),
            )
            for name, span in (("one", first), ("two", second))
        )
    )


def washed_text(marked) -> str:
    return "".join(run.text for line in marked.lines for run in line.runs if run.mark is not None)


def test_every_grounded_fact_is_marked_with_its_own_words_or_reported_unplaced() -> None:
    # The key tells a volunteer that number four is where a fact came from, so the words under
    # that numeral have to contain it. A fact that is neither marked nor listed in `unplaced` is
    # the shape the old merge produced, and nothing reported it.
    for first, second in itertools.combinations(_SWEPT_SPANS, 2):
        result = two_passages(first, second)
        marked = mark_letter(SWEPT_LETTER, LetterFacts(), result)

        accounted = {name for key in marked.keys for name in key.facts} | set(marked.unplaced)
        assert accounted == {"one", "two"}, f"{first}/{second}: accounted for {sorted(accounted)}"

        washed = washed_text(marked)
        for fact in result.grounded:
            if fact.name in marked.unplaced:
                continue
            assert fact.display in washed, f"{first}/{second}: {fact.name} placed but not marked"
            for key in marked.keys:
                if fact.name in key.facts:
                    assert fact.display in key.text, (
                        f"{first}/{second}: {fact.name} filed under a key whose words lack it"
                    )


def test_the_mark_sweep_really_produces_overlapping_pairs_to_check() -> None:
    # The control. A sweep whose pairs never touch would pass however the merge behaved, and the
    # merge is the only thing this sweep exists for. Measured when written: 1,128 pairs, 856 of
    # them overlapping, 231 of those a partial overlap rather than one nested inside the other.
    pairs = list(itertools.combinations(_SWEPT_SPANS, 2))
    overlapping = [
        (first, second) for first, second in pairs if first[0] < second[1] and second[0] < first[1]
    ]
    partial = [
        (first, second)
        for first, second in overlapping
        if not (first[0] <= second[0] and second[1] <= first[1])
        and not (second[0] <= first[0] and first[1] <= second[1])
    ]
    assert len(pairs) > 1_000
    assert len(overlapping) > 600, f"only {len(overlapping)} pairs overlap at all"
    assert len(partial) > 150, f"only {len(partial)} pairs overlap without nesting"
