"""Consent decides whether anything is kept, and what is kept can never hold the letter."""

from __future__ import annotations

import json
from datetime import date

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from plainletter import app as runtime
from plainletter.app import read_letter
from plainletter.demo import sample_text, scripted_model
from plainletter.memory import (
    AgentCoreCaseMemory,
    CaseRecord,
    NoCaseMemory,
    is_case_id,
    new_case_id,
)
from plainletter.pipeline import Pipeline

SAMPLE = "belastingdienst-aanslag"
TODAY = date(2026, 8, 21)
CASE = "K7P2-4MXQ"


class RecordingMemory:
    """A store that keeps records in a dict, so a test can see exactly what was written."""

    def __init__(self, earlier: dict[str, list[CaseRecord]] | None = None) -> None:
        self.kept: dict[str, list[CaseRecord]] = dict(earlier or {})
        self.recalled: list[str] = []

    def remember(self, record: CaseRecord) -> bool:
        self.kept.setdefault(record.case_id, []).append(record)
        return True

    def recall(self, case_id: str) -> tuple[CaseRecord, ...]:
        self.recalled.append(case_id)
        return tuple(reversed(self.kept.get(case_id, [])))


@pytest.fixture
def memory(monkeypatch: pytest.MonkeyPatch) -> RecordingMemory:
    store = RecordingMemory()
    monkeypatch.setattr(runtime, "case_memory", lambda: store)
    return store


def a_reading():
    from plainletter.demo import sample_input

    return Pipeline(model=scripted_model(SAMPLE)).run(
        sample_input(SAMPLE), visitor_language="uk", today=TODAY
    )


def test_a_case_record_holds_derived_values_and_nothing_quoted_from_the_letter() -> None:
    record = CaseRecord.from_reading(CASE, a_reading(), TODAY)
    dumped = json.dumps(record.model_dump(mode="json"), ensure_ascii=False)

    assert record.sender_id == "belastingdienst"
    assert record.deadline == "30 september 2026"
    assert record.total_amount == "EUR 1.316,00"
    assert record.steps and record.steps[0].official_route
    # The letter's own lines never make it in: not the addressee, not the citizen service number,
    # not a passage the verifier matched, not the explanation written about it.
    for line in ("Kovalenko", "1234 56 780", "Zwanenkade", "Betaal het totaalbedrag"):
        assert line not in dumped, line
    assert "explanations" not in dumped and "source" not in dumped


def test_a_sender_id_the_model_made_up_is_not_kept_or_traced(
    memory: RecordingMemory, spans: InMemorySpanExporter
) -> None:
    # sender_id is the model's to fill, so it is the one field where letter text could arrive
    # under an innocent name. Only an id the knowledge base knows survives.
    reading = a_reading()
    invented = reading.model_copy(
        update={"facts": reading.facts.model_copy(update={"sender_id": "Kovalenko Zwanenkade"})}
    )
    record = CaseRecord.from_reading(CASE, invented, TODAY)
    assert record.sender_id is None

    span = runtime.start_reading(source="letter", kind="text")
    span.set_attribute("plainletter.sender", runtime.known_sender_id(invented) or "unknown")
    span.end()
    [finished] = spans.get_finished_spans()
    assert finished.attributes is not None
    assert finished.attributes["plainletter.sender"] == "unknown"


def test_a_record_with_a_masked_number_stays_masked_through_the_mask() -> None:
    record = CaseRecord.from_reading(CASE, a_reading(), TODAY)
    for step in record.steps:
        assert "1234 56 780" not in step.dutch and "1234 56 780" not in step.visitor


def test_without_consent_nothing_is_written(memory: RecordingMemory) -> None:
    answer = read_letter({"sample": SAMPLE, "today": TODAY.isoformat()})
    assert answer["case"] is None
    assert memory.kept == {}
    assert "Zaaknummer" not in answer["desk_card_html"]


def test_with_consent_one_record_is_kept_under_a_new_case_id(memory: RecordingMemory) -> None:
    answer = read_letter({"sample": SAMPLE, "today": TODAY.isoformat(), "consent": True})
    case = answer["case"]
    assert case["remembered"] is True
    assert is_case_id(case["id"])
    [record] = memory.kept[case["id"]]
    assert record.read_on == TODAY
    assert f"Zaaknummer {case['id']}" in answer["desk_card_html"]


