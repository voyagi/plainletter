"""The one thing the swept property tests share: how to tell a truncated number.

Two separate bugs in the grounding check had the same shape, one in the amount pattern and one in
the dates, so the rule that catches them is written once here and used from both.

    "EUR 123 4567"      matched "EUR 123 456"   the number ENDED just before a digit
    "in 2026 450 euro"  matched "26 450 euro"   the number BEGAN just after a digit

Both reported a value nobody wrote. The first refuses a correct reading; the second is worse,
because a mistyped amount whose truncation happens to equal a grounded one is waved through as
allowed. Neither was found by picking examples, and both were found by sweeping.

Every sweep was proved to bite before it was kept, by putting a defect back on purpose and
running only the test written for it. Nine defects across the six sweeps, and every one went red:

    the amount pattern starting inside a longer number       test_verify.py, amounts
    the amount pattern reading on past the number            test_verify.py, amounts
    the ISO date reader reading on past the day              test_verify.py, dates
    the ISO date reader starting inside a longer year        test_verify.py, dates
    the numeric date reader reading on past the year         test_verify.py, dates
    the overlap merge keeping only the first passage's end   test_marks.py
    the card tagging its steps from the explanation          test_render.py
    a failed write reprinting a number that leads nowhere    test_memory_outage.py
    a truncated photograph escaping as a raw OSError         test_intake.py

The date sweep's three were planted after the first version of this note listed only the amount
ones and still said every sweep was covered. A note about proof that overstates the proof is the
one thing this file must not do.

That check is deliberately not a file in this repository. It edits tracked source and reverts with
git, which destroys uncommitted work, and it matches lines of source text, so it goes stale with
the next reformat. The durable protection is the control beside each sweep, and those were checked
the same way: break `is_truncated` so it detects nothing, or collapse a generator so a sweep runs
over nothing, or make every upload fixture expect the same answer, and a test fails. Redoing the
whole-path check is ten minutes of work: put each defect above back, run its test, expect red,
restore.
"""

from __future__ import annotations

import re


def digits_of(text: str, match: re.Match[str]) -> tuple[int, int] | None:
    """Where the number inside this match starts and ends in the text.

    The currency marker sits wholly on one side of the number in both orders, so the first and
    last digit of the match are the number's own edges.
    """
    inside = [index for index in range(*match.span()) if text[index].isdigit()]
    return (inside[0], inside[-1] + 1) if inside else None


def is_truncated(text: str, span: tuple[int, int]) -> str | None:
    """Why this span is only part of a longer number, or None when it is the whole one."""
    first, last = span
    if first > 0 and text[first - 1].isdigit():
        return "begins right after a digit"
    if last < len(text) and text[last].isdigit():
        return "ends right before a digit"
    return None
