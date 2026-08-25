"""Folding a letter's text so two copies of the same passage compare equal.

Nothing here knows which country the letter came from. It is character handling: composition,
case folding, whitespace collapsing, and the offset map that lets a fold be undone well enough to
draw a mark back onto the original.

The offsets are the reason this is not two lines of `str.lower()`. Marking a passage means pointing
at characters, and every fold changes how many characters there are, so the fold has to carry a map
back to the letter the desk actually displays.
"""

from __future__ import annotations

import re
import unicodedata

# Written as codepoints rather than as the characters themselves. Both are invisible or nearly so
# in an editor, and a rule that turns on a character nobody can see is a rule nobody can review.
SOFT_HYPHEN = chr(0x00AD)
RIGHT_SINGLE_QUOTE = chr(0x2019)

_WHITESPACE = re.compile(r"\s")


def canonical(text: str) -> str:
    """The composed form of a letter that everything downstream treats as the letter itself.

    Marking a passage means pointing at characters, and NFKC composition changes how many
    characters there are. Composing once, at the edge, keeps the offsets a mark carries indexing
    the same string the desk displays instead of one that no longer exists.
    """
    return unicodedata.normalize("NFKC", text)


def fold_with_offsets(text: str) -> tuple[str, tuple[int, ...]]:
    """Fold canonical text for comparison, keeping each folded character's index in the input.

    `normalise` is this function's output with the map thrown away, so the two cannot disagree
    about whether a passage matches. That matters more than it looks: a mark that fails to place
    where the verifier succeeded prints a missing numeral, and a missing numeral is this product's
    way of saying the letter does not contain the fact.
    """
    folded: list[str] = []
    offsets: list[int] = []
    for index, char in enumerate(text):
        if char == SOFT_HYPHEN:
            continue
        piece = "'" if char == RIGHT_SINGLE_QUOTE else char
        if _WHITESPACE.match(piece):
            if folded and folded[-1] == " ":
                continue
            folded.append(" ")
            offsets.append(index)
            continue
        for expanded in piece.casefold():
            folded.append(expanded)
            offsets.append(index)

    start = 1 if folded and folded[0] == " " else 0
    end = len(folded) - 1 if folded and folded[-1] == " " else len(folded)
    return "".join(folded[start:end]), tuple(offsets[start:end])


def normalise(text: str) -> str:
    """Fold a passage to the form the grounding check compares on.

    Photographed text arrives with soft hyphens, non-breaking spaces and line breaks in places the
    model does not reproduce, so a raw equality test fails on passages that are plainly the same.
    """
    return fold_with_offsets(canonical(text))[0]


def passage_is_in(letter_text: str, passage: str) -> bool:
    """True when the passage really stands in the letter, whitespace and hyphens aside."""
    needle = normalise(passage)
    return bool(needle) and needle in normalise(letter_text)
