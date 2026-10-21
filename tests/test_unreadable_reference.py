"""A reference the reading could only partly read is never quoted as if it could be used.

The fixture is the parking-tax sample with part of its assessment number typed as unreadable, the
way the transcription writes a gap, and the scripted reading quoting the partial number the way the
deployed planner and drafter did: in the payment step, in the objection draft, and through them in
the card and the reminder.
"""

from __future__ import annotations

from datetime import date

from icalendar import Calendar

from plainletter.demo import ScriptedReadingModel, sample_text, scripted_reading
from plainletter.gaps import fill_gaps, steps_without_gaps
from plainletter.intake import from_text
from plainletter.locales import active
from plainletter.pipeline import Pipeline
from plainletter.reading_model import TRANSCRIBE_PROMPT
from plainletter.render import desk_card_html, reminder_ics, reminder_uid
from plainletter.schemas import DeskReading, Unreadable

SAMPLE = "gemeente-parkeerboete"
TODAY = date(2026, 8, 21)
READABLE = "NP 4471 2208"
PARTIAL = "NP 4471 [onleesbaar] 8"
# The word the deployed planner wrote for the gap in the Ukrainian steps and draft of the capture
# under examples/unreadable-reference, in place of [onleesbaar].
UKRAINIAN_MARKER = "[\u043d\u0435\u0440\u043e\u0437\u0431\u0456\u0440\u043b\u0438\u0432\u043e]"


def _gapped(text: str, marker: str = "[onleesbaar]") -> str:
    return text.replace(READABLE, PARTIAL.replace("[onleesbaar]", marker))


def _run(*, gapped: bool, visitor_marker: str = "[onleesbaar]") -> DeskReading:
    reading = scripted_reading(SAMPLE)
    facts, steps, draft = reading.facts, reading.steps, reading.draft
    text = sample_text(SAMPLE)
    if gapped:
        assert facts.reference is not None and draft is not None
        text = _gapped(text)
        reference = facts.reference.model_copy(
            update={
                "value": _gapped(facts.reference.value),
                "source": facts.reference.source.model_copy(
                    update={"text": _gapped(facts.reference.source.text)}
                ),
            }
        )
        facts = facts.model_copy(
            update={
                "reference": reference,
                "unreadable": (
                    Unreadable(
                        field="Aanslagnummer (volledig)",
                        reason="Een deel van het aanslagnummer is onleesbaar.",
                        ask_the_visitor="Kunt u het volledige aanslagnummer laten zien?",
                    ),
                ),
            }
        )
        steps = tuple(
            step.model_copy(
                update={
                    "dutch": _gapped(step.dutch),
                    "visitor": _gapped(step.visitor, visitor_marker),
                }
            )
            for step in steps
        )
        draft = draft.model_copy(
            update={
                "dutch": _gapped(draft.dutch),
                "visitor": _gapped(draft.visitor, visitor_marker),
            }
        )
    model = ScriptedReadingModel(
        facts=facts,
        explanations=reading.explanations,
        steps=steps,
        draft_letter=draft,
        transcript=text,
    )
    return Pipeline(model=model).run(
        from_text(text), visitor_language=reading.visitor_language, today=TODAY
    )


def _quoted(card: str) -> str:
    """The card without its key: the key prints the letter's own lines, gap and all, as the letter
    shows them, which is the one place the gap is meant to be seen."""
    return card.split('<div class="keys">')[0]


def _description(ics: str) -> str:
    event = next(iter(Calendar.from_ical(ics).walk("VEVENT")))
    return str(event["description"])


def test_a_partly_read_reference_is_quoted_nowhere_a_payment_or_a_letter_leaves_from() -> None:
    reading = _run(gapped=True)
    words = active().words
    assert reading.facts.reference is not None
    assert reading.facts.reference.value == PARTIAL

    # The payment step asks for the whole number first instead of quoting the part.
    pay = reading.steps[0]
    for text in (pay.dutch, pay.visitor):
        assert "[onleesbaar]" not in text
        assert "4471" not in text
        assert words.unreadable_in_step in text
    assert pay.dutch.startswith(words.unreadable_step_lead)
    assert "Betaal EUR 83,00" in pay.dutch

    # The draft leaves a marked place for the whole number.
    assert reading.draft is not None
    for text in (reading.draft.dutch, reading.draft.visitor):
        assert "[onleesbaar]" not in text
        assert "4471" not in text
        assert words.unreadable_in_draft in text

    card = _quoted(desk_card_html(reading, TODAY))
    assert "[onleesbaar]" not in card
    assert "4471" not in card
    assert words.reference_unreadable in card

    uid = reminder_uid(reading)
    ics = reminder_ics(reading, uid=uid)
    assert "[onleesbaar]" not in ics
    assert "4471" not in ics
    assert words.reference_unreadable in _description(ics).replace("\n", "")
    assert uid.endswith("@plainletter")
    assert "[" not in uid and " " not in uid
    # Stable: the same letter read again gives the same reminder.
    assert reminder_uid(_run(gapped=True)) == uid
    # And it does not hang on how the gap happened to be written.
    reference = reading.facts.reference.model_copy(update={"value": "NP4471[onleesbaar]8"})
    grounded = tuple(
        fact.model_copy(update={"display": reference.value}) if fact.name == "reference" else fact
        for fact in reading.verification.grounded
    )
    assert any(fact.name == "reference" for fact in grounded)
    rewritten = reading.model_copy(
        update={
            "facts": reading.facts.model_copy(update={"reference": reference}),
            "verification": reading.verification.model_copy(update={"grounded": grounded}),
        }
    )
    assert reminder_uid(rewritten) == uid


