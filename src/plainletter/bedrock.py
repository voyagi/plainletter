"""The Bedrock implementation of the reading model.

Reading and explaining go to a vision-capable Sonnet, the cheaper Haiku handles the shorter
drafting turn. Both are EU cross-region inference profiles sourced from Frankfurt, because the
letters carry personal data and processing them outside the EU is not a trade this product makes.

Every stage after the verifier is constructed with the grounding guard attached, so a date the
model invents cannot leave through a tool call. The guard is passed in rather than built here: it
can only be built once the verifier has said which values are real.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel
from strands import Agent
from strands.models import BedrockModel

from .guard import AuditTrail, GroundingGuard
from .kb import Sender
from .reading_model import DRAFT_PROMPT, EXPLAIN_PROMPT, PLAN_PROMPT, READING_PROMPT
from .schemas import ActionStep, DeadlineView, DraftLetter, Explanation, LetterFacts

READING_MODEL_ID = "eu.anthropic.claude-sonnet-4-6"
DRAFTING_MODEL_ID = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
SOURCE_REGION = "eu-central-1"


class _Explanations(BaseModel):
    items: list[Explanation]


class _Steps(BaseModel):
    items: list[ActionStep]


class _Draft(BaseModel):
    needed: bool
    letter: DraftLetter | None = None


@dataclass
class BedrockReadingModel:
    """Reads and writes with Bedrock, in the EU, with the guard attached downstream."""

    sender_ids: tuple[str, ...]
    audit: AuditTrail = field(default_factory=AuditTrail)
    region: str = SOURCE_REGION
    reading_model_id: str = READING_MODEL_ID
    drafting_model_id: str = DRAFTING_MODEL_ID

    def read(self, letter: Any) -> LetterFacts:
        agent = self._agent(
            self.reading_model_id,
            READING_PROMPT.format(sender_ids=", ".join(self.sender_ids)),
            guard=None,
        )
        return agent.structured_output(LetterFacts, letter)

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
        return tuple(agent.structured_output(_Explanations, prompt).items)

    def plan(
        self,
        facts: LetterFacts,
        grounded: dict[str, str],
        sender: Sender | None,
        deadline: DeadlineView | None,
        visitor_language: str,
    ) -> tuple[ActionStep, ...]:
        agent = self._agent(self.reading_model_id, PLAN_PROMPT, guard=self._guard(grounded))
        prompt = (
            f"Grounded facts: {grounded}\n"
            f"Deadline: {deadline.model_dump() if deadline else 'none in the letter'}\n"
            f"Knowledge base entry: {sender.model_dump() if sender else 'sender not recognised'}\n"
            f"Visitor language: {visitor_language}."
        )
        return tuple(agent.structured_output(_Steps, prompt).items)

    def draft(
        self,
        facts: LetterFacts,
        grounded: dict[str, str],
        sender: Sender | None,
        visitor_language: str,
    ) -> DraftLetter | None:
        agent = self._agent(self.drafting_model_id, DRAFT_PROMPT, guard=self._guard(grounded))
        prompt = (
            f"Grounded facts: {grounded}\n"
            f"Reference: {_named(facts.reference)}\n"
            f"Objection route in the letter: "
            f"{facts.objection_route.text if facts.objection_route else 'none'}\n"
            f"Knowledge base entry: {sender.model_dump() if sender else 'sender not recognised'}\n"
            f"Visitor language: {visitor_language}."
        )
        result = agent.structured_output(_Draft, prompt)
        return result.letter if result.needed else None

    def _guard(self, grounded: dict[str, str]) -> GroundingGuard:
        return GroundingGuard(frozenset(grounded.values()))

    def _agent(self, model_id: str, system_prompt: str, *, guard: GroundingGuard | None) -> Agent:
        model = BedrockModel(model_id=model_id, region_name=self.region)
        return Agent(
            model=model,
            system_prompt=system_prompt,
            hooks=[self.audit],
            interventions=[guard] if guard else [],
        )


def _named(value: Any) -> str:
    return str(value.value) if value is not None else "not in the letter"
