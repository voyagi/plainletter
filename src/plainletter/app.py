"""The entrypoint AgentCore invokes, and the same server run locally.

One POST carries one letter and comes back with everything the desk needs: the checked reading, the
printable card and the calendar reminder. The console never talks to Bedrock itself, so no AWS
credential ever reaches a browser.

Six things this layer is responsible for and the pipeline is not:

* Refusing an upload before it becomes a model call. A payload with no letter in it, or 25 MB of
  something that is not a letter, is answered rather than forwarded.
* The daily ceiling on readings, claimed here for the same reason: it is the last point at which
  refusing is still free. What that ceiling can and cannot promise is written in `spend.py`.
* Answering a refusal as an answer. When the check fails, that is the product working, so it comes
  back as a structured verdict with a 200 rather than as a server error.
* Masking. The card redacts on its way to the printer; this redacts every string on its way to the
  network, because a response is a place personal data can end up logged by something else.
* Memory, only when asked. A reading is kept under a case id when the request says the visitor
  consented, and a case id sent with a letter brings the earlier readings back. Without consent
  nothing is written anywhere.
* The trace. One span per letter with counts and outcomes, and a failure logged by its type, so
  neither the monitoring nor the log ever holds a line of the letter.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
from collections.abc import Iterator
from datetime import date
from functools import lru_cache
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import intake
from .bedrock import BedrockReadingModel
from .demo import sample_input, sample_names, scripted_model, scripted_reading
from .intake import IntakeError, LetterInput
from .kb import known_sender_ids
from .memory import (
    CASE_ID_PATTERN,
    AgentCoreCaseMemory,
    CaseMemory,
    CaseRecord,
    NoCaseMemory,
    new_case_id,
)
from .pipeline import Pipeline, UngroundedOutputError
from .reading_model import ReadingModel
from .redact import redact
from .render import desk_card_html, reminder_ics
from .schemas import DeskReading, ReadingProgress
from .settings import settings
from .spend import DailyReadings
from .telemetry import record_tool_outcome, start_reading, within

logger = logging.getLogger(__name__)

# A letter is a page or a handful of pages. Anything past this is a dossier, a video, or a mistake,
# and it should be refused before it is decoded rather than after.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

DEFAULT_LANGUAGE = "en"

app = BedrockAgentCoreApp()


@lru_cache(maxsize=1)
def daily_readings() -> DailyReadings:
    """This runtime's ceiling on model-backed readings, built once and kept for its lifetime."""
    return DailyReadings(limit=settings().max_readings_per_day)


def case_memory() -> CaseMemory:
    """The store this deployment keeps consented cases in, or the one that keeps nothing."""
    configured = settings()
    if configured.memory_id:
        return AgentCoreCaseMemory(configured.memory_id, configured.region)
    return NoCaseMemory()


class LetterUpload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(default="letter.txt", max_length=255)
    text: str | None = None
    content_base64: str | None = None


class ReadRequest(BaseModel):
    """What one invocation may carry. Exactly one of `sample` and `letter`."""

    model_config = ConfigDict(extra="forbid")

    sample: str | None = None
    letter: LetterUpload | None = None
    visitor_language: str = Field(default=DEFAULT_LANGUAGE, min_length=2, max_length=12)
    today: date | None = None
    stream: bool = False
    consent: bool = Field(
        default=False, description="true only when the visitor agreed to have this case kept"
    )
    case_id: str | None = Field(
        default=None,
        pattern=CASE_ID_PATTERN,
        description="the case id from an earlier card, to continue that case",
    )


@app.entrypoint
def read_letter(payload: dict[str, Any]) -> dict[str, Any] | Iterator[dict[str, Any]]:
    """One letter in, one reading out, streamed to the desk when the caller asks for it.

    Returning a generator is what the runtime turns into an event stream, so the streaming path is
    the same pipeline in the same order rather than a second implementation with its own bugs.
    """
    try:
        request = ReadRequest.model_validate(_unwrapped(payload))
    except ValidationError as invalid:
        return _error("payload", str(invalid))

    try:
        letter, model, language = _prepare(request)
    except IntakeError as unreadable:
        return _error("upload", str(unreadable))
    except ValueError as unusable:
        return _error("payload", str(unusable))

    # After the upload has been decoded and before the first model call: a letter that was never
    # readable should not spend a reading, and a reading that is refused should cost nothing.
    if request.letter is not None:
        claim = daily_readings().claim()
        if not claim.allowed:
            return _error(
                "budget",
                f"this desk has read its {claim.limit} letters for today. Try again tomorrow, "
                "or ask whoever runs this desk to raise the daily limit.",
            )
        logger.info("plainletter.budget %s of %s on %s", claim.used, claim.limit, claim.day)

    today = request.today or date.today()
    events = _events(request, letter, model, language, today)
    if request.stream:
        return events
    return _last(events)


