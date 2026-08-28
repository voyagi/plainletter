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
from plainletter.pipeline import (
    UnofficialRouteError,
    official_steps,
    route_is_official,
    single_route,
)
from plainletter.schemas import ActionStep

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


@pytest.mark.parametrize(
    "route",
    [
        # An internationalised host is still a host. An ASCII-only pattern would have let one
        # through on the strength of the alphabet it was written in.
        "例子.测试",
        "税務署.jp",
        f"{PHONE} of ga naar例子.测试",
    ],
)
def test_a_route_naming_an_internationalised_host_is_refused(route: str) -> None:
    assert not route_is_official(route, PERMITTED)


@pytest.mark.parametrize(
    ("route", "kept"),
    [
        (f"{PHONE} | {SITE}", PHONE),
        (f"{SITE} | telefoon: {PHONE}", SITE),
        (f"Telefoon: {PHONE} | Website: {SITE}", PHONE),
        (f"Het Juridisch Loket {EN_DASH} {PHONE} | {SITE}", PHONE),
        (PHONE, PHONE),
        (SITE, SITE),
    ],
)
def test_a_combined_route_is_reduced_to_the_first_value_in_it(route: str, kept: str) -> None:
    """Accepting a combined route is not the same as printing one.

    The console renders this field as the target of a link and the card prints it as the one place
    to go, so a string holding two of them is a dead link in front of a frightened person. The first
    one wins, which keeps the order the planner chose.
    """
    assert single_route(route, PERMITTED) == kept


def test_a_route_with_nothing_from_the_lookup_in_it_is_left_for_the_check_to_refuse() -> None:
    assert single_route("0900 123 456", PERMITTED) is None


def test_two_permitted_routes_sharing_a_prefix_keep_the_longer_one() -> None:
    """Both match at position zero, and picking on the string would take the shorter.

    A knowledge base carrying a page and a deeper page under it is ordinary, and handing back the
    shallower one sends the visitor somewhere official and wrong, which is the harder mistake to
    notice of the two.
    """
    page = "https://example.test/"
    deeper = "https://example.test/betalingsregeling"
    permitted = frozenset({page, deeper})

    assert single_route(f"{deeper} of bel de balie", permitted) == deeper
    assert single_route(f"{page} of bel de balie", permitted) == page


def test_the_steps_that_leave_the_pipeline_carry_one_route_each() -> None:
    combined = ActionStep(
        order=1,
        dutch="Bel het Juridisch Loket of kijk op de website.",
        visitor="Hukuk Burosunu arayin veya web sitesine bakin.",
        official_route=f"{PHONE} | {SITE}",
    )
    plain = ActionStep(order=2, dutch="Betaal de boete.", visitor="Cezayi odeyin.")

    kept = official_steps((combined, plain), CJIB)

    assert kept[0].official_route == PHONE
    assert kept[0].dutch == combined.dutch, "only the route field is touched"
    assert kept[1].official_route is None


def test_an_invented_route_still_refuses_the_whole_reading() -> None:
    step = ActionStep(
        order=1,
        dutch="Bel 0900 123 456.",
        visitor="0900 123 456 numarasini arayin.",
        official_route="0900 123 456",
    )
    with pytest.raises(UnofficialRouteError):
        official_steps((step,), CJIB)


def test_a_value_that_contains_another_is_removed_whole() -> None:
    # Longest first. Removing the short one first would leave the tail of the long one behind, and
    # a leftover fragment with digits in it would refuse a route that was entirely official.
    permitted = frozenset({"0800 8020", "0800 8020 12"})
    assert route_is_official("0800 8020 12", permitted)
