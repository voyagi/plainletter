"""One tracer provider for the whole test session, exporting into memory, and one case store.

OpenTelemetry accepts a global provider once per process, so it is installed here, before any test
module builds an agent, and every test that wants to read spans clears and reads the same exporter.

The case store lives here for a different reason: two test modules need a desk that keeps records
where a test can see them, and two copies of it would be two chances to disagree about what
"remembered" means.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from plainletter import app as runtime
from plainletter.memory import CaseRecord

_EXPORTER = InMemorySpanExporter()
_PROVIDER = TracerProvider()
_PROVIDER.add_span_processor(SimpleSpanProcessor(_EXPORTER))
trace.set_tracer_provider(_PROVIDER)


@pytest.fixture
def spans() -> Iterator[InMemorySpanExporter]:
    _EXPORTER.clear()
    yield _EXPORTER
    _EXPORTER.clear()


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

    def forget(self, case_id: str) -> int:
        return len(self.kept.pop(case_id, []))


@pytest.fixture
def memory(monkeypatch: pytest.MonkeyPatch) -> RecordingMemory:
    store = RecordingMemory()
    monkeypatch.setattr(runtime, "case_memory", lambda: store)
    return store
