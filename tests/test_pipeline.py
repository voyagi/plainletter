from datetime import date

import pytest

from plainletter import urgency
from plainletter.demo import ScriptedReadingModel, sample_input, sample_text, scripted_model
from plainletter.kb import load_senders
from plainletter.pipeline import (
    POST_BY,
    Pipeline,
    UngroundedOutputError,
    handoff_for,
    usable_values,
)
from plainletter.schemas import Urgency, VerificationResult
from plainletter.verify import verify

SAMPLE = "cjib-verkeersboete"
LETTER = sample_input(SAMPLE)
TODAY = date(2026, 8, 21)


def cjib_model() -> ScriptedReadingModel:
    return scripted_model(SAMPLE)


def run(model: ScriptedReadingModel = None) -> object:  # type: ignore[assignment]
    return Pipeline(model=model or cjib_model()).run(LETTER, visitor_language="uk", today=TODAY)


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


def test_an_invented_deadline_is_refused_before_the_stage_carrying_it_is_sent() -> None:
    # Streaming puts a stage on the volunteer's screen the instant it is sent, so the check has to
    # happen before the send. Checking everything at the end would show the invented date and then
    # take it back.
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
    stages = Pipeline(model=poisoned).stages(LETTER, visitor_language="uk", today=TODAY)
    sent = []
    with pytest.raises(UngroundedOutputError):
        for progress in stages:
            sent.append(progress.stage)
    assert sent == ["facts", "letter", "deadline"]


def test_the_stages_and_the_finished_reading_never_disagree() -> None:
    merged: dict[str, object] = {}
    stages = Pipeline(model=cjib_model()).stages(LETTER, visitor_language="uk", today=TODAY)
    while True:
        try:
            progress = next(stages)
        except StopIteration as finished:
            reading = finished.value
            break
        dumped = progress.model_dump()
        merged.update(
            {
                key: value
                for key, value in dumped.items()
                if key in progress.model_fields_set and key != "stage"
            }
        )
    assert merged == reading.model_dump()


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
    reading = Pipeline(model=quiet).run(LETTER, visitor_language="uk", today=TODAY)
    assert reading.deadline is None
    assert reading.handoff.required


def _usable(model: ScriptedReadingModel | None = None) -> dict[str, str]:
    model = model or cjib_model()
    result = verify(model.facts, sample_text(SAMPLE))
    deadline = urgency.view(date(2026, 9, 15), TODAY)
    return usable_values(model.facts, result, deadline)


def test_the_writing_stages_are_told_what_each_amount_and_date_is_for() -> None:
    # A bare `line_amount_2: EUR 9,00` made the first live planner guess what the money was for.
    usable = _usable()
    assert usable["total_amount (Totaal te betalen)"] == "EUR 174,00"
    assert usable["line_amount_2 (Administratiekosten)"] == "EUR 9,00"
    assert usable["deadline"] == "15 september 2026"

    ind = scripted_model("ind-verlenging")
    dated = usable_values(ind.facts, verify(ind.facts, sample_text("ind-verlenging")), None)
    assert dated["other_date_1 (laatste dag dat de verblijfsvergunning geldig is)"] == (
        "1 december 2026"
    )


def test_the_posting_date_the_calendar_computed_may_be_repeated() -> None:
    usable = _usable()
    assert usable[POST_BY] == "8 september 2026"
    model = cjib_model()
    first = model.steps[0]
    posting = ScriptedReadingModel(
        facts=model.facts,
        explanations=model.explanations,
        steps=(
            first.model_copy(update={"dutch": "Post de brief uiterlijk 8 september 2026."}),
            *model.steps[1:],
        ),
        draft_letter=model.draft_letter,
    )
    reading = run(posting)
    assert "8 september 2026" in reading.steps[0].dutch


def test_a_posting_date_the_calendar_did_not_compute_is_still_refused() -> None:
    model = cjib_model()
    first = model.steps[0]
    invented = ScriptedReadingModel(
        facts=model.facts,
        explanations=model.explanations,
        steps=(
            first.model_copy(update={"dutch": "Post de brief uiterlijk 9 september 2026."}),
            *model.steps[1:],
        ),
        draft_letter=model.draft_letter,
    )
    with pytest.raises(UngroundedOutputError) as refused:
        run(invented)
    assert refused.value.claims == {"9 september 2026"}


def test_without_a_deadline_there_is_no_posting_date_to_repeat() -> None:
    model = cjib_model()
    result = verify(model.facts, sample_text(SAMPLE))
    assert POST_BY not in usable_values(model.facts, result, None)


def test_an_unverified_sender_is_handed_to_a_person() -> None:
    result = verify(cjib_model().facts, sample_text(SAMPLE))
    handoff = handoff_for(result, load_senders()["ind"])
    assert handoff.required
    assert "lawyer" in handoff.reason or "VluchtelingenWerk" in handoff.reason


def test_a_sender_outside_the_knowledge_base_is_handed_to_a_person() -> None:
    handoff = handoff_for(VerificationResult(), None)
    assert handoff.required


def _with_draft_send_before(when: date | None) -> ScriptedReadingModel:
    model = cjib_model()
    assert model.draft_letter is not None
    return ScriptedReadingModel(
        facts=model.facts,
        explanations=model.explanations,
        steps=model.steps,
        draft_letter=model.draft_letter.model_copy(update={"send_before": when}),
    )


def test_a_posting_day_the_draft_invented_refuses_the_reading() -> None:
    # send_before is a date field rather than prose, so it reaches the guard inside the tool call
    # as "2026-10-01" and reached this check as nothing at all. It is the day the visitor is told
    # to post by, which makes it exactly the kind of value that has to stand in the letter.
    with pytest.raises(UngroundedOutputError) as refused:
        run(_with_draft_send_before(date(2026, 10, 1)))
    assert refused.value.claims == {"1 oktober 2026"}


def test_control_the_posting_day_the_calendar_computed_goes_through() -> None:
    reading = run(_with_draft_send_before(date(2026, 9, 8)))
    assert reading.draft is not None
    assert reading.draft.send_before == date(2026, 9, 8)


def test_control_a_draft_with_no_posting_day_goes_through() -> None:
    reading = run(_with_draft_send_before(None))
    assert reading.draft is not None
    assert reading.draft.send_before is None
