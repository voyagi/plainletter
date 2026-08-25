"""The Bedrock implementation of the reading model.

Every turn goes to a vision-capable Sonnet on an EU cross-region inference profile sourced from
Frankfurt, because the letters carry personal data and processing them outside the EU is not a
trade this product makes. Drafting was the cheaper Haiku's job until the first live letter: it
opened a Ukrainian objection in Russian and changed language halfway down, and the draft is the one
thing the visitor signs. The drafting model stays a separate setting so that can be revisited.

Transcription is a separate agent rather than a second question to the reading one, and the cost of
that extra turn is the point: two turns that never saw each other's answer have to agree before a
fact is allowed through.

Every structured answer is asked for as a tool call. Strands registers the answer's schema as a
tool, the model has to call it, and the call goes through the same executor as any other tool. That
routing is what makes the grounding guard real: after the verifier, an answer carrying an invented
date or amount is refused at that boundary, the refusal goes back to the model as the tool's result,
and the model writes again. The guard is passed in rather than built here, since it can only be
built once the verifier has said which values are real.

The planner and the drafter also carry one real tool, the official-route lookup. A route they name
was fetched, and the fetch is on the audit trail.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel
from strands import Agent
from strands.models import BedrockModel
from strands.models.model import Model

from .guard import AuditTrail, GroundingGuard
from .intake import LetterInput
from .kb import Sender
from .reading_model import (
    DRAFT_PROMPT,
    EXPLAIN_PROMPT,
    PLAN_PROMPT,
    READING_PROMPT,
    TRANSCRIBE_PROMPT,
)
from .schemas import ActionStep, DeadlineView, DraftLetter, Explanation, LetterFacts
from .spend import MAX_OUTPUT_TOKENS, transcription_tokens
from .telemetry import mask_model_content_in_traces
from .tools import official_routes

# The whole published id, read off the model's own Bedrock card on 2026-08-25:
# https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-sonnet-4-6.html
# AWS publishes no dated variant for the 4.6 generation, unlike the 4.5 line, whose id really does
# carry one (anthropic.claude-haiku-4-5-20251001-v1:0). So this is not an alias standing in front of
# a newer model: the `eu.` prefix is the geo inference profile, which decides which regions may
# serve the request and never which model answers it. What a deployment can still get wrong is
# pointing at something else through the environment, which is what the probe below is for.
READING_MODEL_ID = "eu.anthropic.claude-sonnet-4-6"
DRAFTING_MODEL_ID = READING_MODEL_ID
SOURCE_REGION = "eu-central-1"

# The ids the twelve recorded sample readings and the live checks were made against. An id outside
# this set is not refused, since an operator may have a reason, but it is said out loud.
VERIFIED_MODEL_IDS = frozenset({READING_MODEL_ID, DRAFTING_MODEL_ID})
VERIFIED_ON = "2026-08-25"

AnswerT = TypeVar("AnswerT", bound=BaseModel)


class Explanations(BaseModel):
    """The three answers about the letter, once in each language that was asked for."""

    items: list[Explanation]


class ActionPlan(BaseModel):
    """The steps the visitor takes next, in order, each with its official route."""

    items: list[ActionStep]


class DraftDecision(BaseModel):
    """Whether a letter back is the right move, and the letter itself when it is."""

    needed: bool
    letter: DraftLetter | None = None


class NoStructuredAnswerError(RuntimeError):
    """The model finished without calling the answer tool, so there is nothing to read."""


def bedrock_model(model_id: str, region: str, max_tokens: int) -> Model:
    return BedrockModel(model_id=model_id, region_name=region, max_tokens=max_tokens)


@dataclass(frozen=True)
class ModelCheck:
    """What the startup probe could establish about one configured model id."""

    model_id: str
    #: Whether this id is one the recorded readings and the live checks were made against.
    as_verified: bool
    #: True when the region answered for it, False when it said there is no such profile, and None
    #: when the account would not say, which is a different thing and must not read as a failure.
    reachable: bool | None
    detail: str


def probe_models(
    model_ids: tuple[str, ...], region: str, client: Any | None = None
) -> tuple[ModelCheck, ...]:
    """Ask the region about each configured model id, before a letter depends on the answer.

    A wrong id is otherwise found by the first visitor, halfway through their reading. This cannot
    catch a provider quietly changing what an id points at, and nothing on this side could: what it
    catches is a deployment pointing somewhere the account cannot reach, or somewhere this build was
    never checked against.
    """
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    asked = client or boto3.client("bedrock", region_name=region)
    checks: list[ModelCheck] = []
    for model_id in model_ids:
        as_verified = model_id in VERIFIED_MODEL_IDS
        try:
            asked.get_inference_profile(inferenceProfileIdentifier=model_id)
            checks.append(ModelCheck(model_id, as_verified, True, f"{region} knows it"))
        except ClientError as refused:
            code = refused.response.get("Error", {}).get("Code", "")
            reachable = False if code == "ResourceNotFoundException" else None
            checks.append(ModelCheck(model_id, as_verified, reachable, code or "an AWS error"))
        except BotoCoreError as unreachable:
            # No credentials, no endpoint, no network. The reading path may still work, so this is
            # reported rather than treated as a missing model.
            checks.append(ModelCheck(model_id, as_verified, None, type(unreachable).__name__))
    return tuple(checks)


@dataclass
class BedrockReadingModel:
    """Reads and writes with Bedrock, in the EU, with the guard attached downstream."""

    sender_ids: tuple[str, ...]
    audit: AuditTrail = field(default_factory=AuditTrail)
    region: str = SOURCE_REGION
    reading_model_id: str = READING_MODEL_ID
    drafting_model_id: str = DRAFTING_MODEL_ID
    make_model: Callable[[str, str, int], Model] = bedrock_model

    def transcribe(self, letter: LetterInput) -> str:
        agent = self._agent(
            self.reading_model_id,
            TRANSCRIBE_PROMPT,
            guard=None,
            max_tokens=transcription_tokens(letter.pages),
        )
        return str(agent(list(letter.blocks)))

    def read(self, letter: LetterInput) -> LetterFacts:
        agent = self._agent(
            self.reading_model_id,
            READING_PROMPT.format(sender_ids=", ".join(self.sender_ids)),
            guard=None,
        )
        return _ask(agent, list(letter.blocks), LetterFacts)

    def explain(
        self, facts: LetterFacts, grounded: dict[str, str], languages: tuple[str, ...]
    ) -> tuple[Explanation, ...]:
        agent = self._agent(self.reading_model_id, EXPLAIN_PROMPT, guard=self._guard(grounded))
        prompt = (
            f"Grounded facts: {grounded}\n"
            f"Letter type: {_named(facts.letter_type)}\n"
            f"Consequences in the letter: {[span.text for span in facts.consequences]}\n"
            f"Answer in each of these languages: {', '.join(languages)}."
        )
        return tuple(_ask(agent, prompt, Explanations).items)

    def plan(
        self,
        facts: LetterFacts,
        grounded: dict[str, str],
        sender: Sender | None,
        deadline: DeadlineView | None,
        visitor_language: str,
    ) -> tuple[ActionStep, ...]:
        agent = self._agent(
            self.reading_model_id,
            PLAN_PROMPT,
            guard=self._guard(grounded),
            tools=[official_routes],
        )
        prompt = (
            f"Grounded facts: {grounded}\n"
            f"Deadline: {deadline.model_dump() if deadline else 'none in the letter'}\n"
            f"Sender id: {_sender_id(facts, sender)}\n"
            f"Visitor language: {visitor_language}."
        )
        return tuple(_ask(agent, prompt, ActionPlan).items)

    def draft(
        self,
        facts: LetterFacts,
        grounded: dict[str, str],
        sender: Sender | None,
        visitor_language: str,
    ) -> DraftLetter | None:
        agent = self._agent(
            self.drafting_model_id,
            DRAFT_PROMPT,
            guard=self._guard(grounded),
            tools=[official_routes],
        )
        prompt = (
            f"Grounded facts: {grounded}\n"
            f"Reference: {_named(facts.reference)}\n"
            f"Objection route in the letter: "
            f"{facts.objection_route.text if facts.objection_route else 'none'}\n"
            f"Sender id: {_sender_id(facts, sender)}\n"
            f"Visitor language: {visitor_language}."
        )
        decision = _ask(agent, prompt, DraftDecision)
        return decision.letter if decision.needed else None

    def _guard(self, grounded: dict[str, str]) -> GroundingGuard:
        return GroundingGuard(frozenset(grounded.values()))

    def _agent(
        self,
        model_id: str,
        system_prompt: str,
        *,
        guard: GroundingGuard | None,
        tools: list[Any] | None = None,
        max_tokens: int = MAX_OUTPUT_TOKENS,
    ) -> Agent:
        # The tracer is built by the first Agent in the process and reads its policy then.
        mask_model_content_in_traces()
        return Agent(
            model=self.make_model(model_id, self.region, max_tokens),
            system_prompt=system_prompt,
            tools=tools,
            hooks=[self.audit],
            interventions=[guard] if guard else [],
            callback_handler=None,
        )


def _ask(agent: Agent, prompt: Any, answer_type: type[AnswerT]) -> AnswerT:
    """Run the agent until it calls the answer tool, and return what that call carried."""
    result = agent(prompt, structured_output_model=answer_type)
    answer = result.structured_output
    if not isinstance(answer, answer_type):
        raise NoStructuredAnswerError(
            f"the model ended its turn without producing {answer_type.__name__}"
        )
    return answer


def _named(value: Any) -> str:
    return str(value.value) if value is not None else "not in the letter"


def _sender_id(facts: LetterFacts, sender: Sender | None) -> str:
    if sender is not None:
        return sender.id
    return facts.sender_id or "not recognised"
