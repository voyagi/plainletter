from datetime import date

import pytest
from pydantic import ValidationError

from plainletter.schemas import ActionStep, DraftLetter, Explanation, SourceSpan, Unreadable

EM_DASH = chr(0x2014)
EN_DASH = chr(0x2013)

A_LETTER = (
    "Geachte heer, mevrouw,\n\nHierbij maak ik bezwaar tegen de beschikking met kenmerk "
    "8194 5523 7761.\n\nMet vriendelijke groet,"
)


def test_a_dash_a_model_wrote_becomes_a_hyphen_before_anything_prints() -> None:
    step = ActionStep(
        order=1,
        dutch=f"Dit is een juridische stap {EM_DASH} verwijs door.",
        visitor=f"Якщо так {EM_DASH} перейдіть до кроку 2, termijn{EN_DASH}zes weken.",
    )
    assert step.dutch == "Dit is een juridische stap - verwijs door."
    assert step.visitor == "Якщо так - перейдіть до кроку 2, termijn - zes weken."


def test_the_rule_covers_every_text_a_model_writes_for_a_reader() -> None:
    explanation = Explanation(
        language="nl",
        what_is_this=f"Een boete {EM_DASH} van het CJIB.",
        by_when=f"Voor 15 september 2026 {EN_DASH} niet later.",
        if_you_do_nothing=f"Verhoging {EM_DASH} met 50 procent.",
    )
    gap = Unreadable(
        field="kenteken",
        reason=f"onscherp {EM_DASH} schaduw",
        ask_the_visitor=f"Vraag {EM_DASH} na.",
    )
    assert EM_DASH not in explanation.model_dump_json()
    assert EN_DASH not in explanation.model_dump_json()
    assert gap.reason == "onscherp - schaduw"


def test_a_passage_quoted_from_the_letter_is_never_rewritten() -> None:
    # The letter is the ground truth. A dash on the page stays a dash, or the passage would no
    # longer match the page it was copied from.
    span = SourceSpan(page=1, text=f"Betaal {EN_DASH} voor 15 september 2026.")
    assert EN_DASH in span.text


def test_a_language_tag_is_not_a_translated_letter() -> None:
    # The first live drafting turn filled the translation with "uk". The model retries on a
    # validation error, so refusing it here is what makes the second attempt a letter.
    with pytest.raises(ValidationError) as refused:
        DraftLetter(
            kind="objection",
            addressed_to="officier van justitie",
            send_before=date(2026, 9, 15),
            dutch=A_LETTER,
            visitor="uk",
        )
    assert "visitor" in str(refused.value)


def test_the_draft_schema_tells_the_model_what_each_text_is() -> None:
    properties = DraftLetter.model_json_schema()["properties"]
    assert "translated" in properties["visitor"]["description"]
    assert "Dutch" in properties["dutch"]["description"]
    assert properties["visitor"]["minLength"] == properties["dutch"]["minLength"]


def test_a_whole_letter_in_both_languages_is_accepted() -> None:
    draft = DraftLetter(
        kind="objection",
        addressed_to="officier van justitie",
        send_before=None,
        dutch=A_LETTER,
        visitor=(
            "Шановні пані та панове,\n\nЦим я подаю заперечення проти постанови з номером "
            "8194 5523 7761.\n\nЗ повагою,"
        ),
    )
    assert draft.visitor.startswith("Шановні")
