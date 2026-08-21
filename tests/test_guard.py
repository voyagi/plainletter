from typing import Any

from strands.interventions import Deny, Proceed

from plainletter.guard import GroundingGuard

ALLOWED = frozenset({"EUR 174,00", "15 september 2026"})


class FakeEvent:
    """The one field the guard reads off a before-tool-call event."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.tool_use = {"toolUseId": "t1", "name": "send_reminder", "input": payload}


def test_a_call_carrying_only_grounded_values_proceeds() -> None:
    event = FakeEvent({"amount": "EUR 174,00", "deadline": "15 september 2026"})
    assert isinstance(GroundingGuard(ALLOWED).before_tool_call(event), Proceed)


def test_a_call_carrying_an_invented_date_is_denied() -> None:
    event = FakeEvent({"deadline": "1 oktober 2026"})
    action = GroundingGuard(ALLOWED).before_tool_call(event)
    assert isinstance(action, Deny)
    assert "1 oktober 2026" in action.reason


def test_a_call_carrying_an_invented_amount_is_denied() -> None:
    event = FakeEvent({"body": "Het totaal is EUR 999,00."})
    action = GroundingGuard(ALLOWED).before_tool_call(event)
    assert isinstance(action, Deny)
    assert "EUR 999,00" in action.reason


def test_a_number_that_is_neither_a_date_nor_an_amount_is_not_the_guards_business() -> None:
    # Reference numbers, phone numbers and house numbers travel freely; the guard is about the two
    # values somebody acts on.
    event = FakeEvent({"reference": "8194 5523 7761", "phone": "0800 8020"})
    assert isinstance(GroundingGuard(ALLOWED).before_tool_call(event), Proceed)


def test_the_guard_fails_closed_when_its_own_check_breaks() -> None:
    assert GroundingGuard(ALLOWED).on_error == "deny"


def test_the_guard_reads_nested_arguments_too() -> None:
    event = FakeEvent({"card": {"lines": ["betaal voor 1 oktober 2026"]}})
    assert isinstance(GroundingGuard(ALLOWED).before_tool_call(event), Deny)
