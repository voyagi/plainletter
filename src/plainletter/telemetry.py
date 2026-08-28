"""What a trace may carry, decided in code before the first agent exists.

There are TWO ways a letter reaches CloudWatch, they are switched off by different variables, and
the first deployed run proved that shutting only the first one is not enough.

Strands writes every prompt, every model answer and every tool argument into its own spans by
default. That is the first, and `OTEL_SEMCONV_STABILITY_OPT_IN` closes it.

The second is the AWS OpenTelemetry distro. It instruments botocore itself, so it sees the Bedrock
request before Strands is involved, and it emits the whole request body as a `gen_ai.user.message`
log record. Nothing in Strands touches that. Worse, the distro OPTS IN on your behalf:
`aws_opentelemetry_distro.py` runs
`os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true")`, while the
instrumentation's own default is `false`. Because it is `setdefault`, a value already present wins,
which is why this module sets it rather than asking for it.

Measured on the deployed runtime on 2026-08-28, before this was pinned: 49 places in one trace read
`[REDACTED]`, and one log record carried all sixteen lines of the letter, with the visitor's name,
street, reference number and every amount. The first switch was working perfectly and the letter was
in CloudWatch anyway.

Both are pinned here, at import, before any tracer or agent exists, rather than left to a deployment
setting a second deployment can forget. `agentcore.json` carries them too, so the process starts
with them; this module is what holds when it does not. A deployment that unmasks specific attributes
is overruled on purpose: there is no attribute on a letter worth the exception.

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

#: The AWS distro's variable, read by the botocore instrumentation on every Bedrock call. Its own
#: default is "false" and only the exact string "true" turns it on, so anything else closes it.
CAPTURE_VARIABLE = "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"
CAPTURE_NOTHING = "false"

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


def stop_capturing_message_content() -> str:
    """Close the distro's own channel, the one that put a whole letter in CloudWatch.

    Overwritten rather than defaulted. The distro sets this to "true" with `setdefault` before any
    of our code runs, so a value has to be written OVER it, and the instrumentation reads the
    variable on each call rather than caching it, which is what makes writing it here effective at
    all.
    """
    os.environ[CAPTURE_VARIABLE] = CAPTURE_NOTHING
    return CAPTURE_NOTHING


def keep_letters_out_of_traces() -> None:
    """Both switches, together, because closing either one alone leaves the letter in the trace."""
    mask_model_content_in_traces()
    stop_capturing_message_content()


keep_letters_out_of_traces()


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
