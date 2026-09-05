"""A case store that is down must not take a reading down with it.

Memory is what app.py's docstring calls it: something that happens only when asked. The reading is
the product. Before this, a store that raised took a complete, checked reading with it, and a case
number printed on an old card made a letter unreadable.
"""

from __future__ import annotations

from typing import Any

import pytest

from plainletter import app as runtime
from plainletter.app import (
    EARLIER_UNAVAILABLE,
    NO_STORE,
    NOTES,
    STORE_UNREACHABLE,
    read_letter,
)
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
    assert done["case"]["reason"] == STORE_UNREACHABLE
    assert done["case"]["note"] == NOTES[STORE_UNREACHABLE]


def test_the_failure_is_reported_by_its_type_and_never_by_its_message(
    writes_fail: None, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("ERROR"):
        answer({"consent": True})
    logged = caplog.text
    assert "RuntimeError" in logged
    assert BROKEN not in logged


def test_a_store_that_is_down_is_not_reported_as_a_desk_that_keeps_nothing(
    writes_fail: None,
) -> None:
    # The console renders its own sentence per reason and cannot read an English note, so the
    # reason has to say which of the two situations this is. A desk with no store configured will
    # never keep a case; a store that could not be reached may keep it on the next try, and only
    # one of those is worth a visitor coming back for.
    assert answer({"consent": True})["case"]["reason"] == STORE_UNREACHABLE


def test_control_a_desk_with_no_store_configured_reports_the_other_reason() -> None:
    # The control for the line above, and the reason both constants exist: without it the test
    # would pass on a build that answered STORE_UNREACHABLE to everything.
    done = answer({"consent": True})
    assert done["case"]["remembered"] is False
    assert done["case"]["reason"] == NO_STORE
    assert done["case"]["note"] == NOTES[NO_STORE]


def test_a_recall_that_failed_is_said_out_loud_rather_than_read_as_an_empty_case(
    unreachable: None,
) -> None:
    # Without consent nothing is written, so a read-only outage left the desk showing no earlier
    # readings with nothing said about why, and the card dropped the visitor's own case number
    # because `earlier` was empty. Losing a visitor's case number over an outage takes their case
    # away from them.
    done = answer({"case_id": CASE})
    assert done["stage"] == "done"
    assert done["case"]["reason"] == EARLIER_UNAVAILABLE
    assert done["case"]["note"] == NOTES[EARLIER_UNAVAILABLE]
    assert done["case"]["id"] == CASE
    assert CASE in done["desk_card_html"]


def test_a_case_that_was_kept_is_never_reported_as_a_case_that_was_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Reads and writes fail separately. A throttled read beside a working write told a visitor
    # their case had not been kept while it had just been kept, which is worse than saying
    # nothing: it is the opposite of what happened to their own data.
    written: list[CaseRecord] = []

    class ReadsFailWritesWork(Unreachable):
        def remember(self, record: CaseRecord) -> bool:
            written.append(record)
            return True

    monkeypatch.setattr(runtime, "case_memory", ReadsFailWritesWork)
    case = answer({"consent": True, "case_id": CASE})["case"]

    assert len(written) == 1, "the write really happened"
    assert case["remembered"] is True
    assert case["reason"] == EARLIER_UNAVAILABLE
    assert "was kept" in NOTES[EARLIER_UNAVAILABLE]


def test_control_a_failed_write_still_reports_that_nothing_was_kept(writes_fail: None) -> None:
    # The control for the line above: the two reasons have to stay apart in both directions, or
    # splitting them buys nothing.
    case = answer({"consent": True, "case_id": CASE})["case"]
    assert case["remembered"] is False
    assert case["reason"] == STORE_UNREACHABLE


def test_control_a_reading_with_no_case_at_all_prints_no_case_number() -> None:
    # The control for the card assertion above: the number appears because there is a case, not
    # because the card prints one regardless.
    done = answer({})
    assert done["case"] is None
    assert CASE not in done["desk_card_html"]
    assert "Zaaknummer" not in done["desk_card_html"]
