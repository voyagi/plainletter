"""The two spend bounds: what one call may write, and how many calls a day may hold.

The ceiling is only worth anything if it is claimed before the money is spent, so the test that
matters most here is the one that makes any model call fatal and then proves the refusal still
comes back.
"""

from __future__ import annotations

import threading
from typing import Any

import pytest
from strands.models.bedrock import BedrockModel

from plainletter import app as runtime
from plainletter import bedrock, intake
from plainletter.app import read_letter
from plainletter.bedrock import BedrockReadingModel, bedrock_model
from plainletter.schemas import LetterFacts
from plainletter.spend import (
    MAX_OUTPUT_TOKENS,
    MAX_TRANSCRIPTION_TOKENS,
    TRANSCRIPTION_TOKENS_PER_PAGE,
    DailyReadings,
    transcription_tokens,
)
from scripted_strands import ScriptedModel, tool_use

A_LETTER = {"filename": "letter.txt", "text": "Belastingdienst\nAanslag 2026\n"}


class RecordingFactory:
    """Stands in for the model factory and keeps the ceiling every stage asked for."""

    def __init__(self, model: ScriptedModel) -> None:
        self.model = model
        self.ceilings: list[int] = []

    def __call__(self, model_id: str, region: str, max_tokens: int) -> ScriptedModel:
        self.ceilings.append(max_tokens)
        return self.model


def explanation_turn() -> list[dict[str, Any]]:
    item = {
        "language": "nl",
        "what_is_this": "A tax assessment.",
        "by_when": "The letter gives no date.",
        "if_you_do_nothing": "The amount is increased.",
    }
    return [tool_use("Explanations", "u1", {"items": [item]})]


def test_the_bedrock_factory_puts_the_ceiling_on_the_model() -> None:
    model = bedrock_model("eu.anthropic.claude-sonnet-4-6", "eu-central-1", 1234)
    assert isinstance(model, BedrockModel)
    assert model.get_config()["max_tokens"] == 1234


def test_transcription_gets_room_for_every_page_and_stops_at_the_ceiling() -> None:
    assert transcription_tokens(1) == TRANSCRIPTION_TOKENS_PER_PAGE
    assert transcription_tokens(3) == 3 * TRANSCRIPTION_TOKENS_PER_PAGE
    assert transcription_tokens(0) == TRANSCRIPTION_TOKENS_PER_PAGE
    assert transcription_tokens(500) == MAX_TRANSCRIPTION_TOKENS


def test_a_transcription_asks_for_room_proportional_to_the_pages() -> None:
    factory = RecordingFactory(ScriptedModel([[{"text": "--- pagina 1 ---"}]]))
    reader = BedrockReadingModel(sender_ids=("belastingdienst",), make_model=factory)

    reader.transcribe(intake.from_text("Belastingdienst\nAanslag 2026\n"))

    assert factory.ceilings == [transcription_tokens(1)]


def test_a_writing_stage_asks_for_the_fixed_ceiling() -> None:
    factory = RecordingFactory(ScriptedModel([explanation_turn()]))
    reader = BedrockReadingModel(sender_ids=("belastingdienst",), make_model=factory)

    reader.explain(LetterFacts(), {}, ("nl",))

    assert factory.ceilings == [MAX_OUTPUT_TOKENS]


def test_the_daily_ceiling_hands_out_exactly_its_limit() -> None:
    readings = DailyReadings(limit=2, day_of=lambda: "2026-08-25")

    first, second, third = readings.claim(), readings.claim(), readings.claim()

    assert [first.allowed, second.allowed, third.allowed] == [True, True, False]
    assert [first.used, second.used, third.used] == [1, 2, None]
    assert third.limit == 2 and third.day == "2026-08-25"


def test_a_new_day_starts_the_count_again() -> None:
    day = ["2026-08-25"]
    readings = DailyReadings(limit=1, day_of=lambda: day[0])

    assert readings.claim().allowed is True
    assert readings.claim().allowed is False
    day[0] = "2026-08-26"
    assert readings.claim().allowed is True


def test_a_limit_of_zero_closes_the_service() -> None:
    assert DailyReadings(limit=0).claim().allowed is False


def test_concurrent_claims_never_hand_out_more_than_the_limit() -> None:
    readings = DailyReadings(limit=10, day_of=lambda: "2026-08-25")
    allowed: list[bool] = []
    start = threading.Barrier(20)

    def claim() -> None:
        start.wait()
        allowed.append(readings.claim().allowed)

    threads = [threading.Thread(target=claim) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert allowed.count(True) == 10


def test_a_refused_reading_never_reaches_a_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def never(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a refused reading built a model")

    # The Bedrock class itself, so that a claim checked one line too late fails this test rather
    # than passing it with a different error.
    monkeypatch.setattr(bedrock, "BedrockModel", never)
    monkeypatch.setattr(runtime, "daily_readings", lambda: DailyReadings(limit=0))

    answer = read_letter({"letter": A_LETTER})

    assert answer["error"]["kind"] == "budget"
    assert "0 letters" in answer["error"]["detail"]


def test_a_sample_reading_costs_nothing_from_the_daily_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The demo letters run on a scripted model, so metering them would close the demo without
    # saving a cent.
    monkeypatch.setattr(runtime, "daily_readings", lambda: DailyReadings(limit=0))

    answer = read_letter({"sample": "belastingdienst-aanslag", "today": "2026-08-21"})

    assert "error" not in answer
