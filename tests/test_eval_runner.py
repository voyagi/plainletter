"""The runner, driven the whole way through without a cloud account.

Two questions are asked here that the scorer tests cannot answer. Does the toggle really hold the
door shut, and would the instrument notice a bad model? The second is the one that matters: a
harness only ever exercised on a good answer has never been shown to detect a bad one, so the whole
corpus is read here by models that answer badly on purpose and the scorecard is required to say so.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals import cases as corpus
from evals import fingerprint
from evals.run import COULD_NOT_RUN, bedrock_model, compare, main, run, stamp
from evals.scoring import Scorecard
from plainletter.intake import LetterInput
from plainletter.kb import Sender
from plainletter.schemas import (
    ActionStep,
    DeadlineView,
    DraftLetter,
    Explanation,
    LetterDate,
    LetterFacts,
    SourceSpan,
)
from plainletter.settings import settings


class ReadsNothing:
    """A model that returns an empty reading for every letter and explains it in both languages.

    It is not a broken model, it is a useless one: everything it says is structurally valid and
    none of it is an answer. This is the shape a badly damaged prompt takes.
    """

    def __init__(self, visitor_language: str = "uk") -> None:
        self.visitor_language = visitor_language

    def transcribe(self, letter: LetterInput) -> str:
        return letter.text or ""

    def read(self, letter: LetterInput) -> LetterFacts:
        return LetterFacts()

    def explain(
        self, facts: LetterFacts, grounded: dict[str, str], languages: tuple[str, ...]
    ) -> tuple[Explanation, ...]:
        return tuple(
            Explanation(
                language=language,
                what_is_this="Een brief.",
                by_when="De brief geeft geen datum.",
                if_you_do_nothing="Onbekend.",
            )
            for language in languages
        )

    def plan(
        self,
        facts: LetterFacts,
        grounded: dict[str, str],
        sender: Sender | None,
        deadline: DeadlineView | None,
        visitor_language: str,
    ) -> tuple[ActionStep, ...]:
        return (ActionStep(order=1, dutch="Ga naar de balie.", visitor="Ga naar de balie."),)

    def draft(
        self,
        facts: LetterFacts,
        grounded: dict[str, str],
        sender: Sender | None,
        visitor_language: str,
    ) -> DraftLetter | None:
        return None


class InventsADeadline(ReadsNothing):
    """A model that produces a date the letter does not carry, and then writes it out.

    The pipeline refuses this rather than printing it, which is the product working. What the eval
    has to do is record the refusal as a failure to complete rather than as a missing result.
    """

    def read(self, letter: LetterInput) -> LetterFacts:
        return LetterFacts(
            deadline=LetterDate(
                day=1,
                month=12,
                year=2026,
                source=SourceSpan(page=1, text="Betaal voor 1 december 2026."),
            )
        )

    def explain(
        self, facts: LetterFacts, grounded: dict[str, str], languages: tuple[str, ...]
    ) -> tuple[Explanation, ...]:
        return tuple(
            Explanation(
                language=language,
                what_is_this="Een brief.",
                by_when="Betaal voor 1 december 2026.",
                if_you_do_nothing="Onbekend.",
            )
            for language in languages
        )


@pytest.mark.parametrize(
    ("value", "on"),
    [
        ("1", True),
        ("true", True),
        ("YES", True),
        (" on ", True),
        ("0", False),
        ("false", False),
        ("", False),
        ("maybe", False),
    ],
)
def test_the_live_run_is_off_unless_it_is_clearly_asked_for(value: str, on: bool) -> None:
    assert corpus.live_run_enabled({corpus.TOGGLE: value}) is on


def test_the_live_run_is_off_when_the_variable_is_absent() -> None:
    assert corpus.live_run_enabled({}) is False


def test_without_the_toggle_the_runner_stops_before_it_reaches_a_model(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def never() -> object:
        raise AssertionError("the runner built a model without being asked to")

    monkeypatch.delenv(corpus.TOGGLE, raising=False)
    monkeypatch.setattr("evals.run.bedrock_model", never)

    assert main([]) == COULD_NOT_RUN
    assert corpus.TOGGLE in capsys.readouterr().err


def test_a_model_that_reads_nothing_is_scored_as_reading_nothing() -> None:
    """The measurement that makes this harness worth having.

    Measured 2026-08-28 with `uv run pytest tests/test_eval_runner.py`: this model scores 72 of 253
    properties and 0 of 22 letters. The floor is not zero and cannot be, because a letter asserting
    that there is no deadline and no amount is satisfied by an answer containing nothing. That is
    why the line worth reading is the letters, not the ratio, and why the bound below is a bound
    rather than the measured figure, which any new letter would move.
    """
    card = run(corpus.cases(), ReadsNothing)

    assert card.ran == len(corpus.slugs())
    assert card.measured, "these are answers, badly wrong ones, not harness errors"
    assert not card.errors
    assert card.cases_passed == 0
    assert card.checks_passed < card.checks_total / 2, (
        f"a model that read nothing scored {card.checks_passed} of {card.checks_total}, "
        "which means the checks are not asking much"
    )


def test_a_model_that_invents_a_deadline_is_refused_and_the_refusal_is_counted() -> None:
    card = run([corpus.case("cjib-eerste-aanmaning")], InventsADeadline)
    result = card.results[0]

    assert result.actual_outcome == "refusal"
    assert not result.completed
    assert "1 december 2026" in result.detail
    assert result.checks and all(not check.passed for check in result.checks)
    assert card.completed == 0
    # The reason has to be on the card. "It refused" without the date it refused over sends whoever
    # is comparing two prompt versions back to the model to find out what happened.
    assert "1 december 2026" in "\n".join(card.lines())


def test_the_runner_goes_the_whole_way_through_with_the_toggle_on(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Discovery, loading, the pipeline, the scoring, the printed card, the file, the exit code."""
    monkeypatch.setenv(corpus.TOGGLE, "1")
    monkeypatch.setattr("evals.run.bedrock_model", ReadsNothing)
    written = tmp_path / "run.json"

    code = main(["--only", "cjib-eerste-aanmaning", "--json", str(written)])

    assert code == 1, "a model that answered badly must not exit zero"
    printed = capsys.readouterr().out
    assert "Reading 1 letters" in printed
    assert "cjib-eerste-aanmaning" in printed
    assert "FAIL" in printed

    saved = json.loads(written.read_text(encoding="utf-8"))
    assert saved["ran"] == 1
    assert saved["measured"] is True
    assert saved["prompts"] == fingerprint.prompts()
    assert saved["corpus"] == fingerprint.corpus()
    assert saved["cases"][0]["slug"] == "cjib-eerste-aanmaning"


