"""Which ways of reaching somebody a step may carry.

Every accepted string below is one the live model actually produced on 2026-08-28, when twenty of
the twenty-two evaluation letters were refused because the planner had put the referral's phone and
its website into the one route field. Both halves came from the lookup; only the arrangement was
new. The refused strings are the property that must survive the fix: a number the LETTER printed is
still refused, however officially it is dressed.
"""

from __future__ import annotations

import pytest

from plainletter.kb import get_sender
from plainletter.pipeline import route_is_official

CJIB = get_sender("cjib")
assert CJIB is not None
PERMITTED = CJIB.route_values()

PHONE = "0800 8020"
SITE = "https://www.juridischloket.nl/"

# Written as codepoints rather than as the characters, the way `schemas.py` writes its dash rule: a
# hyphen, an en dash and an em dash are three different characters that look nearly identical in an
# editor, and the live model reached for all three. A test that turns on which one is which should
# not depend on anyone spotting the difference by eye.
EN_DASH = chr(0x2013)
EM_DASH = chr(0x2014)


def test_the_lookups_own_values_are_in_the_permitted_set() -> None:
    # If this ever fails the rest of the file is testing nothing.
    assert PHONE in PERMITTED
    assert SITE in PERMITTED


@pytest.mark.parametrize(
    "route",
    [
        PHONE,
        SITE,
        # The eleven arrangements the live run produced, verbatim.
        f"{PHONE} | {SITE}",
        f"{PHONE} {EN_DASH} {SITE}",
        f"Telefoon: {PHONE} | Website: {SITE}",
        f"{SITE} | telefoon: {PHONE}",
        f"{SITE} {EM_DASH} telefoon: {PHONE}",
        f"{SITE} | Telefoon: {PHONE}",
        f"{PHONE} {EN_DASH} Het Juridisch Loket | {SITE}",
        f"Het Juridisch Loket: {PHONE} | {SITE}",
        f"Het Juridisch Loket {EN_DASH} {PHONE} | {SITE}",
        f"{SITE}, of bel {PHONE}",
        f"  {SITE}  ",
    ],
)
def test_a_route_built_only_from_lookup_values_is_allowed(route: str) -> None:
    assert route_is_official(route, PERMITTED)


@pytest.mark.parametrize(
    "route",
    [
        # The attack: a number printed on the letter, wearing an official one for cover.
        f"{PHONE} of bel 0900 123 456",
        f"{SITE} of https://juridischloket-spoed.nl/",
        f"Het Juridisch Loket {PHONE}, spoed: 0900 448 2211",
        "0900 123 456",
        "https://spoedbetaling-belastingdienst.nl/",
        "bel het nummer op de brief: 0900 12 34 567",
        "post@juridischloket-spoed.nl",
        "www.juridischloket-spoed.nl",
        # No digit, no @, no scheme and no www, and still somewhere to send a frightened person.
        "spoedbetaling-belastingdienst.nl",
        f"{SITE} of juridischloket-spoed.nl",
        f"Het Juridisch Loket {PHONE}, of ga naar belastingdienst-spoed.eu",
    ],
)
def test_a_route_carrying_anything_the_lookup_did_not_give_is_refused(route: str) -> None:
    assert not route_is_official(route, PERMITTED)


def test_a_sender_the_knowledge_base_does_not_carry_gets_no_route_at_all() -> None:
    # An unknown sender has an empty permitted set, so nothing is removed and any way of reaching
    # somebody survives to be refused. A route with no contact detail in it is still pointless but
    # is not a danger, which is why it passes.
    assert not route_is_official(PHONE, frozenset())
    assert not route_is_official(SITE, frozenset())
    assert route_is_official("vraag het aan de balie", frozenset())


def test_a_value_that_contains_another_is_removed_whole() -> None:
    # Longest first. Removing the short one first would leave the tail of the long one behind, and
    # a leftover fragment with digits in it would refuse a route that was entirely official.
    permitted = frozenset({"0800 8020", "0800 8020 12"})
    assert route_is_official("0800 8020 12", permitted)
