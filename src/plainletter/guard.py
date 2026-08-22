"""The structural half of the grounding promise.

The verifier decides which dates and amounts are real. This module is what stops an ungrounded one
from reaching a person anyway, by refusing the tool call that would carry it. It is an intervention
rather than a line in a prompt because a prompt is a request and this has to be a rule: the model
that would invent a deadline is the same model that would agree not to.

What counts as a tool call here is wider than it looks. Every structured answer the agents give is
asked for as a tool call, so the explanation, the plan and the draft each pass this guard on their
way out of the model, and so does the official-route lookup the planner makes. A refused call goes
back to the model as the tool's result, with the reason, and the model writes again.

The audit trail beside it records that a tool ran and how it ended, never what was in the letter. A
log line holding someone's fine is the same leak as a stored letter.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent, HookRegistry
from strands.interventions import Deny, InterventionHandler, Proceed
from strands.interventions.handler import OnError

from .verify import ungrounded_claims

logger = logging.getLogger(__name__)


class GroundingGuard(InterventionHandler):
    """Deny any tool call carrying a date or amount the verifier did not ground in the letter."""

    def __init__(self, allowed: frozenset[str]) -> None:
        self._allowed = allowed

    @property
    def name(self) -> str:
        return "grounding-guard"

    @property
    def on_error(self) -> OnError:
        # Fail closed. A guard that lets the call through when its own check breaks is not a guard,
        # and the thing it is protecting is a person acting on a wrong date.
        return "deny"

    def before_tool_call(self, event: BeforeToolCallEvent, **kwargs: Any) -> Proceed | Deny:
        payload = json.dumps(event.tool_use.get("input", {}), ensure_ascii=False)
        stray = ungrounded_claims(payload, self._allowed)
        if not stray:
            return Proceed()

        listed = ", ".join(sorted(stray))
        return Deny(
            reason=(
                f"Refused: {listed} does not appear in the letter. Use only the dates and amounts "
                "the reading grounded, or say that the letter does not give one."
            )
        )


@dataclass
class AuditTrail:
    """Records that a tool ran and how it ended, never what the letter said."""

    entries: list[str] = field(default_factory=list)

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self._before)
        registry.add_callback(AfterToolCallEvent, self._after)

    def _before(self, event: BeforeToolCallEvent) -> None:
        self._record(f"call {event.tool_use.get('name', 'unknown')}")

    def _after(self, event: AfterToolCallEvent) -> None:
        if event.cancel_message:
            outcome = "refused"
        elif event.result.get("status") == "error":
            outcome = "failed"
        else:
            outcome = "done"
        self._record(f"{outcome} {event.tool_use.get('name', 'unknown')}")

    def _record(self, line: str) -> None:
        self.entries.append(line)
        logger.info("plainletter.tool %s", line)
