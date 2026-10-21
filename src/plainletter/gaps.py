"""What the writing stages do with a value the reading could only partly read.

The reading writes the locale's unreadable marker into a value where part of it could not be read,
and that marker is the one signal that holds whatever else the model writes: the field name of an
`unreadable` entry is free prose and cannot be matched to the fact it is about. A number with a gap
in it is not a number anybody can pay or object with. A payment quoting it may never be matched to
the assessment, and an objection quoting it may never reach the right file.

So wherever a step or a draft quotes a gap, the partial number is taken out and a marked place to
fill in the whole one is put in. The planner and the drafter are asked for neither; a prompt is a
preference, and this is the check.
"""

from __future__ import annotations

import re

from .locales import active
from .schemas import ActionStep, DraftLetter

# A number around a marker is the run of pieces holding a digit on either side of it, joined by
# spaces or written against it. "4471 <marker> 6" goes whole, and a word with no digit in it stops
# the run, so the sentence around the number is kept.
# A line break ends the run: the next line is another passage of the letter, not more of the number.
_PIECE_CHARS = frozenset("_/-")
_SPACES = frozenset(" \t\u00a0")


def has_gap(text: str) -> bool:
    """Whether this text carries a value the reading could only partly read."""
    return active().words.unreadable_marker in text


def fill_gaps(text: str, placeholder: str, partial: str | None = None) -> str:
    """The text with every partly read value replaced by the placeholder.

    The partial value as the reading recorded it goes first, with any spacing, so a prefix with no
    digit in it ("NP 4471 <marker> 8") goes with the rest of the number. Whatever is left around
    a marker after that is taken out by shape.
    """
    marker = active().words.unreadable_marker
    if partial and has_gap(partial):
        written = r"\s*".join(re.escape(piece) for piece in partial.split())
        text = re.sub(written, lambda _: placeholder, text)
    # Walked outward from each marker rather than matched with one pattern: a pattern for "pieces
    # with a digit, any number of them" backtracks badly over a long run of digits and spaces.
    found = text.find(marker)
    while found >= 0:
        start = _widen_left(text, found)
        end = _widen_right(text, found + len(marker))
        text = text[:start] + placeholder + text[end:]
        found = text.find(marker, start + len(placeholder))
    return text


def _is_piece(char: str) -> bool:
    return char.isalnum() or char in _PIECE_CHARS


def _widen_left(text: str, start: int) -> int:
    while True:
        gap = start
        while gap > 0 and text[gap - 1] in _SPACES:
            gap -= 1
        piece = gap
        while piece > 0 and _is_piece(text[piece - 1]):
            piece -= 1
        if not any(char.isdigit() for char in text[piece:gap]):
            return start
        start = piece


def _widen_right(text: str, end: int) -> int:
    while True:
        gap = end
        while gap < len(text) and text[gap] in _SPACES:
            gap += 1
        piece = gap
        while piece < len(text) and _is_piece(text[piece]):
            piece += 1
        if not any(char.isdigit() for char in text[gap:piece]):
            return end
        end = piece


def steps_without_gaps(
    steps: tuple[ActionStep, ...], partial: str | None = None
) -> tuple[ActionStep, ...]:
    """Each step that quotes a gap asks for the whole number first instead of quoting the part."""
    words = active().words

    def complete(step: ActionStep) -> ActionStep:
        if not (has_gap(step.dutch) or has_gap(step.visitor)):
            return step
        return step.model_copy(
            update={
                "dutch": (
                    f"{words.unreadable_step_lead} "
                    f"{fill_gaps(step.dutch, words.unreadable_in_step, partial)}"
                ),
                "visitor": fill_gaps(step.visitor, words.unreadable_in_step, partial),
            }
        )

    return tuple(complete(step) for step in steps)


def draft_without_gaps(draft: DraftLetter | None, partial: str | None = None) -> DraftLetter | None:
    """The draft with a marked place to write the whole number where it quoted a part of one."""
    if draft is None or not (has_gap(draft.dutch) or has_gap(draft.visitor)):
        return draft
    placeholder = active().words.unreadable_in_draft
    return draft.model_copy(
        update={
            "dutch": fill_gaps(draft.dutch, placeholder, partial),
            "visitor": fill_gaps(draft.visitor, placeholder, partial),
        }
    )
