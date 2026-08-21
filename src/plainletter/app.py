"""The entrypoint AgentCore invokes, and the same server run locally.

One POST carries one letter and comes back with everything the desk needs: the checked reading, the
printable card and the calendar reminder. The console never talks to Bedrock itself, so no AWS
credential ever reaches a browser.

Three things this layer is responsible for and the pipeline is not:

* Refusing an upload before it becomes a model call. A payload with no letter in it, or 25 MB of
  something that is not a letter, is answered rather than forwarded.
* Answering a refusal as an answer. When the check fails, that is the product working, so it comes
  back as a structured verdict with a 200 rather than as a server error.
* Masking. The card redacts on its way to the printer; this redacts every string on its way to the
  network, because a response is a place personal data can end up logged by something else.
"""

from __future__ import annotations

import base64
import binascii
from datetime import date
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import intake
from .bedrock import BedrockReadingModel
from .demo import sample_input, sample_names, scripted_model, scripted_reading
from .intake import IntakeError, LetterInput
from .kb import known_sender_ids
from .pipeline import Pipeline, UngroundedOutputError
from .reading_model import ReadingModel
from .redact import redact
from .render import desk_card_html, reminder_ics

# A letter is a page or a handful of pages. Anything past this is a dossier, a video, or a mistake,
# and it should be refused before it is decoded rather than after.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

DEFAULT_LANGUAGE = "en"

app = BedrockAgentCoreApp()


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


@app.entrypoint
def read_letter(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        request = ReadRequest.model_validate(payload)
    except ValidationError as invalid:
        return _error("payload", str(invalid))

    try:
        letter, model, language = _prepare(request)
    except IntakeError as unreadable:
        return _error("upload", str(unreadable))
    except ValueError as unusable:
        return _error("payload", str(unusable))

    today = request.today or date.today()
    try:
        reading = Pipeline(model=model).run(letter, visitor_language=language, today=today)
    except UngroundedOutputError as refusal:
        return {
            "refused": True,
            "claims": sorted(refusal.claims),
            "message": (
                "The reading was refused because a date or amount in it does not stand in the "
                "letter. Nothing was printed. This letter needs a person."
            ),
        }

    reference = reading.facts.reference.value if reading.facts.reference else "plainletter"
    return {
        "source": "sample" if request.sample else "letter",
        "pages": letter.pages,
        "pages_omitted": letter.pages_omitted,
        "reading": _redacted(reading.model_dump(mode="json")),
        "desk_card_html": desk_card_html(reading, today),
        "reminder_ics": (
            reminder_ics(reading, uid=f"{reference.replace(' ', '')}@plainletter")
            if reading.deadline is not None
            else None
        ),
    }


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
        return (
            _decode(request.letter),
            BedrockReadingModel(sender_ids=known_sender_ids()),
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
