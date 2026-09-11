"""What the drafting stage actually hands the model, on the path the deployed service runs.

`test_draft_remedy.py` reads fixed sample answers and the instruction's own text. Neither shows
that the instruction reaches a model at all, and a corrected instruction nothing sends is worth
nothing. `test_draft_remedy_live.py` shows the whole thing end to end but costs money, so it is opt
in.

This sits between them. It drives `BedrockReadingModel.draft`, the same object the runtime uses,
with a scripted model in place of Bedrock, and reads back every word the drafting stage put in
front of it. No model is called, so it runs in the ordinary suite.

Two things were leaning the draft towards an objection whatever the letter said: the instruction
asked for "the decision being objected to", and the prompt labelled the letter's own challenge
paragraph "Objection route in the letter", on a letter that offers an appeal.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterable
from typing import Any

from plainletter.bedrock import BedrockReadingModel
from plainletter.demo import scripted_reading
from plainletter.kb import load_senders
from plainletter.schemas import LetterFacts
from scripted_strands import ScriptedModel, tool_use

SAMPLE = "cjib-verkeersboete"
FACTS: LetterFacts = scripted_reading(SAMPLE).facts
GROUNDED = {"total_amount": "EUR 174,00", "deadline": "15 september 2026"}
VISITOR_LANGUAGE = "tr"
# Only long enough to be a letter. What this file reads is what went to the model, not what came
# back, and a Latin-script stand-in keeps the fixture out of the lint's ambiguous-character rule.
LETTER_BODY = (
    "Geachte officier van justitie,\n\nIk stel beroep in tegen beschikking 8194 5523 7761.\n"
    "Mijn auto stond die dag niet op de Boezemweg.\n\nMet vriendelijke groet,"
)
VISITOR_BODY = (
    "Sayin savci,\n\n8194 5523 7761 numarali karara itiraz ediyorum.\n"
    "Arabam o gun Boezemweg caddesinde degildi.\n\nSaygilarimla,"
)


class RecordingModel(ScriptedModel):
    """The scripted model, plus the system prompt it was given, which the base class drops."""

    def __init__(self, turns: list[list[dict[str, Any]]]) -> None:
        super().__init__(turns)
        self.system_prompts: list[str] = []

    async def stream(
        self,
        messages: Any,
        tool_specs: list[dict[str, Any]] | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[dict[str, Any]]:
        self.system_prompts.append(system_prompt or "")
        async for event in super().stream(
            messages, tool_specs, system_prompt=system_prompt, **kwargs
        ):
            yield event


def _decision() -> dict[str, Any]:
    letter = {
        "kind": "appeal",
        "addressed_to": "Officier van justitie",
        "send_before": None,
        "dutch": LETTER_BODY,
        "visitor": VISITOR_BODY,
    }
    return tool_use("DraftDecision", "d1", {"needed": True, "letter": letter})


def _run() -> RecordingModel:
    model = RecordingModel([[_decision()]])
    reader = BedrockReadingModel(
        sender_ids=("cjib",), make_model=lambda model_id, region, max_tokens: model
    )
    draft = reader.draft(FACTS, GROUNDED, load_senders()["cjib"], visitor_language=VISITOR_LANGUAGE)
    assert draft is not None and draft.kind == "appeal"
    return model


def _flat(text: str) -> str:
    # Wrapped prose: a phrase the text really carries can sit either side of a line break.
    return " ".join(text.split()).casefold()


def test_the_drafting_stage_hands_the_model_the_remedy_rule() -> None:
    model = _run()
    assert model.system_prompts, "the drafting stage reached the model with no instruction at all"
    instruction = _flat(model.system_prompts[0])
    assert "the decision being objected to" not in instruction
    assert 'kind to "appeal" for a beroep' in instruction
    assert '"objection" for a bezwaar' in instruction


def test_the_drafting_prompt_does_not_call_the_letters_own_paragraph_an_objection() -> None:
    model = _run()
    asked = _flat(json.dumps(model.requests[0]["messages"], ensure_ascii=False))
    assert "objection route in the letter" not in asked, (
        "the prompt names one of the two remedies while handing over a paragraph offering the other"
    )
    assert "how the letter says to challenge it" in asked, (
        "the letter's own challenge paragraph is no longer handed to the drafting stage"
    )
