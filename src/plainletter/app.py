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
* Memory, only when asked, and erasure whenever asked. A reading is kept under a case id when the
  request says the visitor consented, and a case id sent with a letter brings the earlier readings
  back. Without consent nothing is written anywhere, and a request carrying `forget` erases
  everything under that case without reading anything.
* The trace. One span per letter with counts and outcomes, and a failure logged by its type, so
  neither the monitoring nor the log ever holds a line of the letter.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Annotated, Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError

from . import intake
from .bedrock import VERIFIED_MODEL_IDS, VERIFIED_ON, BedrockReadingModel, probe_models
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
from .pipeline import Pipeline, RefusedReadingError
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

# The same ceiling counted in base64 characters, which is what actually arrives. Comparing the
# encoded string against the byte figure is off by a third, so the real limit was 18.75 MiB while
# the page that uploads the file was letting 25 MiB through: every file between the two was
# accepted by the browser and refused here for being too large.
MAX_UPLOAD_CHARS = (MAX_UPLOAD_BYTES + 2) // 3 * 4


def _within_the_ceiling(text: str) -> str:
    """The letter's size as the wire carries it, which is bytes rather than characters."""
    if len(text.encode("utf-8")) > MAX_UPLOAD_BYTES:
        raise ValueError(f"a letter may be at most {MAX_UPLOAD_BYTES} bytes of text")
    return text


LetterText = Annotated[str, AfterValidator(_within_the_ceiling)]

