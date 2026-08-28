"""Short hashes of the two things a score depends on: the prompts, and the letters.

A saved run is only comparable with another one if you can tell what moved between them. Without
these, two files showing 17 and 19 could differ because a prompt changed, because a letter was
edited, or because the model answered differently on a Tuesday, and there is no way back from the
number to the reason.

They are short on purpose. This is a label for a run, not a signature on it.
"""

from __future__ import annotations

import hashlib

from plainletter.reading_model import (
    DRAFT_PROMPT,
    EXPLAIN_PROMPT,
    PLAN_PROMPT,
    READING_PROMPT,
    TRANSCRIBE_PROMPT,
)

from .cases import LETTERS_DIR, slugs

LENGTH = 12


def _short(parts: list[bytes]) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(len(part).to_bytes(4, "big"))
        digest.update(part)
    return digest.hexdigest()[:LENGTH]


def prompts() -> str:
    """The five system prompts, in a fixed order, exactly as the product will send them."""
    return _short(
        [
            prompt.encode("utf-8")
            for prompt in (
                TRANSCRIBE_PROMPT,
                READING_PROMPT,
                EXPLAIN_PROMPT,
                PLAN_PROMPT,
                DRAFT_PROMPT,
            )
        ]
    )


def corpus() -> str:
    """Every letter and every expectation file, in slug order."""
    parts: list[bytes] = []
    for slug in slugs():
        parts.append(slug.encode("utf-8"))
        parts.append((LETTERS_DIR / f"{slug}.txt").read_bytes())
        parts.append((LETTERS_DIR / f"{slug}.expected.yaml").read_bytes())
    return _short(parts)
