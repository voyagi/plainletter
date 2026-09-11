"""The remedy check against a real model, opt in, because it spends money on somebody's account.

`tests/test_draft_remedy.py` reads fixed answers and pins the drafting instruction's text. Neither
can say what a model does when it reads that instruction, and that is where the defect lived: the
instruction asked for "the decision being objected to", so a live draft named an objection against
a letter whose own last paragraph offered an appeal.

This closes that gap and is skipped unless `PLAINLETTER_EVAL=1`, the same switch the evaluation
harness uses and for the same reason. One run is one reading, which is several calls to the model.

    PLAINLETTER_EVAL=1 uv run pytest tests/test_draft_remedy_live.py
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from evals.cases import TOGGLE, live_run_enabled
from plainletter import intake
from plainletter.bedrock import BedrockReadingModel
from plainletter.kb import known_sender_ids
from plainletter.pipeline import Pipeline

# Its last paragraph offers `beroep instellen bij de officier van justitie`, and it is short enough
# that one reading of it is the cheapest honest version of this check.
LETTER = Path(__file__).resolve().parents[1] / "evals" / "letters" / "cjib-eerste-aanmaning.txt"
VISITOR_LANGUAGE = "tr"
TODAY = date(2026, 9, 1)

pytestmark = pytest.mark.skipif(
    not live_run_enabled(), reason=f"reaching the model costs money: set {TOGGLE}=1 to run this"
)


def test_a_live_reading_of_an_appeal_letter_drafts_an_appeal() -> None:
    reading = Pipeline(model=BedrockReadingModel(sender_ids=known_sender_ids())).run(
        intake.from_path(LETTER), visitor_language=VISITOR_LANGUAGE, today=TODAY
    )
    draft = reading.draft
    assert draft is not None, "the letter offers an appeal and the reading wrote nothing back"
    assert draft.kind == "appeal", f"drafted a {draft.kind} against a letter offering an appeal"
    dutch = draft.dutch.casefold()
    assert "beroep" in dutch, "the draft is called an appeal and never says so"
    assert "bezwaar" not in dutch, "the draft names the objection remedy as well as the appeal one"
