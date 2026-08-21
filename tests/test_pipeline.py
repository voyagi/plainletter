from datetime import date

import pytest

from plainletter.demo import ScriptedReadingModel, cjib_model, sample_text
from plainletter.kb import load_senders
from plainletter.pipeline import Pipeline, UngroundedOutputError, handoff_for
from plainletter.schemas import Urgency, VerificationResult
from plainletter.verify import verify

LETTER = sample_text("cjib-verkeersboete")
TODAY = date(2026, 8, 21)


def run(model: ScriptedReadingModel = None) -> object:  # type: ignore[assignment]
    return Pipeline(model=model or cjib_model()).run(
        LETTER, LETTER, visitor_language="ar", today=TODAY
    )


def test_a_sample_letter_goes_through_end_to_end() -> None:
    reading = run()
    assert reading.sender_name == "Centraal Justitieel Incassobureau"
    assert reading.deadline is not None
    assert reading.deadline.on == date(2026, 9, 15)
    assert reading.deadline.days_left == 25
    assert reading.deadline.urgency is Urgency.AMPLE
    assert reading.deadline.post_by == date(2026, 9, 8)
    assert len(reading.steps) == 3
    assert reading.draft is not None
    assert not reading.handoff.required


def test_the_unreadable_field_survives_to_the_desk_instead_of_being_filled_in() -> None:
    reading = run()
    assert [item.field for item in reading.facts.unreadable] == ["kenteken"]


def test_an_invented_deadline_in_the_explanation_stops_the_whole_reading() -> None:
    model = cjib_model()
    nl = model.explanations[0]
    poisoned = ScriptedReadingModel(
        facts=model.facts,
        explanations=(
            nl.model_copy(update={"by_when": "Betaal voor 1 oktober 2026."}),
            *model.explanations[1:],
        ),
        steps=model.steps,
        draft_letter=model.draft_letter,
    )
    with pytest.raises(UngroundedOutputError) as refused:
        run(poisoned)
    assert "1 oktober 2026" in refused.value.claims


def test_an_invented_amount_in_a_step_stops_the_whole_reading() -> None:
    model = cjib_model()
    first = model.steps[0]
    poisoned = ScriptedReadingModel(
        facts=model.facts,
        explanations=model.explanations,
        steps=(first.model_copy(update={"dutch": "Betaal EUR 999,00."}), *model.steps[1:]),
        draft_letter=model.draft_letter,
    )
    with pytest.raises(UngroundedOutputError):
        run(poisoned)


def _broken_deadline_model() -> ScriptedReadingModel:
    """A reading whose deadline cites a passage that says something else."""
    model = cjib_model()
    facts = model.facts
    assert facts.deadline is not None
    return ScriptedReadingModel(
        facts=facts.model_copy(
            update={"deadline": facts.deadline.model_copy(update={"day": 1, "month": 10})}
        ),
        explanations=model.explanations,
        steps=model.steps,
        draft_letter=None,
    )


def test_a_failed_check_stops_the_output_that_still_quotes_the_date() -> None:
    with pytest.raises(UngroundedOutputError) as refused:
        run(_broken_deadline_model())
    assert "15 september 2026" in refused.value.claims


def test_a_deadline_that_did_not_check_out_never_reaches_the_desk() -> None:
    # Same broken reading, but with output that does not quote any date. The deadline is dropped
    # rather than shown, because only a checked one counts.
    broken = _broken_deadline_model()
    quiet = ScriptedReadingModel(
        facts=broken.facts,
        explanations=tuple(
            item.model_copy(
                update={
                    "by_when": "De brief noemt een datum die niet gecontroleerd kon worden.",
                    "what_is_this": "Een brief van het CJIB.",
                    "if_you_do_nothing": "Het bedrag kan hoger worden.",
                }
            )
            for item in broken.explanations
        ),
        steps=(),
        draft_letter=None,
    )
    reading = Pipeline(model=quiet).run(LETTER, LETTER, visitor_language="ar", today=TODAY)
    assert reading.deadline is None
    assert reading.handoff.required


def test_an_unverified_sender_is_handed_to_a_person() -> None:
    result = verify(cjib_model().facts, LETTER)
    handoff = handoff_for(result, load_senders()["ind"])
    assert handoff.required
    assert "lawyer" in handoff.reason or "VluchtelingenWerk" in handoff.reason


def test_a_sender_outside_the_knowledge_base_is_handed_to_a_person() -> None:
    handoff = handoff_for(VerificationResult(), None)
    assert handoff.required
