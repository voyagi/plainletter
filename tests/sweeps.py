"""The one thing the swept property tests share: how to tell a truncated number.

Two separate bugs in the grounding check had the same shape, one in the amount pattern and one in
the dates, so the rule that catches them is written once here and used from both.

    "EUR 123 4567"      matched "EUR 123 456"   the number ENDED just before a digit
    "in 2026 450 euro"  matched "26 450 euro"   the number BEGAN just after a digit

Both reported a value nobody wrote. The first refuses a correct reading; the second is worse,
because a mistyped amount whose truncation happens to equal a grounded one is waved through as
allowed. Neither was found by picking examples, and both were found by sweeping.
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