def _events(
    request: ReadRequest,
    letter: LetterInput,
    model: ReadingModel,
    language: str,
    today: date,
) -> Iterator[dict[str, Any]]:
    """Every stage as it lands, then one final message carrying the whole reading."""
    span = start_reading(
        source="sample" if request.sample else "letter",
        kind=letter.kind,
        pages=letter.pages,
        visitor_language=language,
        consent=request.consent,
        returning=request.case_id is not None,
    )
    try:
        memory = case_memory()
        with within(span):
            earlier = memory.recall(request.case_id) if request.case_id else ()
        if earlier:
            yield {"stage": "case", "case": _case_event(request.case_id, earlier)}

        stages = Pipeline(model=model).stages(letter, visitor_language=language, today=today)
        try:
            while True:
                with within(span):
                    try:
                        progress = next(stages)
                    except StopIteration as finished:
                        reading: DeskReading = finished.value
                        break
                yield _redacted(_only_what_this_stage_set(progress))
        except UngroundedOutputError as refusal:
            span.set_attribute("plainletter.refused", True)
            yield {
                "stage": "refused",
                "refused": True,
                "claims": sorted(refusal.claims),
                "message": (
                    "The reading was refused because a date or amount in it does not stand in "
                    "the letter. Nothing was printed. This letter needs a person."
                ),
            }
            return
        except Exception as failure:
            # The type is the diagnosis and is safe to log. The message is not: a validation
            # error quotes the value it refused, and that value came out of the letter.
            span.set_attribute("plainletter.failed", type(failure).__name__)
            logger.error("plainletter.reading failed with %s", type(failure).__name__)
            yield _error("agent", f"the reading stopped with {type(failure).__name__}")
            return
        finally:
            for entry in model_audit(model):
                record_tool_outcome(span, entry)

        span.set_attribute("plainletter.facts_grounded", len(reading.verification.grounded))
        span.set_attribute("plainletter.issues", len(reading.verification.issues))
        span.set_attribute("plainletter.handoff", reading.handoff.required)
        # The model fills sender_id and could put anything there. A span gets the knowledge
        # base's own id or nothing, never a string the model wrote.
        span.set_attribute("plainletter.sender", known_sender_id(reading) or "unknown")
        with within(span):
            case = _remember(request, reading, today, memory, earlier)
        span.set_attribute("plainletter.remembered", bool(case and case["remembered"]))
        yield _completed(request, letter, reading, today, case)
    finally:
        span.end()


def known_sender_id(reading: DeskReading) -> str | None:
    """The sender id only when it names an entry in the knowledge base."""
    sender_id = reading.facts.sender_id
    return sender_id if sender_id in known_sender_ids() else None


def model_audit(model: ReadingModel) -> list[str]:
    """The audit trail the Bedrock model kept, or nothing for a scripted one."""
    audit = getattr(model, "audit", None)
    entries = getattr(audit, "entries", None)
    return list(entries) if isinstance(entries, list) else []


def _remember(
    request: ReadRequest,
    reading: DeskReading,
    today: date,
    memory: CaseMemory,
    earlier: tuple[CaseRecord, ...],
) -> dict[str, Any] | None:
    """Keep the reading when, and only when, the visitor consented. Return what the desk shows."""
    if not request.consent:
        return _case_event(request.case_id, earlier) if request.case_id else None
    case_id = request.case_id or new_case_id()
    kept = memory.remember(CaseRecord.from_reading(case_id, reading, today))
    event = _case_event(case_id, earlier)
    event["remembered"] = kept
    if not kept:
        event["note"] = "This desk keeps no cases: no memory store is configured."
    return event


def _case_event(case_id: str | None, earlier: tuple[CaseRecord, ...]) -> dict[str, Any]:
    return {
        "id": case_id,
        "remembered": False,
        "earlier": [record.model_dump(mode="json") for record in earlier],
    }


