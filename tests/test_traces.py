"""What a trace carries, proved on the spans the real Strands path emits.

Phase 3's third criterion is that no span or log holds letter text, an image, a citizen service
number or a bank account number. These tests run a scripted Strands model through the same
`BedrockReadingModel` the runtime uses, with a letter that carries all of those, and read every
attribute and event of every span that came out.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from plainletter import app as runtime
from plainletter.app import ReadRequest, _events
from plainletter.bedrock import BedrockReadingModel
from plainletter.demo import sample_input, sample_text, scripted_reading
from plainletter.telemetry import (
    CAPTURE_NOTHING,
    CAPTURE_VARIABLE,
    MASK_EVERYTHING,
    OPT_IN_VARIABLE,
    keep_letters_out_of_traces,
    mask_model_content_in_traces,
    record_tool_outcome,
    start_reading,
    stop_capturing_message_content,
)
from scripted_strands import ScriptedModel, tool_use

SAMPLE = "belastingdienst-aanslag"
LETTER_TEXT = sample_text(SAMPLE)
FACTS = scripted_reading(SAMPLE).facts

# Three things printed on that letter that must never reach a span: the citizen service number,
# the addressee, and the reference number the reading extracts.
FORBIDDEN = ("1234 56 780", "Kovalenko", "7423 61 902 H 56", "Zwanenkade")


def everything_in(spans: list[ReadableSpan]) -> str:
    """Every attribute and every event attribute of every span, as one searchable string."""
    seen: list[Any] = []
    for span in spans:
        seen.append(dict(span.attributes or {}))
        for event in span.events:
            seen.append({event.name: dict(event.attributes or {})})
    return json.dumps(seen, ensure_ascii=False, default=str)


def test_the_policy_is_pinned_in_the_environment_before_any_agent_exists() -> None:
    assert MASK_EVERYTHING in os.environ[OPT_IN_VARIABLE].split(",")


def test_the_restrictive_values_are_what_they_are_spelled_out_here() -> None:
    """Written out, not imported, because every other assertion here imports them.

    A test that compares the environment against the constant it came from passes just as happily
    when both are changed to something permissive. These two strings are the ones the AWS distro and
    the Strands tracer actually read, so this is the assertion that would notice.
    """
    assert CAPTURE_NOTHING == "false"
    assert MASK_EVERYTHING == "gen_ai_unredacted_attributes="
    assert CAPTURE_VARIABLE == "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"
    assert OPT_IN_VARIABLE == "OTEL_SEMCONV_STABILITY_OPT_IN"

    assert os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] == "false"
    assert "gen_ai_unredacted_attributes=" in os.environ["OTEL_SEMCONV_STABILITY_OPT_IN"].split(",")


def test_the_distros_own_capture_switch_is_pinned_shut_too() -> None:
    """The second channel, and the one that actually leaked on the deployed runtime.

    Strands' redaction was working perfectly and a whole letter was in CloudWatch anyway, because
    the AWS distro instruments botocore and emits the Bedrock request body as its own log record.
    """
    assert os.environ[CAPTURE_VARIABLE] == CAPTURE_NOTHING


@contextmanager
def restored(*names: str) -> Iterator[None]:
    """Put every named environment variable back, whether it was set before or absent."""
    before = {name: os.environ.get(name) for name in names}
    try:
        yield
    finally:
        for name, value in before.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def test_the_distro_turning_capture_on_is_overwritten_not_defaulted() -> None:
    """`aws_opentelemetry_distro` runs `setdefault(CAPTURE, "true")` before any of our code.

    A value that merely defaulted would lose that race every time, so this one has to overwrite.
    """
    with restored(CAPTURE_VARIABLE):
        os.environ[CAPTURE_VARIABLE] = "true"
        assert stop_capturing_message_content() == CAPTURE_NOTHING
        assert os.environ[CAPTURE_VARIABLE] == CAPTURE_NOTHING


def test_closing_one_channel_is_not_closing_both() -> None:
    # The lesson from the live run, kept as a test: whoever adds a third channel should have to
    # delete an assertion rather than merely forget one.
    #
    # Both variables are restored, not just the one this test sets. The calls below write to the
    # opt-in variable as well, and a test that leaves the environment changed makes the next one
    # depend on the order they happened to run in.
    with restored(CAPTURE_VARIABLE, OPT_IN_VARIABLE):
        os.environ[CAPTURE_VARIABLE] = "true"
        mask_model_content_in_traces()
        assert os.environ[CAPTURE_VARIABLE] == "true", "masking spans must not touch the distro"
        keep_letters_out_of_traces()
        assert os.environ[CAPTURE_VARIABLE] == CAPTURE_NOTHING
        assert MASK_EVERYTHING in os.environ[OPT_IN_VARIABLE].split(",")


def test_the_deployment_carries_both_switches_as_well_as_the_code() -> None:
    """A runbook naming a runtime variable is worth nothing unless the deploy spec carries it.

    The same lesson as the emergency stop that set a variable on the operator's own laptop.
    """
    spec = json.loads(Path("agentcore/agentcore.json").read_text(encoding="utf-8"))
    declared = {item["name"]: item["value"] for item in spec["runtimes"][0]["envVars"]}
    assert declared[CAPTURE_VARIABLE] == CAPTURE_NOTHING
    assert declared[OPT_IN_VARIABLE] == MASK_EVERYTHING


def test_a_deployment_that_unmasks_an_attribute_is_overruled() -> None:
    original = os.environ[OPT_IN_VARIABLE]
    unmasking = "gen_ai_latest_experimental,gen_ai_unredacted_attributes=gen_ai.input.*"
    try:
        os.environ[OPT_IN_VARIABLE] = unmasking
        value = mask_model_content_in_traces()
        assert value == "gen_ai_latest_experimental,gen_ai_unredacted_attributes="
    finally:
        os.environ[OPT_IN_VARIABLE] = original


def test_reading_a_letter_leaves_no_letter_text_in_any_span(spans: InMemorySpanExporter) -> None:
    payload = FACTS.model_dump(mode="json", exclude_none=True)
    model = ScriptedModel([[tool_use("LetterFacts", "u1", payload)]])
    reader = BedrockReadingModel(sender_ids=("belastingdienst",), make_model=lambda *_: model)

    reader.read(sample_input(SAMPLE))

    finished = spans.get_finished_spans()
    names = {span.name for span in finished}
    assert any(name.startswith("invoke_agent") for name in names), names
    assert "chat" in names
    dump = everything_in(finished)
    for forbidden in FORBIDDEN:
        assert forbidden not in dump, forbidden
    # The mechanism, not merely the absence: the SDK wrote its mask where the letter would be.
    assert "[REDACTED]" in dump
    # And the scripted model really was handed the letter, so the spans had something to mask.
    assert "1234 56 780" in json.dumps(model.requests[0]["messages"], ensure_ascii=False)


def test_the_reading_span_carries_counts_and_outcomes_only(spans: InMemorySpanExporter) -> None:
    span = start_reading(source="letter", kind="text", pages=1, facts_grounded=11)
    record_tool_outcome(span, "refused ActionPlan")
    record_tool_outcome(span, "done ActionPlan")
    span.end()

    [finished] = spans.get_finished_spans()
    assert finished.name == "plainletter.reading"
    assert finished.attributes is not None
    assert finished.attributes["plainletter.facts_grounded"] == 11
    assert finished.attributes["plainletter.kind"] == "text"
    assert [event.name for event in finished.events] == ["plainletter.tool", "plainletter.tool"]
    first = finished.events[0].attributes or {}
    assert first["plainletter.tool.name"] == "ActionPlan"
    assert first["plainletter.outcome"] == "refused"
    for forbidden in (*FORBIDDEN, LETTER_TEXT[:40]):
        assert forbidden not in everything_in([finished])


def test_on_the_entrypoint_the_sdk_spans_hang_under_the_reading_span(
    spans: InMemorySpanExporter, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The whole reading, four model turns and two route lookups, scripted and run through the
    # streaming entrypoint the runtime calls. The generator is resumed step by step from outside,
    # which is exactly where a span attached across a yield would break.
    reading = scripted_reading(SAMPLE)
    explanations = {"items": [item.model_dump() for item in reading.explanations]}
    steps = {"items": [step.model_dump() for step in reading.steps]}
    lookup = tool_use("official_routes", "r", {"sender_id": "belastingdienst"})
    model = ScriptedModel(
        [
            [tool_use("LetterFacts", "u1", FACTS.model_dump(mode="json", exclude_none=True))],
            [tool_use("Explanations", "u2", explanations)],
            [lookup],
            [tool_use("ActionPlan", "u3", steps)],
            [lookup],
            [tool_use("DraftDecision", "u4", {"needed": False})],
        ]
    )
    reader = BedrockReadingModel(sender_ids=("belastingdienst",), make_model=lambda *_: model)
    monkeypatch.setattr(runtime, "case_memory", lambda: runtime.NoCaseMemory())
    request = ReadRequest(letter={"text": LETTER_TEXT}, visitor_language="uk", stream=True)

    events = list(_events(request, sample_input(SAMPLE), reader, "uk", date(2026, 8, 21)))

    assert events[-1]["stage"] == "done"
    finished = spans.get_finished_spans()
    [root] = [span for span in finished if span.name == "plainletter.reading"]
    agents = [span for span in finished if span.name.startswith("invoke_agent")]
    assert len(agents) == 4
    for agent in agents:
        assert agent.parent is not None and agent.parent.span_id == root.context.span_id
    assert root.attributes is not None
    assert root.attributes["plainletter.facts_grounded"] > 0
    assert root.attributes["plainletter.sender"] == "belastingdienst"
    outcomes = [
        event.attributes["plainletter.outcome"] for event in root.events if event.attributes
    ]
    assert outcomes.count("call") == 6 and outcomes.count("done") == 6
    for forbidden in FORBIDDEN:
        assert forbidden not in everything_in(finished), forbidden
