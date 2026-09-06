"""A case store that is down must not take a reading down with it.

Memory is what app.py's docstring calls it: something that happens only when asked. The reading is
the product. Before this, a store that raised took a complete, checked reading with it, and a case
number printed on an old card made a letter unreadable.
"""

from __future__ import annotations

import itertools
import re
from datetime import date
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

# Kept so the sweep below can put the real one back after swapping in a fake per row.
_real_case_memory = runtime.case_memory


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


def _a_reading() -> Any:
    from plainletter.demo import sample_input, scripted_model
    from plainletter.pipeline import Pipeline

    return Pipeline(model=scripted_model(SAMPLE)).run(
        sample_input(SAMPLE), visitor_language="uk", today=date(2026, 8, 1)
    )


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


def test_a_failed_write_alone_does_not_reprint_a_number_that_leads_nowhere(
    writes_fail: None,
) -> None:
    # The sentence printed beside the number says to bring the card back and the desk will
    # continue where you left off. Here the store ANSWERED, so the case really is empty, and
    # today was not kept either. Reprinting the number repeats a promise nothing can keep.
    #
    # This is narrower than "any outage". When the READ failed the desk could not look, so the
    # number is kept, which the test above pins.
    done = answer({"consent": True, "case_id": CASE})
    assert done["case"]["remembered"] is False
    assert done["case"]["reason"] == STORE_UNREACHABLE
    assert CASE not in done["desk_card_html"]


def test_control_a_failed_write_still_prints_the_number_when_the_case_has_earlier_readings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The control for the line above. The number leads somewhere here, so it must survive the
    # same failed write, or the rule is just "drop it whenever a write fails".
    kept = CaseRecord.from_reading(CASE, _a_reading(), date(2026, 8, 1))

    class HasEarlierButCannotWrite(Unreachable):
        def recall(self, case_id: str) -> tuple[CaseRecord, ...]:
            return (kept,)

    monkeypatch.setattr(runtime, "case_memory", HasEarlierButCannotWrite)
    done = answer({"consent": True, "case_id": CASE})
    assert done["case"]["remembered"] is False
    assert done["case"]["earlier"]
    assert CASE in done["desk_card_html"]


def test_control_a_reading_with_no_case_at_all_prints_no_case_number() -> None:
    # The control for the card assertion above: the number appears because there is a case, not
    # because the card prints one regardless.
    done = answer({})
    assert done["case"] is None
    assert CASE not in done["desk_card_html"]
    assert "Zaaknummer" not in done["desk_card_html"]


# ---------------------------------------------------------------------------------------------
# The swept property.
#
# What the desk is told about a case is a small state machine: the store can be absent, healthy,
# failing on reads, failing on writes or failing on both, crossed with whether the visitor
# consented and whether they brought a case number. Twenty combinations, and two of them were
# wrong at different times, each found only after it shipped.
#
# So the whole space is enumerated, and each row is checked against what actually happened to the
# store rather than against what anyone expected the code to say.
# ---------------------------------------------------------------------------------------------

_ON_CARD = re.compile(r"Zaaknummer ([A-Z0-9]{4}-[A-Z0-9]{4})")


class SweptStore:
    """A store whose reads and writes can each be made to fail, recording what really landed."""

    def __init__(self, *, reads: bool, writes: bool, holds: tuple[CaseRecord, ...] = ()) -> None:
        self._reads = reads
        self._writes = writes
        self._holds = holds
        self.written: list[CaseRecord] = []

    def remember(self, record: CaseRecord) -> bool:
        if not self._writes:
            raise RuntimeError("write refused")
        self.written.append(record)
        return True

    def recall(self, case_id: str) -> tuple[CaseRecord, ...]:
        if not self._reads:
            raise RuntimeError("read refused")
        return self._holds

    def forget(self, case_id: str) -> int:
        return 0


_HEALTH = {
    "no store": None,
    "healthy": (True, True),
    "reads fail": (False, True),
    "writes fail": (True, False),
    "both fail": (False, False),
}


def test_what_the_desk_is_told_matches_what_happened_to_the_store() -> None:
    seen: list[tuple[str, bool, bool]] = []

    for label, (consent, with_case) in itertools.product(
        _HEALTH, itertools.product([False, True], [False, True])
    ):
        health = _HEALTH[label]
        store: Any = (
            runtime.NoCaseMemory()
            if health is None
            else SweptStore(reads=health[0], writes=health[1])
        )
        runtime.case_memory = lambda kept=store: kept  # type: ignore[assignment]
        try:
            payload: dict[str, Any] = {"sample": SAMPLE, "today": TODAY}
            if consent:
                payload["consent"] = True
            if with_case:
                payload["case_id"] = CASE
            done = read_letter(payload)
        finally:
            runtime.case_memory = _real_case_memory

        assert isinstance(done, dict)
        assert done["stage"] == "done", f"{label}: no reading at all"
        seen.append((label, consent, with_case))

        case = done["case"]
        landed = bool(getattr(store, "written", []))
        reason = (case or {}).get("reason")
        where = f"{label}/consent={consent}/case={with_case}"

        if case is not None:
            # Ground truth first. What the desk says must agree with the store, in both
            # directions: never claim a case was kept that was not, never deny one that was.
            assert case["remembered"] == landed, f"{where}: says {case['remembered']}, was {landed}"
            if landed:
                assert reason != STORE_UNREACHABLE, f"{where}: kept, but reason says not kept"
            if reason == NO_STORE:
                assert health is None, f"{where}: blames a missing store"
            if reason == EARLIER_UNAVAILABLE:
                assert health is not None and not health[0], f"{where}: blames a working read"
            if reason is not None:
                assert reason in NOTES, f"{where}: unknown reason {reason!r}"
                assert case["note"] == NOTES[reason], f"{where}: note does not match its reason"

        # A number is printed only when it leads somewhere: kept today, or the desk could not look
        # and the visitor brought it in themselves.
        printed = _ON_CARD.search(done["desk_card_html"])
        could_not_look = with_case and health is not None and not health[0]
        assert bool(printed) == (landed or could_not_look), f"{where}: card number={printed}"
        if printed and with_case:
            assert printed.group(1) == CASE, f"{where}: card shows {printed.group(1)}"

    assert len(seen) == len(_HEALTH) * 4


def test_a_failed_write_does_not_erase_a_number_that_still_leads_somewhere() -> None:
    # The control for the card rule above, and the reason it is worded around the READ. The store
    # answered here and the case really does hold something, so the number survives the same
    # failed write that drops it when the case is empty.
    kept = CaseRecord.from_reading(CASE, _a_reading(), date(2026, 8, 1))
    store = SweptStore(reads=True, writes=False, holds=(kept,))
    runtime.case_memory = lambda: store  # type: ignore[assignment]
    try:
        done = answer({"consent": True, "case_id": CASE})
    finally:
        runtime.case_memory = _real_case_memory

    assert done["case"]["remembered"] is False
    assert done["case"]["earlier"]
    assert CASE in done["desk_card_html"]
