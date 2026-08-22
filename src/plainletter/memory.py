"""What a consenting visitor's case remembers between visits, and where it is kept.

Nothing is remembered unless the visitor says so, and what is remembered when they do is the
checked reading's derived values, masked: who sent the letter, what kind it is, its reference, the
dates and amounts the verifier grounded, the steps, and whether a person had to take over. Never
the letter, a photograph of it, a passage quoted from it, or the explanation written about it. A
visitor who consents to "remember my case" has not consented to a copy of a government letter with
their citizen service number on it, and the record is built so that it cannot carry one.

The record lives in AgentCore Memory as one short-term event per reading, under a case id the desk
card prints. A returning visitor reads the id off the card, the desk recalls every earlier reading
under it, and the new letter is read in the light of the old ones. Nothing here uses a long-term
memory strategy: those mine stored events for insights across visits, which is a second consent the
visitor was never asked for.
"""

from __future__ import annotations

import logging
import re
import secrets
from datetime import date
from typing import Any, Protocol

from pydantic import Field, ValidationError

from .kb import known_sender_ids
from .redact import redact
from .schemas import DeskReading, Frozen

logger = logging.getLogger(__name__)

# Letters and digits a person can read back across a counter: no 0 against O, no 1 against I.
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CASE_ID_PATTERN = r"^[A-Z0-9]{4}-[A-Z0-9]{4}$"
_CASE_ID = re.compile(CASE_ID_PATTERN)


class RememberedStep(Frozen):
    order: int
    dutch: str
    visitor: str
    official_route: str | None = None


class CaseRecord(Frozen):
    """One reading as a returning visitor's desk sees it. Display values only, all masked."""

    case_id: str = Field(pattern=CASE_ID_PATTERN)
    read_on: date
    visitor_language: str
    sender_id: str | None
    sender_name: str
    letter_type: str
    reference: str | None
    issued_on: str | None
    deadline: str | None
    post_by: str | None
    urgency: str | None
    total_amount: str | None
    steps: tuple[RememberedStep, ...]
    handoff_required: bool
    referral: str

    @classmethod
    def from_reading(cls, case_id: str, reading: DeskReading, read_on: date) -> CaseRecord:
        grounded = {fact.name: fact.display for fact in reading.verification.grounded}
        deadline = reading.deadline
        # The model fills sender_id. Only an id the knowledge base knows is worth keeping, and
        # only such an id is guaranteed not to be something the model copied off the page.
        sender_id = reading.facts.sender_id
        return cls.model_validate(
            _masked(
                {
                    "case_id": case_id,
                    "read_on": read_on,
                    "visitor_language": reading.visitor_language,
                    "sender_id": sender_id if sender_id in known_sender_ids() else None,
                    "sender_name": reading.sender_name,
                    "letter_type": reading.letter_type,
                    "reference": grounded.get("reference"),
                    "issued_on": grounded.get("issued_on"),
                    "deadline": deadline.on_written if deadline else None,
                    "post_by": deadline.post_by_written if deadline else None,
                    "urgency": deadline.urgency.value if deadline else None,
                    "total_amount": grounded.get("total_amount"),
                    "steps": [
                        {
                            "order": step.order,
                            "dutch": step.dutch,
                            "visitor": step.visitor,
                            "official_route": step.official_route,
                        }
                        for step in reading.steps
                    ],
                    "handoff_required": reading.handoff.required,
                    "referral": reading.handoff.referral,
                }
            )
        )


class CaseMemory(Protocol):
    """Where case records go, and where they come back from."""

    def remember(self, record: CaseRecord) -> bool:
        """Store the record. True when it is now kept, False when this desk keeps nothing."""
        ...

    def recall(self, case_id: str) -> tuple[CaseRecord, ...]:
        """Every earlier reading under this case id, newest first."""
        ...


class NoCaseMemory:
    """The desk with no memory store configured: consent is recorded, nothing is kept."""

    def remember(self, record: CaseRecord) -> bool:
        return False

    def recall(self, case_id: str) -> tuple[CaseRecord, ...]:
        return ()


class AgentCoreCaseMemory:
    """Case records as short-term events in one AgentCore Memory store, in the EU region."""

    def __init__(self, memory_id: str, region: str) -> None:
        from bedrock_agentcore.memory.session import MemorySessionManager

        self._store = MemorySessionManager(memory_id=memory_id, region_name=region)

    def remember(self, record: CaseRecord) -> bool:
        from bedrock_agentcore.memory.constants import BlobMessage

        self._store.add_turns(
            actor_id=record.case_id,
            session_id=record.case_id,
            messages=[BlobMessage(record.model_dump(mode="json"))],
        )
        return True

    def recall(self, case_id: str) -> tuple[CaseRecord, ...]:
        events = self._store.list_events(actor_id=case_id, session_id=case_id, max_results=50)
        records = [
            record for event in events for record in _records_in(_payload_of(event), case_id)
        ]
        records.sort(key=lambda record: record.read_on, reverse=True)
        return tuple(records)


def new_case_id() -> str:
    half = "".join(secrets.choice(_ALPHABET) for _ in range(4))
    rest = "".join(secrets.choice(_ALPHABET) for _ in range(4))
    return f"{half}-{rest}"


def is_case_id(value: str) -> bool:
    return bool(_CASE_ID.match(value))


def _masked(value: Any) -> Any:
    """Every string in the structure through the mask, leaving numbers, dates and flags alone."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {key: _masked(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_masked(item) for item in value]
    return value


def _payload_of(event: Any) -> list[Any]:
    payload = event.get("payload", []) if hasattr(event, "get") else []
    return list(payload) if isinstance(payload, list) else []


def _records_in(payload: list[Any], case_id: str) -> list[CaseRecord]:
    records: list[CaseRecord] = []
    for item in payload:
        blob = item.get("blob") if isinstance(item, dict) else None
        if not isinstance(blob, dict):
            continue
        try:
            records.append(CaseRecord.model_validate(blob))
        except ValidationError:
            # A record written by an older version of this product, or not by it at all. It is
            # skipped rather than shown wrong, and named by the case so someone can look.
            logger.warning("plainletter.memory skipped an unreadable record under %s", case_id)
    return records
