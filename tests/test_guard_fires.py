"""The guard and the audit trail, proved on the path the product actually runs.

`test_guard.py` calls the guard's decision directly and proves the decision logic. These tests run
a scripted Strands model through the same `BedrockReadingModel` the deployed service uses and prove
the decision is reached at all: that a structured answer is a tool call, that the intervention
refuses an ungrounded one, that the refusal goes back to the model, that the model's rewrite is
what comes out, and that the audit trail saw every step. Each test has a control showing the same
script going through when the guard has no reason to refuse, or when the guard is absent.
"""

from __future__ import annotations

import json
import warnings
from collections.abc import AsyncGenerator, AsyncIterable
from typing import Any

import pytest
from strands import Agent
from strands.models.model import Model

from plainletter.bedrock import ActionPlan, BedrockReadingModel
from plainletter.demo import sample_input, scripted_reading
from plainletter.kb import load_senders
from plainletter.schemas import LetterFacts
from plainletter.tools import official_routes

SAMPLE = "cjib-verkeersboete"
FACTS: LetterFacts = scripted_reading(SAMPLE).facts
GROUNDED = {"total_amount": "EUR 174,00", "deadline": "15 september 2026"}
INVENTED_STEP = "Betaal EUR 174,00 voor 1 oktober 2026."
GROUNDED_STEP = "Betaal EUR 174,00 voor 15 september 2026."
ROUTE = "https://www.cjib.nl/verkeersboete"