def test_the_card_and_reminder_hold_a_stored_reading_that_still_quotes_the_gap() -> None:
    # A reading kept from before the pipeline took gaps out still carries them in its steps. What
    # the visitor takes home must not.
    reading = _run(gapped=True)
    raw = scripted_reading(SAMPLE).steps
    stored = reading.model_copy(
        update={
            "steps": tuple(
                step.model_copy(
                    update={"dutch": _gapped(step.dutch), "visitor": _gapped(step.visitor)}
                )
                for step in raw
            )
        }
    )
    assert "4471" not in _quoted(desk_card_html(stored, TODAY))
    assert "4471" not in reminder_ics(stored, uid=reminder_uid(stored))


def test_a_translated_marker_in_the_visitor_text_is_caught_too() -> None:
    # The visitor-language text of the capture carries the gap in Ukrainian, not as [onleesbaar].
    reading = _run(gapped=True, visitor_marker=UKRAINIAN_MARKER)
    words = active().words
    pay = reading.steps[0]
    assert "4471" not in pay.visitor
    assert UKRAINIAN_MARKER not in pay.visitor
    assert words.unreadable_in_step in pay.visitor
    assert reading.draft is not None
    assert "4471" not in reading.draft.visitor
    assert words.unreadable_in_draft in reading.draft.visitor
    assert "4471" not in _quoted(desk_card_html(reading, TODAY))


def test_a_partial_value_with_too_little_read_never_matches_ordinary_text() -> None:
    # One digit read is too little to find a translated gap by: the count of days beside a
    # bracket has to stay as it is.
    text = "Nog (zeer urgent) 6 dagen."
    assert fill_gaps(text, "[nummer]", "[onleesbaar] 6") == text


def test_two_letters_that_differ_only_in_the_part_read_get_two_reminders() -> None:
    # Two fines from one sender on one day for one amount differ only in their numbers, and a
    # calendar treats two events with one UID as one.
    reading = _run(gapped=True)
    assert reading.facts.reference is not None
    other = "NP 4472 [onleesbaar] 8"
    grounded = tuple(
        fact.model_copy(update={"display": other}) if fact.name == "reference" else fact
        for fact in reading.verification.grounded
    )
    second = reading.model_copy(
        update={
            "facts": reading.facts.model_copy(
                update={"reference": reading.facts.reference.model_copy(update={"value": other})}
            ),
            "verification": reading.verification.model_copy(update={"grounded": grounded}),
        }
    )
    assert reminder_uid(second) != reminder_uid(reading)


def test_other_unreadable_words_are_not_taken_for_the_reference() -> None:
    # The transcription writes the same marker for any word it could not read. A number plate or a
    # street name with a gap is not the reference, whether the reference was read whole or not.
    step = (
        scripted_reading(SAMPLE)
        .steps[0]
        .model_copy(
            update={
                "dutch": "Controleer kenteken 30-[onleesbaar]-7 en het adres [onleesbaar].",
                "visitor": "Check plate 30-[onleesbaar]-7 and the address [onleesbaar].",
            }
        )
    )
    for partial in (READABLE, None, PARTIAL):
        assert steps_without_gaps((step,), partial) == (step,)
    # A part of the partly read reference is still taken out where a step quotes only that part.
    placeholder = active().words.unreadable_in_step
    assert fill_gaps("met kenmerk 4471 [onleesbaar] 8.", placeholder, PARTIAL) == (
        f"met kenmerk {placeholder}."
    )


def test_the_marker_looked_for_is_the_one_the_transcription_writes() -> None:
    # The transcription prompt asks for the marker and the writing stages look for it. If the two
    # ever differ, every gap passes through unseen and no other test notices.
    assert active().words.unreadable_marker in TRANSCRIBE_PROMPT


def test_a_fully_read_reference_is_quoted_exactly_as_before() -> None:
    reading = _run(gapped=False)
    expected = scripted_reading(SAMPLE)
    assert reading.steps == expected.steps
    assert reading.draft == expected.draft
    assert "Betaal EUR 83,00 met aanslagnummer NP 4471 2208." in reading.steps[0].dutch

    card = desk_card_html(reading, TODAY)
    assert "Kenmerk NP 4471 2208" in card
    assert active().words.reference_unreadable not in card

    uid = reminder_uid(reading)
    assert uid == "NP44712208@plainletter"
    ics = reminder_ics(reading, uid=uid)
    assert "UID:NP44712208@plainletter" in ics
    assert active().words.reference_unreadable not in _description(ics).replace("\n", "")