TOO_LARGE = "that file is too large to be a letter. Send the pages one at a time."

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
    # Both fields carry a letter, so both are bounded. Only the encoded one used to be, which left
    # the text field as an unbounded way into a metered service. The encoded one keeps its bound in
    # `_decode` instead of here, because that is where the refusal can say what to do about it.
    #
    # Bounded in bytes rather than in characters. Pydantic's own `max_length` counts characters,
    # and the visitors this desk serves write in Cyrillic and Arabic, where a character is two
    # bytes or three: a character bound is twice the ceiling it was written to be, for exactly the
    # letters this product exists for.
    text: LetterText | None = None
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
    forget: str | None = Field(
        default=None,
        pattern=CASE_ID_PATTERN,
        description="the case id to erase, which is the whole request when it is set",
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
        return _error("payload", _why_invalid(invalid))

    if request.forget is not None:
        return _forgotten(request.forget)

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
            earlier = _recalled(span, memory, request.case_id)
        if earlier.records:
            yield {"stage": "case", "case": _case_event(request.case_id, earlier.records)}

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
        except RefusedReadingError as refusal:
            span.set_attribute("plainletter.refused", True)
            yield {
                "stage": "refused",
                "refused": True,
                "claims": sorted(refusal.claims),
                "message": f"{refusal.message} Nothing was printed. This letter needs a person.",
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
            case = _remembered(span, request, reading, today, memory, earlier)
        span.set_attribute("plainletter.remembered", bool(case and case["remembered"]))
        yield _completed(request, letter, reading, today, case, earlier)
    finally:
        span.end()


def _forgotten(case_id: str) -> dict[str, Any]:
    """Erase a case, and say how many readings were under it.

    No model, no letter, no reading: withdrawing consent must be cheaper and simpler than giving
    it. A case that was never kept answers zero rather than an error, because a visitor asking for
    something to be deleted is entitled to hear that there is nothing there.
    """
    erased = case_memory().forget(case_id)
    logger.info("plainletter.forget %s readings erased", erased)
    return {"stage": "forgotten", "case_id": case_id, "erased": erased}


def known_sender_id(reading: DeskReading) -> str | None:
    """The sender id only when it names an entry in the knowledge base."""
    sender_id = reading.facts.sender_id
    return sender_id if sender_id in known_sender_ids() else None


def model_audit(model: ReadingModel) -> list[str]:
    """The audit trail the Bedrock model kept, or nothing for a scripted one."""
    audit = getattr(model, "audit", None)
    entries = getattr(audit, "entries", None)
    return list(entries) if isinstance(entries, list) else []


# Why a case was not kept, as a value the console can switch on rather than a sentence it has to
# read. The two are different situations for the visitor in front of the desk: one desk keeps
# nothing and never will, the other keeps cases and could not reach the store just now, and only
# the second is worth coming back for.
NO_STORE = "no_store"
STORE_UNREACHABLE = "store_unreachable"
EARLIER_UNAVAILABLE = "earlier_unavailable"

NOTES = {
    NO_STORE: "This desk keeps no cases: no memory store is configured.",
    STORE_UNREACHABLE: (
        "The case store could not be reached just now, so this reading was not kept. The reading "
        "itself is unaffected, and trying again may still keep the case."
    ),
    EARLIER_UNAVAILABLE: (
        "This reading was kept, but the earlier ones under this case could not be read just now, "
        "so they are not shown."
    ),
}

# The two ways a store that exists can let the desk down. They are separate because reads and
# writes fail separately: a throttled read with a working write kept the case and reported that it
# had not been, which tells a visitor the opposite of what happened to their data.
OUTAGES = frozenset({STORE_UNREACHABLE, EARLIER_UNAVAILABLE})


@dataclass(frozen=True)
class Recalled:
    """Earlier readings under a case, and whether looking for them worked."""

    records: tuple[CaseRecord, ...] = ()
    reached: bool = True


def _recalled(span: Any, memory: CaseMemory, case_id: str | None) -> Recalled:
    """Earlier readings under this case, and whether the store answered at all.

    Recalling is a convenience and reading the letter is the product, so a store that is down must
    not stop a visitor having their letter read. Before this, a case id on the card plus an
    unreachable store meant no reading at all.

    Whether it answered is carried rather than dropped. An empty answer and an unreachable store
    look identical from the outside, and they are not the same thing to tell a returning visitor:
    one says the case has nothing in it, the other says the desk could not look.
    """
    if case_id is None:
        return Recalled()
    try:
        return Recalled(records=memory.recall(case_id))
    except Exception as failure:
        _note_memory_failure(span, "recall", failure)
        return Recalled(reached=False)


def _remembered(
    span: Any,
    request: ReadRequest,
    reading: DeskReading,
    today: date,
    memory: CaseMemory,
    earlier: Recalled,
) -> dict[str, Any] | None:
    """Keep the reading, and say so honestly when keeping it did not work.

    This runs after the whole pipeline has succeeded. A store that raises here used to take a
    finished, checked reading down with it, so the desk lost the card and the calendar file for a
    letter that had been read correctly. Consent that could not be honoured is reported as such,
    and so is a lookup that could not be made, which otherwise left the desk showing nothing with
    nothing said about why.

    The two failures are reported apart, because they happen apart. Reads and writes fail
    separately, and a throttled read beside a working write once put "the case was not kept" in
    front of a visitor whose case had just been kept, which is worse than saying nothing: it is
    telling somebody the opposite of what happened to their own data.
    """
    try:
        event = _remember(request, reading, today, memory, earlier.records)
    except Exception as failure:
        _note_memory_failure(span, "remember", failure)
        event = _case_event(request.case_id, earlier.records)
        event["reason"] = STORE_UNREACHABLE

    if event is not None:
        # A failed write is the worse news and keeps the reason. A failed read only means the
        # earlier readings are missing from the screen, whatever happened to this one.
        if not event.get("reason") and not earlier.reached:
            event["reason"] = EARLIER_UNAVAILABLE
        if event.get("reason"):
            event["note"] = NOTES[event["reason"]]
    return event


def _note_memory_failure(span: Any, what: str, failure: Exception) -> None:
    """The type only, for the same reason the reading path logs only the type."""
    span.set_attribute(f"plainletter.memory_{what}_failed", type(failure).__name__)
    logger.error("plainletter.memory %s failed with %s", what, type(failure).__name__)


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
        event["reason"] = NO_STORE
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
    earlier: Recalled,
) -> dict[str, Any]:
    reference = reading.facts.reference.value if reading.facts.reference else "plainletter"
    # The card carries the case id only when that number leads somewhere, because the sentence
    # printed beside it says to bring the card back and the desk will continue where you left off.
    # It leads somewhere when the reading was kept today, or when there are earlier ones under it.
    #
    # The third case is the one worth spelling out, and it is narrower than it first looks. When
    # the store could not be READ, `earlier` is empty because nobody could look, not because the
    # case is empty, so dropping the number would hand a returning visitor a card without the
    # number they walked in with over an outage. A failed WRITE is not that case: the read
    # answered, the case really is empty, and today was not kept either, so printing the number
    # would repeat a promise that nothing behind it can keep.
    could_not_look = bool(request.case_id) and not earlier.reached
    case_id = (
        case["id"] if case and (case["remembered"] or case["earlier"] or could_not_look) else None
    )
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
    """Check the models this deployment is pointed at, then serve. Nothing starts on a wrong id."""
    check_models()
    app.run(port=8080)


def check_models() -> None:
    """Say what the region knows about the configured models, and refuse a model it does not have.

    Refusing here rather than later is the point: an id that does not resolve fails every reading,
    and finding that out with a visitor in front of the desk is the worst place to find it out. An
    account that will not answer is not the same as a missing model and does not stop the service.
    """
    configured = settings()
    for check in probe_models(
        (configured.reading_model, configured.drafting_model), configured.region
    ):
        if check.reachable is False:
            raise SystemExit(
                f"{check.model_id} does not resolve in {configured.region} ({check.detail}). "
                "Check PLAINLETTER_READING_MODEL and that the model is enabled on this account."
            )
        if not check.as_verified:
            logger.warning(
                "plainletter.model %s is not one this build was checked against on %s (%s)",
                check.model_id,
                VERIFIED_ON,
                ", ".join(sorted(VERIFIED_MODEL_IDS)),
            )
        logger.info(
            "plainletter.model %s in %s: %s", check.model_id, configured.region, check.detail
        )


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
    if len(upload.content_base64) > MAX_UPLOAD_CHARS:
        raise IntakeError(TOO_LARGE)
    try:
        data = base64.b64decode(upload.content_base64, validate=True)
    except (binascii.Error, ValueError) as broken:
        raise IntakeError(f"the upload was not valid base64 ({broken})") from broken
    # The character bound above is the cheap check, made before decoding, and it rounds up to the
    # next whole base64 quantum: a string of exactly that length with no padding decodes to two
    # bytes past the ceiling. The ceiling is a number of bytes, so it is also checked in bytes.
    if len(data) > MAX_UPLOAD_BYTES:
        raise IntakeError(TOO_LARGE)
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


def _why_invalid(invalid: ValidationError) -> str:
    """Which field was wrong and why, never the value that was wrong.

    `str(ValidationError)` quotes the input it refused. The refused input here is the letter, so
    the whole reason the reading path logs only an exception type applies to this line too: the
    detail travels to the browser and into whatever logs the response. The field name and the
    rule it broke are all a caller needs to fix the request.
    """
    problems = [
        f"{'.'.join(str(part) for part in problem['loc']) or 'payload'}: {problem['msg']}"
        for problem in invalid.errors(include_url=False)
    ]
    return "; ".join(problems) or "the payload did not match what one reading may carry"


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
