"""The remedy in the draft has to be the remedy the letter names.

Dutch administrative law keeps two of them apart. A `bezwaar` is an objection, lodged with the body
that took the decision. A `beroep` is an appeal, lodged with a different body: a traffic fine is
appealed to the officier van justitie and cannot be objected to at all. A draft naming the wrong
one sends the visitor to the wrong office with the wrong word on the page, inside a window that
cannot be reopened once it closes.

The traffic fine sample drafted an objection while its own last paragraph said `beroep instellen`,
and the drafting instruction that produced it asked for "the decision being objected to". So this
reads every sample rather than the one that was wrong.
"""

from __future__ import annotations

from plainletter.demo import sample_names, sample_text, scripted_reading
from plainletter.reading_model import DRAFT_PROMPT
from plainletter.schemas import DraftLetter

APPEAL = "beroep"
OBJECTION = "bezwaar"


def _drafts() -> dict[str, DraftLetter]:
    readings = {name: scripted_reading(name) for name in sample_names()}
    return {name: reading.draft for name, reading in readings.items() if reading.draft is not None}


def test_a_letter_offering_an_appeal_is_answered_with_an_appeal() -> None:
    named_it = {name for name in sample_names() if APPEAL in sample_text(name).casefold()}
    assert named_it, "no sample letter names an appeal, so this check would pass on an empty set"
    drafts = _drafts()
    # A letter offering an appeal may still need no letter back, so this does not demand a draft for
    # every one of them. It does demand at least one, because the day the last such draft disappears
    # the loop below runs over nothing and reports success for a set it never read.
    covered = named_it & drafts.keys()
    assert covered, f"no sample letter offering an appeal drafts a reply: {sorted(named_it)}"
    wrong = {name: drafts[name].kind for name in sorted(covered) if drafts[name].kind != "appeal"}
    assert not wrong, f"the letter offers an appeal and the draft calls it something else: {wrong}"


def test_no_draft_mixes_the_two_remedies() -> None:
    drafts = _drafts()
    kinds = {draft.kind for draft in drafts.values()}
    assert {"appeal", "objection"} <= kinds, (
        f"the sample set has to exercise both remedies for this to mean anything, saw {kinds}"
    )
    mixed: dict[str, str] = {}
    for name, draft in sorted(drafts.items()):
        dutch = draft.dutch.casefold()
        if draft.kind == "appeal" and (APPEAL not in dutch or OBJECTION in dutch):
            mixed[name] = "an appeal that does not read as one"
        if draft.kind == "objection" and (OBJECTION not in dutch or APPEAL in dutch):
            mixed[name] = "an objection that does not read as one"
    assert not mixed, f"the draft's own words disagree with its kind: {mixed}"


def test_the_drafting_instruction_does_not_lean_towards_an_objection() -> None:
    # The two checks above read fixed answers. `scripted_model` never reads the drafting
    # instruction, so nothing in this file can say what a live model does with it. What this pins is
    # the instruction itself, which is where the defect was: it asked for "the decision being
    # objected to", so every draft leaned one way whatever the letter said. The live path is
    # exercised by the evaluation harness behind PLAINLETTER_EVAL=1, which spends real money on
    # every run and is deliberately not part of this suite.
    # Collapsed to single spaces first: the instruction is wrapped prose, so a phrase it really
    # carries can sit either side of a line break and a plain substring search misses it.
    instruction = " ".join(DRAFT_PROMPT.split()).casefold()
    # The exact phrase that was there, rather than the two words on their own: the instruction now
    # says a traffic fine is "never objected to", which is the opposite of the defect.
    assert "the decision being objected to" not in instruction, (
        "the instruction still asks for the decision being objected to, whatever the letter says"
    )
    assert APPEAL in instruction and OBJECTION in instruction, "it names only one of the remedies"
    assert '"appeal"' in instruction and '"objection"' in instruction, (
        "the instruction does not say which kind to set for which remedy"
    )
