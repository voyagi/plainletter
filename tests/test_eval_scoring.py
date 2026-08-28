"""Proof that the scorecard would notice. A harness only ever run against a good answer has never
been shown to detect a bad one, so every kind of wrong answer is manufactured here and the check
that should catch it is named.

The starting point is a real run: one letter from the set, read by a stand-in whose answers are
written out in full, through the actual pipeline with the actual verifier. Each test then changes
exactly one thing about that reading and asserts that exactly one check changes its mind. One, not
at least one: a scorer whose checks overlap reports four failures for one fault and drowns the
reader who has to act on it.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from evals import cases as corpus
from evals.run import read_one
from evals.scoring import RunOutcome, Scorecard, score
from plainletter.demo import ScriptedReadingModel
from plainletter.schemas import (
    ActionStep,
    DeskReading,
    DraftLetter,
    Explanation,
    Handoff,
    LabelledDate,
    LetterDate,
    LetterFacts,
    MarkedLetter,
    Money,
    NamedValue,
    SourceSpan,
    VerificationIssue,
    VerificationResult,
)

SLUG = "cjib-eerste-aanmaning"


def page(text: str) -> SourceSpan:
    return SourceSpan(page=1, text=text)


GOOD_FACTS = LetterFacts(
    sender_id="cjib",
    sender_name=NamedValue(
        value="Centraal Justitieel Incassobureau", source=page("Centraal Justitieel Incassobureau")
    ),
    letter_type=NamedValue(
        value="Eerste aanmaning administratieve sanctie",
        source=page("Eerste aanmaning administratieve sanctie"),
    ),
    reference=NamedValue(value="7702 4418 9931", source=page("Beschikkingsnummer: 7702 4418 9931")),
    issued_on=LetterDate(
        day=20, month=8, year=2026, source=page("Datum aanmaning: 20 augustus 2026")
    ),
    deadline=LetterDate(day=20, month=9, year=2026, source=page("Betaal voor 20 september 2026.")),
    other_dates=(
        LabelledDate(
            day=3,
            month=7,
            year=2026,
            label="Pleegdatum",
            source=page("Pleegdatum: 3 juli 2026, 08:41 uur"),
        ),
    ),
    total_amount=Money(
        cents=42000, label="Totaal te betalen", source=page("Totaal te betalen: EUR 420,00")
    ),
    line_amounts=(
        Money(
            cents=28000,
            label="Oorspronkelijk sanctiebedrag",
            source=page("Oorspronkelijk sanctiebedrag: EUR 280,00"),
        ),
        Money(
            cents=14000,
            label="Verhoging 50 procent",
            source=page("Verhoging 50 procent: EUR 140,00"),
        ),
    ),
    consequences=(
        page(
            "Betaalt u ook nu niet, dan verhogen wij het bedrag een tweede keer met 100 procent "
            "van het oorspronkelijke bedrag."
        ),
    ),
    objection_route=page(
        "U kunt binnen zes weken na de datum van de beschikking beroep instellen bij de officier "
        "van justitie."
    ),
)

GOOD_EXPLANATIONS = (
    Explanation(
        language="nl",
        what_is_this="Een verkeersboete van het CJIB. U moet EUR 420,00 betalen.",
        by_when="Betaal voor 20 september 2026.",
        if_you_do_nothing="Het bedrag wordt nog een keer verhoogd.",
    ),
    Explanation(
        language="tr",
        what_is_this="CJIB tarafindan gonderilen bir trafik cezasi. EUR 420,00 odemeniz gerekiyor.",
        by_when="20 september 2026 tarihinden once odeyin.",
        if_you_do_nothing="Tutar bir kez daha artirilir.",
    ),
)

GOOD_STEPS = (
    ActionStep(
        order=1,
        dutch="Betaal EUR 420,00 met beschikkingsnummer 7702 4418 9931.",
        visitor="7702 4418 9931 numarasi ile EUR 420,00 odeyin.",
    ),
    ActionStep(
        order=2,
        dutch="Kunt u het niet in een keer betalen? Vraag een betalingsregeling aan.",
        visitor="Tek seferde odeyemiyorsaniz taksitlendirme isteyin.",
    ),
)


def good_model() -> ScriptedReadingModel:
    return ScriptedReadingModel(
        facts=GOOD_FACTS,
        explanations=GOOD_EXPLANATIONS,
        steps=GOOD_STEPS,
        draft_letter=None,
        transcript=corpus.letter_text(SLUG),
    )


@pytest.fixture(scope="module")
def good() -> DeskReading:
    """One correct reading, produced by the real pipeline rather than assembled by hand."""
    outcome = read_one(corpus.case(SLUG), good_model())
    assert outcome.error is None, outcome.error
    assert outcome.reading is not None, outcome.refusal
    return outcome.reading


def failures(reading: DeskReading, slug: str = SLUG) -> set[str]:
    result = score(corpus.case(slug), RunOutcome(reading=reading))
    return {check.name for check in result.checks if not check.passed}


def test_a_correct_reading_answers_every_question(good: DeskReading) -> None:
    result = score(corpus.case(SLUG), RunOutcome(reading=good))
    assert result.passed, [check for check in result.checks if not check.passed]
    assert result.checks, "a case that produced no checks proves nothing"


def with_facts(reading: DeskReading, **changes: object) -> DeskReading:
    return reading.model_copy(update={"facts": reading.facts.model_copy(update=changes)})


def bad_sender(reading: DeskReading) -> DeskReading:
    return with_facts(reading, sender_id="duo")


def no_reference(reading: DeskReading) -> DeskReading:
    return with_facts(reading, reference=None)


def wrong_issue_date(reading: DeskReading) -> DeskReading:
    moved = LetterDate(day=21, month=8, year=2026, source=page("Datum aanmaning: 20 augustus 2026"))
    return with_facts(reading, issued_on=moved)


def wrong_deadline(reading: DeskReading) -> DeskReading:
    moved = LetterDate(day=21, month=9, year=2026, source=page("Betaal voor 20 september 2026."))
    return with_facts(reading, deadline=moved)


def wrong_total(reading: DeskReading) -> DeskReading:
    wrong = Money(
        cents=28000, label="Totaal te betalen", source=page("Totaal te betalen: EUR 420,00")
    )
    return with_facts(reading, total_amount=wrong)


def no_line_amounts(reading: DeskReading) -> DeskReading:
    return with_facts(reading, line_amounts=())


def no_consequences(reading: DeskReading) -> DeskReading:
    return with_facts(reading, consequences=())


def sent_to_a_person(reading: DeskReading) -> DeskReading:
    handoff = Handoff(required=True, referral="Juridisch Loket", reason="a manufactured handoff")
    return reading.model_copy(update={"handoff": handoff})


def only_dutch(reading: DeskReading) -> DeskReading:
    dutch = tuple(item for item in reading.explanations if item.language == "nl")
    return reading.model_copy(update={"explanations": dutch})


def nothing_to_do(reading: DeskReading) -> DeskReading:
    return reading.model_copy(update={"steps": ()})


def ungrounded(reading: DeskReading) -> DeskReading:
    spoiled = VerificationResult(
        grounded=reading.verification.grounded,
        issues=(
            VerificationIssue(
                name="deadline", problem="a manufactured problem", claimed="20 september 2026"
            ),
        ),
    )
    return reading.model_copy(update={"verification": spoiled})


def amount_never_written(reading: DeskReading) -> DeskReading:
    # Every place the desk writes, not only the explanation: the point of the check is that the
    # amount reached the visitor somewhere, so a mutation that leaves it in a step tests nothing.
    quiet = tuple(
        item.model_copy(update={"what_is_this": "Een verkeersboete van het CJIB."})
        for item in reading.explanations
    )
    steps = tuple(
        step.model_copy(
            update={
                "dutch": "Betaal het bedrag met het beschikkingsnummer.",
                "visitor": "Tutari dosya numarasi ile odeyin.",
            }
        )
        for step in reading.steps
    )
    return reading.model_copy(update={"explanations": quiet, "steps": steps})


def no_urgency(reading: DeskReading) -> DeskReading:
    return reading.model_copy(update={"deadline": None})


@pytest.mark.parametrize(
    ("spoil", "caught_by"),
    [
        (bad_sender, "sender_id"),
        (no_reference, "reference"),
        (wrong_issue_date, "issued_on"),
        (wrong_deadline, "deadline"),
        (wrong_total, "total_amount_cents"),
        (no_line_amounts, "line_amount_cents"),
        (no_consequences, "consequences_at_least"),
        (sent_to_a_person, "handoff_required"),
        (only_dutch, "explained_in_both_languages"),
        (nothing_to_do, "an action plan with something in it"),
        (ungrounded, "grounded"),
        (amount_never_written, "must_appear: EUR 420,00"),
        (no_urgency, "urgency"),
    ],
)
def test_one_thing_wrong_fails_exactly_one_check(
    good: DeskReading, spoil: Callable[[DeskReading], DeskReading], caught_by: str
) -> None:
    assert failures(spoil(good)) == {caught_by}


def test_a_refusal_fails_every_question_rather_than_skipping_them(good: DeskReading) -> None:
    """The denominator must not shrink when the product breaks.

    If a refused letter simply had no checks, a version that refused all twenty would report full
    marks over nothing, which is the most flattering possible way to describe a total failure.
    """
    case = corpus.case(SLUG)
    refused = score(case, RunOutcome(refusal="the reading was refused"))
    answered = score(case, RunOutcome(reading=good))

    assert len(refused.checks) == len(answered.checks)
    assert all(not check.passed for check in refused.checks)
    assert not refused.completed
    assert not refused.passed


def test_a_harness_error_is_not_scored_as_a_dozen_wrong_answers(good: DeskReading) -> None:
    """A rate limit on one letter must not move the accuracy figure.

    A refusal is an answer and every question it was asked is marked wrong. A timeout is not an
    answer at all, so it asks nothing: otherwise a Bedrock hiccup halfway through a run reads as a
    regression in the next comparison, which is a change nobody made.
    """
    case = corpus.case(SLUG)
    broken = score(case, RunOutcome(error="ThrottlingException: rate exceeded"))

    assert broken.checks == ()
    assert not broken.passed
    assert not broken.completed
    assert "rate exceeded" in broken.detail

    card = Scorecard()
    card.add(score(case, RunOutcome(reading=good)))
    card.add(broken)
    assert card.ran == 2
    assert card.cases_passed == 1
    assert len(card.errors) == 1
    assert card.measured, "one letter answered is still a measurement, with the error beside it"
    # The properties figure is over the letter that answered, and says so.
    assert card.checks_passed == card.checks_total
    assert "over the 1 letters the model answered" in "\n".join(card.lines())


def test_a_forbidden_string_is_counted_apart_from_the_score() -> None:
    """A phone number off the letter reaching the desk card is a harm, not four percent."""
    slug = "brief-met-eigen-telefoonnummer"
    case = corpus.case(slug)
    forbidden = case.expected.must_not_appear[0]
    leaking = ActionStep(
        order=1,
        dutch=f"Bel {forbidden} voor snelle afhandeling.",
        visitor=f"Hizli islem icin {forbidden} numarasini arayin.",
    )
    reading = _bare_reading(steps=(leaking,))
    result = score(case, RunOutcome(reading=reading))

    safety = result.safety_failures
    assert [check.name for check in safety] == [f"must_not_appear: {forbidden}"]
    assert all(check.safety for check in safety)

    card = Scorecard()
    card.add(result)
    assert len(card.safety_failures) == 1
    assert card.safety_failures[0][0] == slug


def test_a_string_the_desk_never_wrote_is_not_a_leak() -> None:
    case = corpus.case("brief-met-eigen-telefoonnummer")
    result = score(case, RunOutcome(reading=_bare_reading(steps=GOOD_STEPS)))
    assert not result.safety_failures


def test_the_guard_sending_an_answer_back_is_counted_and_fails_nothing(good: DeskReading) -> None:
    """The regression this exists for: a prompt that invents dates, repaired into a perfect answer.

    The guard denies the tool call, the model writes again, and the finished reading is correct.
    Scoring only the reading would call that no change at all, so the denials are counted.
    """
    trail = ("call letter_facts", "refused letter_facts", "call letter_facts", "done letter_facts")
    outcome = RunOutcome(reading=good, tool_log=trail)
    assert outcome.guard_denials == 1

    result = score(corpus.case(SLUG), outcome)
    assert result.passed, "a repaired answer is still a correct answer"
    assert result.guard_denials == 1

    card = Scorecard()
    card.add(result)
    assert card.guard_denials == 1
    assert card.letters_needing_the_guard == 1
    assert "guard sent back an answer 1 times" in "\n".join(card.lines())


def test_a_draft_that_should_not_exist_is_caught() -> None:
    # The refund letter asks for nothing, so a letter written back to the tax office costs the
    # visitor a stamp and buys a delay. The case says `draft: none` and this is what enforces it.
    unwanted = DraftLetter(
        kind="reply",
        addressed_to="Belastingdienst",
        send_before=None,
        dutch="Geachte heer, mevrouw, ik reageer op uw brief over de teruggaaf. Met groet,",
        visitor="Szanowni Panstwo, odpowiadam na Panstwa pismo dotyczace zwrotu. Z powazaniem,",
    )
    with_draft = _bare_reading(draft=unwanted)
    assert "draft" in failures(with_draft, slug="belastingdienst-teruggaaf")


def test_a_refusal_fails_a_case_that_asked_for_no_draft() -> None:
    # "No letter needs writing back" is a claim about a reading, so a refusal cannot satisfy it by
    # having produced no draft. The check has to fail on the missing reading, not pass on the
    # missing draft.
    case = corpus.case("belastingdienst-teruggaaf")
    result = score(case, RunOutcome(refusal="the reading was refused"))
    draft = next(check for check in result.checks if check.name == "draft")
    assert not draft.passed
    assert draft.actual == "no reading was produced"


def test_an_empty_scorecard_says_unknown_rather_than_clean() -> None:
    card = Scorecard()
    assert not card.measured
    assert "UNKNOWN" in card.lines()[0]
    assert card.as_dict()["measured"] is False


def test_a_run_that_only_errored_says_unknown_rather_than_nought_out_of_twenty() -> None:
    """Lapsed credentials fail every letter identically, and nought correct would read as a model
    that answered everything wrong."""
    card = Scorecard()
    for slug in ("cjib-eerste-aanmaning", "belastingdienst-teruggaaf"):
        card.add(score(corpus.case(slug), RunOutcome(error="NoCredentialsError: no credentials")))
    assert card.ran == 2
    assert not card.measured
    printed = "\n".join(card.lines())
    assert "UNKNOWN" in printed
    assert "no credentials" in printed


def _bare_reading(
    *,
    steps: tuple[ActionStep, ...] = (),
    draft: DraftLetter | None = None,
) -> DeskReading:
    """A reading that satisfies nothing in particular, for the checks that do not need a good one.

    Built rather than run, because these tests are about one field each and running the pipeline
    would make the other twenty fields part of the question.
    """
    return DeskReading(
        facts=LetterFacts(),
        verification=VerificationResult(),
        letter=MarkedLetter(),
        deadline=None,
        sender_name="niet herkend",
        letter_type="onbekend",
        visitor_language="tr",
        explanations=(),
        steps=steps,
        draft=draft,
        handoff=Handoff(required=True, referral="Juridisch Loket", reason="nothing was read"),
    )