def test_a_run_where_every_letter_broke_exits_non_zero_and_says_unknown(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """What lapsed credentials look like. It must not exit zero and must not print a score."""

    class Breaks(ReadsNothing):
        def read(self, letter: LetterInput) -> LetterFacts:
            raise RuntimeError("NoCredentialsError: unable to locate credentials")

    monkeypatch.setenv(corpus.TOGGLE, "1")
    monkeypatch.setattr("evals.run.bedrock_model", Breaks)

    assert main(["--only", "rdw-apk-herinnering"]) == COULD_NOT_RUN
    printed = capsys.readouterr().out
    assert "UNKNOWN" in printed
    assert "unable to locate credentials" in printed


def test_an_unknown_letter_is_refused_rather_than_quietly_running_none(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(corpus.TOGGLE, "1")
    monkeypatch.setattr("evals.run.bedrock_model", ReadsNothing)

    assert main(["--only", "geen-brief"]) == COULD_NOT_RUN
    assert "geen-brief" in capsys.readouterr().err


def test_comparing_two_runs_reads_no_letters_and_needs_no_toggle(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.delenv(corpus.TOGGLE, raising=False)
    monkeypatch.setattr("evals.run.bedrock_model", ReadsNothing)
    earlier = tmp_path / "earlier.json"
    later = tmp_path / "later.json"
    earlier.write_text(json.dumps(_saved(better=False)), encoding="utf-8")
    later.write_text(json.dumps(_saved(better=True)), encoding="utf-8")

    assert main(["--compare", str(earlier), str(later)]) == 0
    assert "better cjib-eerste-aanmaning" in capsys.readouterr().out


def test_the_comparison_names_the_letters_that_changed_side() -> None:
    printed = "\n".join(compare(_saved(better=False), _saved(better=True)))
    assert "newly correct   1" in printed
    assert "newly wrong     0" in printed
    assert "better cjib-eerste-aanmaning" in printed


def test_the_comparison_names_a_letter_that_got_worse() -> None:
    printed = "\n".join(compare(_saved(better=True), _saved(better=False)))
    assert "newly wrong     1" in printed
    assert "worse  cjib-eerste-aanmaning" in printed


def test_the_comparison_says_which_letters_only_one_run_had() -> None:
    before = _saved(better=True)
    after = _saved(better=True) | {
        "cases": [
            {"slug": "rdw-apk-herinnering", "passed": True},
            {"slug": "nieuw", "passed": True},
        ]
    }
    printed = "\n".join(compare(before, after))
    assert "gone   cjib-eerste-aanmaning" in printed
    assert "new    nieuw" in printed


def test_the_comparison_refuses_to_weigh_a_leak_against_the_rest() -> None:
    after = _saved(better=True) | {"safety_failures": 2}
    printed = "\n".join(compare(_saved(better=False), after))
    assert "2 forbidden strings reached the desk" in printed
    assert "fix it before the change goes anywhere" in printed


def test_a_model_that_raises_is_an_error_and_not_a_wrong_answer() -> None:
    class Breaks(ReadsNothing):
        def read(self, letter: LetterInput) -> LetterFacts:
            raise RuntimeError("the model connection went away")

    card = run([corpus.case("rdw-apk-herinnering")], Breaks)
    result = card.results[0]

    assert result.actual_outcome == "error"
    assert "the model connection went away" in result.detail
    assert len(card.errors) == 1
    assert not card.measured, "one letter, one error, so nothing at all was measured"


def test_an_empty_corpus_stops_the_run_rather_than_scoring_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(corpus.TOGGLE, "1")
    monkeypatch.setattr("evals.run.bedrock_model", ReadsNothing)
    monkeypatch.setattr("evals.run.cases", tuple)

    assert main([]) == COULD_NOT_RUN
    assert "not a clean run" in capsys.readouterr().err


def test_the_comparison_refuses_to_compare_against_a_run_that_measured_nothing() -> None:
    # Lapsed credentials produce a file where every letter errored. Comparing against it would read
    # as every letter having got worse, which is the most misleading answer available.
    blind = _saved(better=True) | {"measured": False}
    printed = "\n".join(compare(blind, _saved(better=True)))
    assert "measured nothing" in printed
    assert "better" not in printed


def test_the_comparison_says_so_when_the_letters_themselves_changed() -> None:
    before = _saved(better=False)
    after = _saved(better=True) | {"corpus": "0000deadbeef"}
    printed = "\n".join(compare(before, after))
    assert "CHANGED" in printed
    assert "not measuring the same" in printed


def test_the_live_model_is_built_from_the_settings_the_run_files_its_score_under(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Otherwise the JSON names a model that never answered, and every comparison is worthless."""
    monkeypatch.setenv("PLAINLETTER_READING_MODEL", "eu.anthropic.some-other-model")
    monkeypatch.setenv("PLAINLETTER_REGION", "eu-west-1")
    settings.cache_clear()
    try:
        built = bedrock_model()
        saved = stamp(Scorecard())
        assert built.reading_model_id == "eu.anthropic.some-other-model"
        assert built.region == "eu-west-1"
        assert saved["reading_model"] == built.reading_model_id
        assert saved["region"] == built.region
    finally:
        settings.cache_clear()


def test_the_stamp_records_what_the_run_was_a_run_of() -> None:
    card = run([corpus.case("rdw-apk-herinnering")], ReadsNothing)
    saved = stamp(card)
    assert saved["prompts"] == fingerprint.prompts()
    assert saved["corpus"] == fingerprint.corpus()
    assert saved["reading_model"]
    assert saved["region"]


def test_two_different_splits_of_the_same_bytes_hash_differently() -> None:
    # The length prefix in the digest is what stops "ab" + "c" and "a" + "bc" reading the same, and
    # without it an edit that moved a line from one letter to the next would be invisible.
    assert fingerprint._short([b"ab", b"c"]) != fingerprint._short([b"a", b"bc"])


def _saved(*, better: bool) -> dict[str, object]:
    return {
        "measured": True,
        "prompts": "aaaabbbbcccc",
        "corpus": "111122223333",
        "guard_denials": 3 if better else 7,
        "safety_failures": 0,
        "cases": [
            {"slug": "cjib-eerste-aanmaning", "passed": better},
            {"slug": "rdw-apk-herinnering", "passed": True},
        ],
    }


def test_the_corpus_reads_the_same_day_every_time() -> None:
    # A measurement whose answer moves with the wall clock cannot be compared with last week's.
    assert corpus.TODAY.isoformat() == "2026-09-01"
    assert all(case.expected.today == corpus.TODAY for case in corpus.cases())
