"""What a trace may carry, decided in code before the first agent exists.

Strands writes every prompt, every model answer and every tool argument into its spans by default.
On the runtime that would put the photographed letter, its transcript and the citizen service number
printed on it into CloudWatch as span events, which is the stored letter this product promises never
to keep, kept by the monitoring instead. The SDK masks all of that when one environment variable
says so, and this module says so at import, before the tracer is built, rather than leaving it to a
deployment setting that a second deployment can forget. A deployment that unmasks specific
attributes is overruled on purpose: there is no attribute on a letter worth the exception.

Beside the SDK's own spans the product records one span per reading, carrying counts and outcomes
only: how many facts were grounded, whether the check passed, which tools ran and how each ended.
Never what any of them said. `AgentCore Observability` shows both.
"""

from __future__ import annotations

import os
from contextlib import AbstractContextManager

from opentelemetry import trace
from opentelemetry.trace import Span

OPT_IN_VARIABLE = "OTEL_SEMCONV_STABILITY_OPT_IN"
UNREDACTED_PREFIX = "gen_ai_unredacted_attributes="

# The token with an empty list after it: nothing is left unmasked.
MASK_EVERYTHING = UNREDACTED_PREFIX

READING_SPAN = "plainletter.reading"


def mask_model_content_in_traces() -> str:
    """Pin the Strands tracer's policy so prompts, answers and tool arguments never reach a span."""
    kept = [
        token.strip()
        for token in os.environ.get(OPT_IN_VARIABLE, "").split(",")
        if token.strip() and not token.strip().startswith(UNREDACTED_PREFIX)
    ]
    kept.append(MASK_EVERYTHING)
    value = ",".join(kept)
    os.environ[OPT_IN_VARIABLE] = value
    return value


mask_model_content_in_traces()


def start_reading(**attributes: str | int | bool) -> Span:
    """One span for one letter. The attributes are counts, ids and flags, never letter content.

    The span is started but not made current. The reading is a generator the runtime resumes from
    whichever context it pleases, and a span attached across a yield is detached in a context it
    was never attached in. Each step between two yields makes it current with `within` instead,
    so the SDK's own spans still hang under it, and the caller ends it when the reading is over.
    """
    span = trace.get_tracer("plainletter").start_span(READING_SPAN)
    for key, value in attributes.items():
        span.set_attribute(f"plainletter.{key}", value)
    return span


def within(span: Span) -> AbstractContextManager[Span]:
    """Make the reading span current for one synchronous step."""
    return trace.use_span(
        span, end_on_exit=False, record_exception=False, set_status_on_exception=False
    )


def record_tool_outcome(span: Span, entry: str) -> None:
    """An audit-trail line as a span event: which tool, how it ended, and nothing else."""
    outcome, _, tool = entry.partition(" ")
    span.add_event(
        "plainletter.tool", {"plainletter.tool.name": tool, "plainletter.outcome": outcome}
    )