class ScriptedModel(Model):
    """A Strands model whose turns are written in advance, one list of content blocks per call.

    It also keeps every request the agent made, so a test can read what the model was offered and
    what it was told.
    """

    def __init__(self, turns: list[list[dict[str, Any]]]) -> None:
        self._turns = list(turns)
        self.requests: list[dict[str, Any]] = []

    def update_config(self, **model_config: Any) -> None:
        return None

    def get_config(self) -> dict[str, Any]:
        return {}

    async def structured_output(
        self, output_model: Any, prompt: Any, system_prompt: str | None = None, **kwargs: Any
    ) -> AsyncGenerator[dict[str, Any], None]:
        raise AssertionError("the deprecated Agent.structured_output path was used")
        yield {}  # pragma: no cover

    async def stream(
        self,
        messages: Any,
        tool_specs: list[dict[str, Any]] | None = None,
        system_prompt: str | None = None,
        *,
        tool_choice: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[dict[str, Any]]:
        self.requests.append(
            {
                "messages": json.loads(json.dumps(messages)),
                "tools": [spec["name"] for spec in tool_specs or []],
                "tool_choice": tool_choice,
            }
        )
        if not self._turns:
            raise AssertionError("the agent asked for more turns than were scripted")
        turn = self._turns.pop(0)
        yield {"messageStart": {"role": "assistant"}}
        for block in turn:
            if "text" in block:
                yield {"contentBlockStart": {"start": {}}}
                yield {"contentBlockDelta": {"delta": {"text": block["text"]}}}
            else:
                use = block["toolUse"]
                start = {"toolUse": {"toolUseId": use["toolUseId"], "name": use["name"]}}
                yield {"contentBlockStart": {"start": start}}
                delta = {"toolUse": {"input": json.dumps(use["input"])}}
                yield {"contentBlockDelta": {"delta": delta}}
            yield {"contentBlockStop": {}}
        stop = "tool_use" if any("toolUse" in block for block in turn) else "end_turn"
        yield {"messageStop": {"stopReason": stop}}
        yield {"metadata": {}}


def tool_use(name: str, tool_use_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"toolUse": {"toolUseId": tool_use_id, "name": name, "input": payload}}


def lookup(tool_use_id: str = "u1") -> dict[str, Any]:
    return tool_use("official_routes", tool_use_id, {"sender_id": "cjib"})


def plan(step: str, tool_use_id: str) -> dict[str, Any]:
    item = {"order": 1, "dutch": step, "visitor": step, "official_route": ROUTE}
    return tool_use("ActionPlan", tool_use_id, {"items": [item]})


def explanation(by_when: str, tool_use_id: str) -> dict[str, Any]:
    item = {
        "language": "nl",
        "what_is_this": "Een verkeersboete van het CJIB.",
        "by_when": by_when,
        "if_you_do_nothing": "Het bedrag wordt verhoogd.",
    }
    return tool_use("Explanations", tool_use_id, {"items": [item]})


def reader_with(model: ScriptedModel) -> BedrockReadingModel:
    return BedrockReadingModel(sender_ids=("cjib",), make_model=lambda model_id, region: model)


def tool_result_text(messages: list[dict[str, Any]], tool_use_id: str) -> str:
    for message in messages:
        for block in message.get("content", []):
            result = block.get("toolResult")
            if result and result["toolUseId"] == tool_use_id:
                return "".join(part.get("text", "") for part in result["content"])
    raise AssertionError(f"the model never saw a result for {tool_use_id}")


def run_plan(reader: BedrockReadingModel) -> list[str]:
    steps = reader.plan(
        FACTS, GROUNDED, load_senders()["cjib"], deadline=None, visitor_language="uk"
    )
    return [step.dutch for step in steps]


def test_an_invented_deadline_in_the_plan_is_refused_and_the_model_writes_again() -> None:
    model = ScriptedModel([[lookup()], [plan(INVENTED_STEP, "u2")], [plan(GROUNDED_STEP, "u3")]])
    reader = reader_with(model)

    assert run_plan(reader) == [GROUNDED_STEP]
    assert reader.audit.entries == [
        "call official_routes",
        "done official_routes",
        "call ActionPlan",
        "refused ActionPlan",
        "call ActionPlan",
        "done ActionPlan",
    ]


def test_the_refusal_reaches_the_model_with_its_reason() -> None:
    model = ScriptedModel([[lookup()], [plan(INVENTED_STEP, "u2")], [plan(GROUNDED_STEP, "u3")]])
    run_plan(reader_with(model))

    seen_by_the_rewrite = tool_result_text(model.requests[2]["messages"], "u2")
    assert seen_by_the_rewrite.startswith("DENIED: Refused: 1 oktober 2026")
    assert "15 september 2026" not in seen_by_the_rewrite


def test_the_route_lookup_is_a_real_tool_call_whose_answer_the_model_reads() -> None:
    model = ScriptedModel([[lookup()], [plan(GROUNDED_STEP, "u2")]])
    run_plan(reader_with(model))

    assert model.requests[0]["tools"] == ["official_routes", "ActionPlan"]
    answer = json.loads(tool_result_text(model.requests[1]["messages"], "u1"))
    assert answer["known"] and answer["verified"]
    assert answer["objection"]["source"].startswith("https://www.om.nl/")


def test_control_the_same_plan_goes_through_once_the_date_is_grounded() -> None:
    model = ScriptedModel([[lookup()], [plan(INVENTED_STEP, "u2")]])
    reader = reader_with(model)
    grounded = {**GROUNDED, "other": "1 oktober 2026"}

    steps = reader.plan(FACTS, grounded, None, deadline=None, visitor_language="uk")
    assert [step.dutch for step in steps] == [INVENTED_STEP]
    assert "refused ActionPlan" not in reader.audit.entries


def test_control_without_the_guard_the_sdk_accepts_the_invented_deadline() -> None:
    model = ScriptedModel([[plan(INVENTED_STEP, "u2")]])
    reader = reader_with(model)
    agent = Agent(
        model=model,
        tools=[official_routes],
        hooks=[reader.audit],
        interventions=[],
        callback_handler=None,
    )

    result = agent("Write the plan.", structured_output_model=ActionPlan)
    assert isinstance(result.structured_output, ActionPlan)
    assert result.structured_output.items[0].dutch == INVENTED_STEP
    assert reader.audit.entries == ["call ActionPlan", "done ActionPlan"]


def test_an_invented_amount_in_the_explanation_is_refused_without_any_other_tool() -> None:
    model = ScriptedModel(
        [
            [explanation("Betaal EUR 999,00 voor 15 september 2026.", "u1")],
            [explanation("Betaal voor 15 september 2026.", "u2")],
        ]
    )
    reader = reader_with(model)

    explanations = reader.explain(FACTS, GROUNDED, ("nl",))
    assert [item.by_when for item in explanations] == ["Betaal voor 15 september 2026."]
    assert model.requests[0]["tools"] == ["Explanations"]
    assert reader.audit.entries == [
        "call Explanations",
        "refused Explanations",
        "call Explanations",
        "done Explanations",
    ]


def test_reading_the_facts_is_a_tool_call_on_the_supported_path() -> None:
    payload = FACTS.model_dump(mode="json", exclude_none=True)
    model = ScriptedModel([[tool_use("LetterFacts", "u1", payload)]])
    reader = reader_with(model)

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        facts = reader.read(sample_input(SAMPLE))
    assert facts == FACTS
    assert reader.audit.entries == ["call LetterFacts", "done LetterFacts"]


def test_a_model_that_answers_in_prose_is_made_to_call_the_answer_tool() -> None:
    model = ScriptedModel([[{"text": "Here is the plan, in prose."}], [plan(GROUNDED_STEP, "u2")]])

    assert run_plan(reader_with(model)) == [GROUNDED_STEP]
    assert model.requests[1]["tool_choice"] == {"any": {}}
    assert model.requests[1]["tools"] == ["ActionPlan"]


def test_the_drafter_carries_the_lookup_and_can_decide_no_letter_is_needed() -> None:
    model = ScriptedModel([[lookup()], [tool_use("DraftDecision", "u2", {"needed": False})]])
    reader = reader_with(model)

    draft = reader.draft(FACTS, GROUNDED, load_senders()["cjib"], visitor_language="uk")
    assert draft is None
    assert model.requests[0]["tools"] == ["official_routes", "DraftDecision"]
    assert reader.audit.entries[-2:] == ["call DraftDecision", "done DraftDecision"]


def test_the_audit_trail_never_carries_what_the_letter_said() -> None:
    model = ScriptedModel([[lookup()], [plan(GROUNDED_STEP, "u2")]])
    reader = reader_with(model)
    run_plan(reader)

    joined = " ".join(reader.audit.entries)
    for value in (*GROUNDED.values(), "8194 5523 7761", ROUTE):
        assert value not in joined


@pytest.mark.parametrize("opening", [[[lookup()]], [[{"text": "Done."}]]])
def test_a_model_that_never_answers_raises_rather_than_returning_nothing(
    opening: list[list[dict[str, Any]]],
) -> None:
    prose: list[list[dict[str, Any]]] = [[{"text": "No tool call here."}]] * 2
    model = ScriptedModel(opening + prose)
    with pytest.raises(Exception, match="structured output tool"):
        run_plan(reader_with(model))
