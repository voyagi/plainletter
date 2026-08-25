"""What is kept, for how long, and how a visitor takes it back.

A privacy page can say "thirty days, and you can have it deleted" without a line of code behind it.
These tests are the line of code: the expiry is read out of the deployment description that creates
the store, and the erasure route is exercised end to end through the entrypoint.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from conftest import RecordingMemory
from plainletter import app as runtime
from plainletter.app import read_letter
from plainletter.memory import AgentCoreCaseMemory, CaseRecord, NoCaseMemory

DEPLOYMENT = Path(__file__).resolve().parents[1] / "agentcore" / "agentcore.json"
CASE = "K7P2-4MXQ"
SAMPLE = "belastingdienst-aanslag"
TODAY = date(2026, 8, 21)

RETENTION_DAYS = 30


def deployment() -> dict[str, Any]:
    return json.loads(DEPLOYMENT.read_text(encoding="utf-8"))


def test_the_store_this_deployment_creates_expires_its_events_after_thirty_days() -> None:
    [store] = deployment()["memories"]

    assert store["eventExpiryDuration"] == RETENTION_DAYS


def test_the_store_mines_nothing_across_visits() -> None:
    # A long-term strategy would derive insights from stored events, which is a second purpose the
    # visitor consented to nothing about.
    [store] = deployment()["memories"]

    assert store["strategies"] == []


def test_the_runtime_may_delete_an_event_as_well_as_write_one() -> None:
    # An erasure route the deployed role cannot perform is a promise, not a route.
    policy = json.loads(
        (Path(__file__).resolve().parents[1] / "src" / "runtime-permissions.json").read_text(
            encoding="utf-8"
        )
    )
    memory_actions = [
        action
        for statement in policy["Statement"]
        for action in statement["Action"]
        if action.startswith("bedrock-agentcore:")
    ]

    assert "bedrock-agentcore:DeleteEvent" in memory_actions


def test_a_visitor_can_have_their_case_erased(memory: RecordingMemory) -> None:
    kept = read_letter({"sample": SAMPLE, "today": TODAY.isoformat(), "consent": True})
    case_id = kept["case"]["id"]

    answer = read_letter({"forget": case_id})

    assert answer == {"stage": "forgotten", "case_id": case_id, "erased": 1}
    assert memory.kept == {}


def test_erasing_a_case_that_was_never_kept_is_an_answer_rather_than_an_error(
    memory: RecordingMemory,
) -> None:
    answer = read_letter({"forget": CASE})

    assert answer == {"stage": "forgotten", "case_id": CASE, "erased": 0}


def test_a_malformed_case_id_is_refused_before_anything_is_deleted(
    memory: RecordingMemory,
) -> None:
    answer = read_letter({"forget": "delete everything"})

    assert answer["error"]["kind"] == "payload"


def test_erasing_reads_no_letter_and_calls_no_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def never(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("erasing a case built a model")

    monkeypatch.setattr(runtime, "Pipeline", never)
    monkeypatch.setattr(runtime, "case_memory", NoCaseMemory)

    assert read_letter({"forget": CASE})["erased"] == 0


def test_the_agentcore_store_deletes_every_event_under_the_case() -> None:
    class FakeSessionManager:
        def __init__(self) -> None:
            self.events = [{"eventId": "e1"}, {"eventId": "e2"}, {"no_id": True}]
            self.deleted: list[str] = []

        def list_events(self, **kwargs: Any) -> list[dict[str, Any]]:
            return self.events

        def delete_event(self, actor_id: str, session_id: str, event_id: str) -> None:
            self.deleted.append(event_id)

    store = AgentCoreCaseMemory.__new__(AgentCoreCaseMemory)
    store._store = FakeSessionManager()

    assert store.forget(CASE) == 2
    assert store._store.deleted == ["e1", "e2"]


def test_a_desk_with_no_store_answers_zero_rather_than_pretending() -> None:
    assert NoCaseMemory().forget(CASE) == 0


def test_a_record_carries_nothing_that_outlives_its_purpose() -> None:
    from plainletter.demo import sample_input, scripted_model
    from plainletter.pipeline import Pipeline

    reading = Pipeline(model=scripted_model(SAMPLE)).run(
        sample_input(SAMPLE), visitor_language="uk", today=TODAY
    )
    record = CaseRecord.from_reading(CASE, reading, TODAY)

    # Every field is a derived display value. A name, an address or a passage would be personal
    # data kept for thirty days that the stated purpose never needed.
    dumped = json.dumps(record.model_dump(mode="json"), ensure_ascii=False)
    for personal in ("Kovalenko", "Zwanenkade", "1234 56 780"):
        assert personal not in dumped
