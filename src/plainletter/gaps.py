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

# A visitor-language text can translate the marker: beside "4471 [onleesbaar] 6" the deployed
# planner wrote the Ukrainian word in the same brackets (examples/unreadable-reference).
# So the recorded partial value is also matched with any short bracketed phrase where its marker
# stands, but only when what was read of it holds this many digits: a shorter pattern would match
# ordinary text, such as a count of days beside a bracket.
_ANY_MARKER = r"(?:\[[^\[\]\n]{1,40}\]|\([^()\n]{1,40}\))"
_MIN_DIGITS_READ = 3


def has_gap(text: str) -> bool:
    """Whether this text carries a value the reading could only partly read."""
    return active().words.unreadable_marker in text


def fill_gaps(text: str, placeholder: str, partial: str | None = None) -> str:
    """The text with every partly read value replaced by the placeholder.

    The partial value as the reading recorded it goes first, with any spacing, so a prefix with no
    digit in it ("NP 4471 <marker> 8") goes with the rest of the number, and then the same value
    with its marker translated. Whatever is left around a marker after that is taken out by shape.
    """
    marker = active().words.unreadable_marker
    if partial and has_gap(partial):
        written = r"\s*".join(re.escape(piece) for piece in partial.split())
        text = re.sub(written, lambda _: placeholder, text)
        translated = _translated(partial)
        if translated is not None:
            text = translated.sub(lambda _: placeholder, text)
    # Walked outward from each marker rather than matched with one pattern: a pattern for "pieces
    # with a digit, any number of them" backtracks badly over a long run of digits and spaces.
    found = text.find(marker)
    while found >= 0:
        start = _widen_left(text, found)
        end = _widen_right(text, found + len(marker))
        text = text[:start] + placeholder + text[end:]
        found = text.find(marker, start + len(placeholder))
    return text


def read_part(value: str) -> str:
    """What was read of a partly read value, its spacing dropped and each gap written as "?".

    Two readings of the same letter can space a gap differently, and the part they read stays the
    same, so this is what identifies the value.
    """
    marker = active().words.unreadable_marker
    return "?".join("".join(part.split()) for part in value.split(marker))


def _translated(partial: str) -> re.Pattern[str] | None:
    """The partial value with any short bracketed phrase where its marker stands, or None."""
    parts = partial.split(active().words.unreadable_marker)
    if sum(char.isdigit() for char in "".join(parts)) < _MIN_DIGITS_READ:
        return None
    pieces = (r"\s*".join(re.escape(token) for token in part.split()) for part in parts)
    return re.compile(r"(?<!\w)" + (r"\s*" + _ANY_MARKER + r"\s*").join(pieces) + r"(?!\w)")


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
    """Each step that quotes a gap, in either language, asks for the whole number first instead."""
    words = active().words

    def complete(step: ActionStep) -> ActionStep:
        dutch = fill_gaps(step.dutch, words.unreadable_in_step, partial)
        visitor = fill_gaps(step.visitor, words.unreadable_in_step, partial)
        if dutch == step.dutch and visitor == step.visitor:
            return step
        return step.model_copy(
            update={"dutch": f"{words.unreadable_step_lead} {dutch}", "visitor": visitor}
        )

    return tuple(complete(step) for step in steps)


def draft_without_gaps(draft: DraftLetter | None, partial: str | None = None) -> DraftLetter | None:
    """The draft with a marked place to write the whole number where it quoted a part of one."""
    if draft is None:
        return None
    placeholder = active().words.unreadable_in_draft
    dutch = fill_gaps(draft.dutch, placeholder, partial)
    visitor = fill_gaps(draft.visitor, placeholder, partial)
    if dutch == draft.dutch and visitor == draft.visitor:
        return draft
    return draft.model_copy(update={"dutch": dutch, "visitor": visitor})
