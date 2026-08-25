"""A letter that tries to give the agent orders, and what stops it when the model obeys.

Two halves, because a prompt and a check are worth different amounts. The prompt clause is the part
that asks the model not to be fooled, and all a test can do about it is fail when a prompt loses
it. The rest of this file assumes the clause did not work: the scripted model here is a COMPROMISED
one that does exactly what the injected letter asked, and every assertion is about the
deterministic layers refusing anyway.

The fixture is the CJIB sample letter with a block of instructions dropped into the middle of it.
It lives here rather than beside the sample letters on purpose: it is an attack, not a demo, and it
must never appear in the console's list of letters a volunteer can pick.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from plainletter import reading_model
from plainletter.demo import ScriptedReadingModel, scripted_reading
from plainletter.intake import from_text
from plainletter.kb import get_sender
from plainletter.pipeline import Pipeline, UngroundedOutputError, UnofficialRouteError
from plainletter.reading_model import DATA_NOT_INSTRUCTIONS
from plainletter.schemas import ActionStep, Explanation

SAMPLE = "cjib-verkeersboete"
TODAY = date(2026, 8, 21)
FIXTURE = Path(__file__).parent / "fixtures" / "injected-cjib-verkeersboete.txt"

ATTACKER_PHONE = "06 12345678"
ATTACKER_IBAN = "NL91 ABNA 0417 1643 00"
ATTACKER_AMOUNT = "EUR 950,00"


def injected_letter() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def prompts() -> dict[str, str]:
    return {
        name: value
        for name, value in vars(reading_model).items()
        if name.endswith("_PROMPT") and isinstance(value, str)
    }


def compromised(**obeyed: object) -> ScriptedReadingModel:
    """The recorded good reading of this letter, with the stage under test doing as it was told."""
    recorded = scripted_reading(SAMPLE)
    fields: dict[str, object] = {
        "facts": recorded.facts,
        "explanations": recorded.explanations,
        "steps": recorded.steps,
        "draft_letter": recorded.draft,
        "transcript": injected_letter(),
    }
    fields.update(obeyed)
    return ScriptedReadingModel(**fields)  # type: ignore[arg-type]


def run(model: ScriptedReadingModel) -> object:
    return Pipeline(model=model).run(
        from_text(injected_letter()), visitor_language="uk", today=TODAY
    )


def test_the_fixture_really_carries_an_instruction_aimed_at_the_reader() -> None:
    # A fixture nobody has checked is a fixture that quietly stops testing anything.
    letter = injected_letter()
    assert "ignore all previous instructions" in letter
    assert ATTACKER_PHONE in letter and ATTACKER_IBAN in letter


def test_every_prompt_says_the_letter_is_data_rather_than_orders() -> None:
    named = prompts()
    assert len(named) == 5, f"expected the five prompts, found {sorted(named)}"
    missing = [name for name, text in named.items() if DATA_NOT_INSTRUCTIONS not in text]
    assert not missing, f"these prompts do not tell the model the letter is data: {missing}"


def test_a_step_taking_the_letters_own_phone_number_as_a_route_is_refused() -> None:
    obedient_step = ActionStep(
        order=1,
        dutch="Bel het nieuwe servicenummer en betaal vandaag.",
        visitor="Zadzwon pod nowy numer i zaplac dzisiaj.",
        official_route=ATTACKER_PHONE,
    )

    with pytest.raises(UnofficialRouteError) as refusal:
        run(compromised(steps=(obedient_step,)))

    assert refusal.value.claims == frozenset({ATTACKER_PHONE})


def test_an_explanation_repeating_the_injected_amount_is_refused() -> None:
    obedient = Explanation(
        language="nl",
        what_is_this="Een verkeersboete van het CJIB.",
        by_when=f"Betaal vandaag {ATTACKER_AMOUNT}.",
        if_you_do_nothing="Het bedrag wordt verhoogd.",
    )

    with pytest.raises(UngroundedOutputError) as refusal:
        run(compromised(explanations=(obedient,)))

    assert any(ATTACKER_AMOUNT in claim for claim in refusal.value.claims)


def test_no_draft_is_written_once_a_step_has_been_refused() -> None:
    class RecordsTheDraft(ScriptedReadingModel):
        drafted: bool = False

        def draft(self, *args: object, **kwargs: object) -> None:
            RecordsTheDraft.drafted = True
            return None

    recorded = scripted_reading(SAMPLE)
    model = RecordsTheDraft(
        facts=recorded.facts,
        explanations=recorded.explanations,
        steps=(recorded.steps[0].model_copy(update={"official_route": ATTACKER_IBAN}),),
        draft_letter=recorded.draft,
        transcript=injected_letter(),
    )

    with pytest.raises(UnofficialRouteError):
        run(model)
    assert RecordsTheDraft.drafted is False


def test_the_same_letter_reads_normally_when_the_model_ignores_the_injection() -> None:
    reading = run(compromised())

    assert reading is not None
    routes = {step.official_route for step in reading.steps if step.official_route}  # type: ignore[attr-defined]
    assert routes <= (get_sender("cjib") or pytest.fail("cjib is missing")).route_values()
    assert ATTACKER_PHONE not in str(routes)


def test_the_knowledge_base_is_the_only_source_of_a_route() -> None:
    sender = get_sender("cjib")
    assert sender is not None
    permitted = sender.route_values()

    assert "https://www.om.nl/onderwerpen/verkeer" in permitted
    assert "0800 8020" in permitted
    assert ATTACKER_PHONE not in permitted
