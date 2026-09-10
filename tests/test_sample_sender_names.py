"""A sender's name must survive into the visitor's language, sentence by sentence.

The visitor is holding the paper letter. The only way they can tell that the
explanation in front of them is about THAT envelope is by matching the sender's
name across the two. Translating the name breaks that link, and it can do worse:
one sample rendered SVB as a real Turkish institution, so the reader was told a
Turkish body had written to them.

The pairing is per field on purpose. A first version of this test joined every
field into one string and asked whether the name appeared anywhere in it, and
that version stayed green with the defect planted back, because the same name
survived in a different sentence. Each Dutch field is checked against the visitor
field that says the same thing.
"""

from collections.abc import Iterator

import pytest

from plainletter.demo import sample_names, scripted_reading
from plainletter.kb import get_sender

# Short names that are ordinary Dutch common nouns rather than names. A visitor
# matches "gemeente" against the envelope by its logo, not its spelling, and
# translating the word for "municipality" is the right thing to do. Every other
# short name in the knowledge base is a name or an abbreviation and stays put.
# A new sender with a generic short name fails this test until it is listed here,
# which is the correct way round: the decision is a person's, not a default.
GENERIC_DUTCH_NOUNS = frozenset({"Gemeente", "Deurwaarder", "Waterschap", "Zorgverzekeraar"})


def paired_fields(name: str) -> Iterator[tuple[str, str, str]]:
    """Every (label, Dutch text, visitor text) pair the desk shows side by side."""
    reading = scripted_reading(name)
    by_language = {e.language: e for e in reading.explanations}
    dutch = by_language.get("nl")
    visitor = by_language.get(reading.visitor_language)

    if dutch is not None and visitor is not None:
        for field in ("what_is_this", "by_when", "if_you_do_nothing"):
            yield field, str(getattr(dutch, field)), str(getattr(visitor, field))

    for step in reading.steps:
        yield f"step {step.order}", str(step.dutch), str(step.visitor)

    if reading.draft is not None:
        yield "draft", str(reading.draft.dutch), str(reading.draft.visitor)


@pytest.mark.parametrize("name", sample_names())
def test_the_senders_name_reaches_the_visitor_in_their_own_language(name: str) -> None:
    reading = scripted_reading(name)
    sender = get_sender(reading.facts.sender_id)
    assert sender is not None, f"{name} names a sender the knowledge base does not have"

    if sender.short_name in GENERIC_DUTCH_NOUNS:
        pytest.skip(f"{sender.short_name} is a category, not a name")

    dropped = [
        label
        for label, dutch, visitor in paired_fields(name)
        if sender.short_name in dutch and sender.short_name not in visitor
    ]

    assert not dropped, (
        f"{name}: {sender.short_name} stands in the Dutch {', '.join(dropped)} and not in the "
        f"{reading.visitor_language} beside it, so the visitor cannot match the explanation "
        f"to the envelope in their hand"
    )


def test_at_least_one_sample_actually_exercises_this_check() -> None:
    """A test that skips or matches nothing is not a test. Prove the check has work."""
    exercised = [
        name
        for name in sample_names()
        if (sender := get_sender(scripted_reading(name).facts.sender_id)) is not None
        and sender.short_name not in GENERIC_DUTCH_NOUNS
        and any(sender.short_name in dutch for _, dutch, _ in paired_fields(name))
    ]
    assert len(exercised) >= 5, f"only {len(exercised)} samples reach the assertion"


def test_every_generic_name_on_the_exemption_list_is_still_a_real_sender() -> None:
    """Stop the exemption list rotting into a list of names nothing checks."""
    short_names = {
        sender.short_name
        for name in sample_names()
        if (sender := get_sender(scripted_reading(name).facts.sender_id)) is not None
    }
    stale = GENERIC_DUTCH_NOUNS - short_names
    assert not stale, f"exempted names that no sample uses any more: {sorted(stale)}"