def _completed(
    request: ReadRequest,
    letter: LetterInput,
    reading: DeskReading,
    today: date,
    case: dict[str, Any] | None,
) -> dict[str, Any]:
    reference = reading.facts.reference.value if reading.facts.reference else "plainletter"
    # The card carries the case id once there is a case: kept today, or continued from before.
    case_id = case["id"] if case and (case["remembered"] or case["earlier"]) else None
    return {
        "stage": "done",
        "source": "sample" if request.sample else "letter",
        "pages": letter.pages,
        "pages_omitted": letter.pages_omitted,
        "reading": _redacted(reading.model_dump(mode="json")),
        "case": case,
        "desk_card_html": desk_card_html(reading, today, case_id=case_id),
        "reminder_ics": (
            reminder_ics(reading, uid=f"{reference.replace(' ', '')}@plainletter")
            if reading.deadline is not None
            else None
        ),
    }


def _only_what_this_stage_set(progress: ReadingProgress) -> dict[str, Any]:
    """The stage's own fields, whole.

    Pydantic's own `exclude_unset` reaches all the way down, which would hand the console a facts
    object missing every field the letter happened not to carry. The selection belongs at the top
    level only: this stage produced these fields, and each of them arrives complete.
    """
    dumped = progress.model_dump(mode="json")
    return {key: value for key, value in dumped.items() if key in progress.model_fields_set}


def _last(events: Iterator[dict[str, Any]]) -> dict[str, Any]:
    """Drain the stages and answer with the terminal message, which is the whole reading."""
    final: dict[str, Any] = _error("pipeline", "the reading produced nothing")
    for event in events:
        final = event
    return final


def serve() -> None:
    """Run the same entrypoint locally. Outside a container this binds to the loopback only."""
    app.run(port=8080)


def _prepare(request: ReadRequest) -> tuple[LetterInput, ReadingModel, str]:
    if request.sample is not None and request.letter is not None:
        raise ValueError("send a sample name or a letter, not both")
    if request.sample is not None:
        if request.sample not in sample_names():
            raise ValueError(f"unknown sample; the ones that exist are {', '.join(sample_names())}")
        language = scripted_reading(request.sample).visitor_language
        return sample_input(request.sample), scripted_model(request.sample), language
    if request.letter is not None:
        configured = settings()
        return (
            _decode(request.letter),
            BedrockReadingModel(
                sender_ids=known_sender_ids(),
                region=configured.region,
                reading_model_id=configured.reading_model,
                drafting_model_id=configured.drafting_model,
            ),
            request.visitor_language,
        )
    raise ValueError("send either a sample name or a letter")


def _decode(upload: LetterUpload) -> LetterInput:
    if upload.text is not None:
        return intake.from_text(upload.text)
    if upload.content_base64 is None:
        raise ValueError("a letter needs either text or content_base64")
    if len(upload.content_base64) > MAX_UPLOAD_BYTES:
        raise IntakeError("that file is too large to be a letter. Send the pages one at a time.")
    try:
        data = base64.b64decode(upload.content_base64, validate=True)
    except (binascii.Error, ValueError) as broken:
        raise IntakeError(f"the upload was not valid base64 ({broken})") from broken
    return intake.from_bytes(data, filename=upload.filename)


def _unwrapped(payload: dict[str, Any]) -> dict[str, Any]:
    """The request inside the envelope the AgentCore CLI puts around its argument.

    `agentcore invoke` and `agentcore dev` send `{"prompt": text}`. A JSON object in there is the
    request itself; a bare word is the name of a sample letter. Anything else is left alone for the
    schema to refuse with its own reason.
    """
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or set(payload) != {"prompt"}:
        return payload
    text = prompt.strip()
    if not text.startswith("{"):
        return {"sample": text}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return payload
    return parsed if isinstance(parsed, dict) else payload


def _error(kind: str, detail: str) -> dict[str, Any]:
    return {"error": {"kind": kind, "detail": detail}}


def _redacted(value: Any) -> Any:
    """Mask every string on the way out, leaving numbers and structure alone.

    Walking the parsed structure rather than the serialised text is deliberate: a citizen service
    number is nine digits, and running the mask over raw JSON would rewrite the inside of a number
    and hand back something that no longer parses.
    """
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {key: _redacted(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redacted(item) for item in value]
    return value


if __name__ == "__main__":  # pragma: no cover
    serve()
