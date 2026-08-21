from datetime import date

import pytest

from plainletter.demo import (
    sample_input,
    sample_names,
    sample_text,
    scripted_model,
    scripted_reading,
)
from plainletter.kb import get_sender, known_sender_ids
from plainletter.pipeline import Pipeline
from plainletter.render import desk_card_html, reminder_ics
from plainletter.schemas import DeskReading

TODAY = date(2026, 8, 21)

SYNTHETIC_MARKER = "verzonnen voorbeeldbrief"


def run(name: str) -> DeskReading:
    reading = scripted_reading(name)
    return Pipeline(model=scripted_model(name)).run(
        sample_input(name), visitor_language=reading.visitor_language, today=TODAY
    )


def test_the_sample_set_is_the_size_the_phase_asked_for() -> None:
    assert 8 <= len(sample_names()) <= 12


def test_the_samples_cover_every_sender_in_the_knowledge_base() -> None:
    covered = {scripted_reading(name).facts.sender_id for name in sample_names()}
    assert covered == set(known_sender_ids())


@pytest.mark.parametrize("name", sample_names())
def test_every_sample_letter_says_in_the_letter_that_it_is_invented(name: str) -> None:
    assert SYNTHETIC_MARKER in sample_text(name)


@pytest.mark.parametrize("name", sample_names())
def test_every_sample_letter_reads_end_to_end(name: str) -> None:
    reading = run(name)
    assert reading.verification.issues == ()
    assert reading.verification.is_grounded
    assert reading.steps
    assert reading.deadline is not None


@pytest.mark.parametrize("name", sample_names())
def test_every_sample_is_explained_in_dutch_and_in_the_visitors_language(name: str) -> None:
    reading = run(name)
    languages = {item.language for item in reading.explanations}
    assert "nl" in languages
    assert reading.visitor_language in languages


@pytest.mark.parametrize("name", sample_names())
def test_every_sample_prints_a_card_and_a_reminder(name: str) -> None:
    reading = run(name)
    card = desk_card_html(reading, TODAY)
    assert reading.sender_name in card
    assert "BEGIN:VCALENDAR" in reminder_ics(reading, uid=f"{name}@plainletter")


@pytest.mark.parametrize("name", sample_names())
def test_a_sample_from_an_unverified_sender_is_always_handed_to_a_person(name: str) -> None:
    reading = run(name)
    sender = get_sender(scripted_reading(name).facts.sender_id)
    assert sender is not None
    assert reading.handoff.required is not sender.verified


@pytest.mark.parametrize("name", sample_names())
def test_every_step_route_comes_from_the_knowledge_base(name: str) -> None:
    reading = run(name)
    sender = get_sender(scripted_reading(name).facts.sender_id)
    assert sender is not None
    allowed = set(sender.sources()) | {
        referral.website for referral in sender.referrals if referral.website
    }
    for step in reading.steps:
        assert step.official_route is None or step.official_route in allowed
