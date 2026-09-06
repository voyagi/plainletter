"""Drawing the marks on the letter, and numbering them.

The product's one sharp claim is that nothing reaches the visitor unless it stands in their letter.
This module is where that claim becomes something a person can point at: every passage the verifier
grounded gets a highlighter wash and a numeral in the margin, in the order the passages appear down
the page, and a passage the verifier could not ground gets nothing at all.

The absence is the feature. A colour can be misread and a warning can be skipped, but a missing
numeral cannot be mistaken for a fact, which is why the broken key is a gap in the margin rather
than a red badge.

Matching uses the same fold the verifier used, from the same function, so the two cannot disagree
about whether a passage is in the letter. When a grounded passage still fails to place, that is a
bug rather than a finding, so it is recorded in `unplaced` and the test suite refuses it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .redact import redact
from .schemas import (
    LetterFacts,
    LetterLine,
    LetterRun,
    MarkedLetter,
    MarkKey,
    VerificationResult,
)
from .text import canonical, fold_with_offsets, normalise


@dataclass(frozen=True)
class _Placement:
    start: int
    end: int
    text: str
    facts: tuple[str, ...]


def mark_letter(letter_text: str, facts: LetterFacts, result: VerificationResult) -> MarkedLetter:
    """Number every grounded passage down the letter and split the letter around them.

    Redaction happens to the whole letter before it is split, never to the pieces afterwards: a
    citizen service number that straddled a split would survive a per-piece mask, and the whole
    point of masking is that it has no exceptions. The passages are folded through the same mask so
    both sides of the comparison carry it.
    """
    letter = redact(canonical(letter_text))
    folded, offsets = fold_with_offsets(letter)

    placements, unplaced = _place(letter, folded, offsets, result)
    keys = tuple(
        MarkKey(number=number, text=item.text, facts=item.facts)
        for number, item in enumerate(placements, start=1)
    )
    gap_lines = _gap_lines(letter, facts)

    return MarkedLetter(
        lines=_split_lines(letter, placements, gap_lines),
        keys=keys,
        gaps=facts.unreadable,
        unplaced=unplaced,
    )


def _place(
    letter: str, folded: str, offsets: tuple[int, ...], result: VerificationResult
) -> tuple[tuple[_Placement, ...], tuple[str, ...]]:
    """Locate each grounded passage once, covering both when two of them overlap."""
    found: dict[str, _Placement] = {}
    unplaced: list[str] = []

    for fact in result.grounded:
        needle = normalise(redact(fact.span.text))
        if not needle:
            unplaced.append(fact.name)
            continue
        existing = found.get(needle)
        if existing is not None:
            found[needle] = _Placement(
                existing.start, existing.end, existing.text, (*existing.facts, fact.name)
            )
            continue
        at = folded.find(needle)
        if at < 0:
            unplaced.append(fact.name)
            continue
        start = offsets[at]
        end = offsets[at + len(needle) - 1] + 1
        found[needle] = _Placement(start, end, fact.span.text, (fact.name,))

    # Longest first at a shared start, so a passage quoted both whole and in part keeps the whole
    # one and the part folds into it rather than cutting the wash in two.
    ordered = sorted(found.values(), key=lambda item: (item.start, -item.end))
    kept: list[_Placement] = []
    for item in ordered:
        if kept and item.start < kept[-1].end:
            kept[-1] = _merged(letter, kept[-1], item)
            continue
        kept.append(item)
    return tuple(kept), tuple(unplaced)


def _merged(letter: str, previous: _Placement, item: _Placement) -> _Placement:
    """Two passages that touch, as one mark that really covers both of them.

    Nesting is the easy case and the sort makes it the common one. Two passages that merely
    overlap are the case worth writing down. The model picks its own spans, so a deadline whose
    span runs to the middle of a sentence and an amount whose span starts in that same middle and
    runs past its end are an ordinary pair. Keeping only the first one's end left the amount
    outside the wash while its name was still listed under that numeral, so the key pointed the
    volunteer at words that do not contain the value. Nothing reported it either: the passage had
    been found, so it never reached `unplaced`.

    When the range grows, the key's text has to grow with it, and it comes from the letter rather
    than from either span, because neither span is the merged passage.
    """
    facts = previous.facts + item.facts
    if item.end <= previous.end:
        return _Placement(previous.start, previous.end, previous.text, facts)
    return _Placement(previous.start, item.end, letter[previous.start : item.end], facts)


def _split_lines(
    letter: str, placements: tuple[_Placement, ...], gap_lines: frozenset[int]
) -> tuple[LetterLine, ...]:
    lines: list[LetterLine] = []
    cursor = 0
    for index, text in enumerate(letter.split("\n")):
        line_start, line_end = cursor, cursor + len(text)
        cursor = line_end + 1
        runs, mark = _runs_for(text, line_start, line_end, placements)
        lines.append(LetterLine(runs=runs, mark=mark, gap=index in gap_lines and mark is None))
    return tuple(lines)


def _runs_for(
    text: str, line_start: int, line_end: int, placements: tuple[_Placement, ...]
) -> tuple[tuple[LetterRun, ...], int | None]:
    """Cut one line into marked and unmarked runs, and say which numeral goes in its margin.

    A passage that wraps over several lines washes each of them but writes its numeral once, beside
    the line it starts on, which is where a hand would have written it.
    """
    runs: list[LetterRun] = []
    mark: int | None = None
    position = line_start
    for number, item in enumerate(placements, start=1):
        if item.end <= line_start or item.start >= line_end:
            continue
        overlap_start = max(item.start, line_start)
        overlap_end = min(item.end, line_end)
        if overlap_start > position:
            runs.append(LetterRun(text=text[position - line_start : overlap_start - line_start]))
        runs.append(
            LetterRun(text=text[overlap_start - line_start : overlap_end - line_start], mark=number)
        )
        position = overlap_end
        if mark is None and item.start >= line_start:
            mark = number
    if position < line_end:
        runs.append(LetterRun(text=text[position - line_start :]))
    return tuple(run for run in runs if run.text), mark


def _gap_lines(letter: str, facts: LetterFacts) -> frozenset[int]:
    """The lines a broken key belongs beside: the ones naming a field the desk could not read."""
    lines = letter.split("\n")
    folded_lines = [normalise(line) for line in lines]
    gaps: set[int] = set()
    for item in facts.unreadable:
        needle = normalise(item.field)
        if not needle:
            continue
        for index, line in enumerate(folded_lines):
            if needle in line:
                gaps.add(index)
                break
    return frozenset(gaps)
