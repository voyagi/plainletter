"""A case store that is down must not take a reading down with it.

Memory is what app.py's docstring calls it: something that happens only when asked. The reading is
the product. Before this, a store that raised took a complete, checked reading with it, and a case
number printed on an old card made a letter unreadable.
"""

from __future__ import annotations

from typing import Any

import pytest

from plainletter import app as runtime
from plainletter.app import MEMORY_UNAVAILABLE, read_letter
from plainletter.memory import CaseRecord

SAMPLE = "cjib-verkeersboete"
TODAY = "2026-08-21"
CASE = "AB12-CD34"
BROKEN = "the case store is unreachable"


class Unreachable:
    """A store that fails the way a throttled or misconfigured one does."""

    def remember(self, record: CaseRecord) -> bool:
        raise RuntimeError(BROKEN)

    def recall(self, case_id: str) -> tuple[CaseRecord, ...]:
        raise RuntimeError(BROKEN)

    def forget(self, case_id: str) -> int:
        raise RuntimeError(BROKEN)


class WritesFail(Unreachable):
    def recall(self, case_id: str) -> tuple[CaseRecord, ...]:
        return ()


@pytest.fixture
def unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "case_memory", Unreachable)


@pytest.fixture
def writes_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "case_memory", WritesFail)


def answer(payload: dict[str, Any]) -> dict[str, Any]:
    got = read_letter({"sample": SAMPLE, "today": TODAY, **payload})
    assert isinstance(got, dict)
    return got


def streamed(payload: dict[str, Any]) -> list[dict[str, Any]]:
    events = read_letter({"sample": SAMPLE, "today": TODAY, "stream": True, **payload})
    assert not isinstance(events, dict)
    return list(events)


def test_control_the_reading_completes_with_the_ordinary_no_store_desk() -> None:
    assert answer({})["stage"] == "done"
    assert streamed({})[-1]["stage"] == "done"


def test_a_case_number_on_a_card_still_gets_the_letter_read(unreachable: None) -> None:
    # Recall runs before the pipeline. A store outage used to mean no reading at all for exactly
    # the visitor who came back.
    assert answer({"case_id": CASE})["stage"] == "done"
    assert streamed({"case_id": CASE})[-1]["stage"] == "done"


def test_a_failed_write_does_not_destroy_a_reading_that_already_succeeded(
    writes_fail: None,
) -> None:
    # Remembering happens after every stage has been checked and sent. Losing the card and the
    # calendar file over it is the whole reading thrown away for the optional half.
    done = answer({"consent": True})
    assert done["stage"] == "done"
    assert done["desk_card_html"]
    assert done["case"]["remembered"] is False
    assert done["case"]["note"] == MEMORY_UNAVAILABLE


def test_the_failure_is_reported_by_its_type_and_never_by_its_message(
    writes_fail: None, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("ERROR"):
        answer({"consent": True})
    logged = caplog.text
    assert "RuntimeError" in logged
    assert BROKEN not in logged
