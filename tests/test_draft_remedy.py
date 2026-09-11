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
    wrong = {
        name: drafts[name].kind
        for name in sorted(named_it & drafts.keys())
        if drafts[name].kind != "appeal"
    }
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