def test_a_returning_visitor_gets_the_earlier_readings_first(memory: RecordingMemory) -> None:
    earlier = CaseRecord.from_reading(CASE, a_reading(), date(2026, 7, 1))
    memory.kept[CASE] = [earlier]

    stream = read_letter(
        {"sample": SAMPLE, "today": TODAY.isoformat(), "case_id": CASE, "stream": True}
    )
    assert not isinstance(stream, dict)
    events = list(stream)

    assert events[0]["stage"] == "case"
    assert events[0]["case"]["earlier"][0]["read_on"] == "2026-07-01"
    assert memory.recalled == [CASE]
    # Brought a case id but did not consent again: the earlier case is shown, nothing new is kept.
    assert memory.kept[CASE] == [earlier]
    assert events[-1]["case"]["remembered"] is False
    assert f"Zaaknummer {CASE}" in events[-1]["desk_card_html"]


def test_consent_on_a_return_visit_appends_to_the_same_case(memory: RecordingMemory) -> None:
    memory.kept[CASE] = [CaseRecord.from_reading(CASE, a_reading(), date(2026, 7, 1))]
    answer = read_letter(
        {"sample": SAMPLE, "today": TODAY.isoformat(), "case_id": CASE, "consent": True}
    )
    assert answer["case"]["id"] == CASE
    assert [record.read_on for record in memory.kept[CASE]] == [date(2026, 7, 1), TODAY]


def test_a_malformed_case_id_is_refused_before_anything_runs(memory: RecordingMemory) -> None:
    answer = read_letter({"sample": SAMPLE, "case_id": "not a case"})
    assert answer["error"]["kind"] == "payload"
    assert memory.recalled == []


def test_a_desk_without_a_store_says_so_instead_of_pretending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "case_memory", NoCaseMemory)
    answer = read_letter({"sample": SAMPLE, "today": TODAY.isoformat(), "consent": True})
    assert answer["case"]["remembered"] is False
    assert "no memory store" in answer["case"]["note"]
    assert "Zaaknummer" not in answer["desk_card_html"]


def test_case_ids_are_readable_across_a_counter() -> None:
    for _ in range(200):
        case_id = new_case_id()
        assert is_case_id(case_id)
        assert not set(case_id) & set("0O1I")


def test_the_agentcore_store_writes_one_blob_event_per_reading() -> None:
    class FakeSessionManager:
        def __init__(self) -> None:
            self.turns: list[dict] = []

        def add_turns(self, **kwargs):
            self.turns.append(kwargs)

        def list_events(self, **kwargs):
            return [{"payload": [{"blob": turn["messages"][0].data} for turn in self.turns]}]

    store = AgentCoreCaseMemory.__new__(AgentCoreCaseMemory)
    store._store = FakeSessionManager()
    record = CaseRecord.from_reading(CASE, a_reading(), TODAY)

    assert store.remember(record) is True
    [turn] = store._store.turns
    assert turn["actor_id"] == CASE and turn["session_id"] == CASE
    assert turn["messages"][0].data["deadline"] == "30 september 2026"
    assert store.recall(CASE) == (record,)
    assert "1234 56 780" not in json.dumps(turn["messages"][0].data)


def test_the_reading_span_records_consent_and_memory_as_flags_only(
    memory: RecordingMemory, spans: InMemorySpanExporter
) -> None:
    read_letter({"sample": SAMPLE, "today": TODAY.isoformat(), "consent": True})
    [span] = [item for item in spans.get_finished_spans() if item.name == "plainletter.reading"]
    attributes = dict(span.attributes or {})
    assert attributes["plainletter.consent"] is True
    assert attributes["plainletter.remembered"] is True
    assert attributes["plainletter.facts_grounded"] > 0
    assert attributes["plainletter.sender"] == "belastingdienst"
    assert "1234 56 780" not in json.dumps(attributes, default=str)
    assert sample_text(SAMPLE).splitlines()[0] not in json.dumps(attributes, default=str)
