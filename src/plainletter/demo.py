"""The offline demo, and the fixtures the tests run the whole pipeline against.

Every sample letter comes as a pair: the letter itself, and a reading of it written out in full
instead of asked for. The scripted reading stands in for Bedrock, so the deterministic half of the
product, which is the half carrying the trust claim, runs end to end with no cloud account and no
network.

The letters are invented. The names, addresses, reference numbers, number plates and citizen
service numbers in them belong to nobody, and a real letter never goes near this directory.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from .intake import LetterInput, from_text
from .kb import Sender
from .schemas import (
    ActionStep,
    DeadlineView,
    DraftLetter,
    Explanation,
    LetterFacts,
)

SAMPLES_DIR = Path(__file__).parent / "samples"


class ScriptedReading(BaseModel):
    """What a good reading of one sample letter returns, sourced passage by passage."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    visitor_language: str
    facts: LetterFacts
    explanations: tuple[Explanation, ...]
    steps: tuple[ActionStep, ...] = ()
    draft: DraftLetter | None = None


def sample_text(name: str) -> str:
    return (SAMPLES_DIR / f"{name}.txt").read_text(encoding="utf-8")


def sample_names() -> tuple[str, ...]:
    return tuple(sorted(path.stem for path in SAMPLES_DIR.glob("*.txt")))


def sample_input(name: str) -> LetterInput:
    """The sample letter as the pipeline receives it, which for text needs no model to read it."""
    return from_text(sample_text(name))


@functools.cache
def scripted_reading(name: str) -> ScriptedReading:
    raw = yaml.safe_load((SAMPLES_DIR / f"{name}.reading.yaml").read_text(encoding="utf-8"))
    return ScriptedReading.model_validate(raw)


def scripted_model(name: str) -> ScriptedReadingModel:
    reading = scripted_reading(name)
    return ScriptedReadingModel(
        facts=reading.facts,
        explanations=reading.explanations,
        steps=reading.steps,
        draft_letter=reading.draft,
        transcript=sample_text(name),
    )


@dataclass(frozen=True)
class ScriptedReadingModel:
    """A reading model whose answers are fixed in advance."""

    facts: LetterFacts
    explanations: tuple[Explanation, ...]
    steps: tuple[ActionStep, ...]
    draft_letter: DraftLetter | None
    transcript: str = ""

    def transcribe(self, letter: LetterInput) -> str:
        return self.transcript

    def read(self, letter: LetterInput) -> LetterFacts:
        return self.facts

    def explain(
        self, facts: LetterFacts, grounded: dict[str, str], languages: tuple[str, ...]
    ) -> tuple[Explanation, ...]:
        return tuple(item for item in self.explanations if item.language in languages)

    def plan(
        self,
        facts: LetterFacts,
        grounded: dict[str, str],
        sender: Sender | None,
        deadline: DeadlineView | None,
        visitor_language: str,
    ) -> tuple[ActionStep, ...]:
        return self.steps

    def draft(
        self,
        facts: LetterFacts,
        grounded: dict[str, str],
        sender: Sender | None,
        visitor_language: str,
    ) -> DraftLetter | None:
        return self.draft_letter
