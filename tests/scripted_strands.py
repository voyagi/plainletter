"""A Strands model whose turns are written in advance, for tests that run the real agent loop.

The guard tests and the trace tests both need a model that goes through `Agent`, the event loop,
the tool executor and the tracer exactly as Bedrock would, while saying what the test scripted.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, AsyncIterable
from typing import Any

from strands.models.model import Model


class ScriptedModel(Model):
    """One list of content blocks per call, and a record of every request the agent made."""

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
                "messages": json.loads(json.dumps(messages, default=_describe_bytes)),
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


def _describe_bytes(value: Any) -> str:
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    raise TypeError(f"not serialisable: {type(value).__name__}")
