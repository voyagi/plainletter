from plainletter.kb import load_senders
from plainletter.locales.nl import NL
from plainletter.tools import (
    UNKNOWN_SENDER_NOTE,
    UNVERIFIED_SENDER_NOTE,
    VERIFIED_SENDER_NOTE,
    official_routes,
)


def test_a_verified_sender_returns_its_routes_with_their_sources() -> None:
    routes = official_routes(sender_id="cjib")
    assert routes.known and routes.verified
    assert routes.objection is not None
    assert routes.objection.window_days == 42
    assert routes.objection.source.startswith("https://www.om.nl/")
    assert routes.payment is not None and routes.payment.payment_plan
    assert routes.referrals[0].name == "Het Juridisch Loket"
    assert routes.note == VERIFIED_SENDER_NOTE


def test_an_unverified_sender_says_so_instead_of_stating_a_procedure() -> None:
    unverified = next(sender for sender in load_senders().values() if not sender.verified)
    routes = official_routes(sender_id=unverified.id)
    assert routes.known and not routes.verified
    assert routes.note == UNVERIFIED_SENDER_NOTE


def test_a_sender_outside_the_knowledge_base_is_an_answer_not_an_error() -> None:
    routes = official_routes(sender_id="bank-of-nowhere")
    assert not routes.known
    assert routes.objection is None and routes.payment is None and routes.referrals == ()
    # The body of last resort comes from the locale, so the note the model reads names a real one
    # rather than a placeholder.
    assert routes.note == UNKNOWN_SENDER_NOTE.format(referral=NL.words.referral_last_resort)
    assert "{referral}" not in routes.note


def test_the_tool_tells_the_model_what_it_is_for() -> None:
    spec = official_routes.tool_spec
    assert spec["name"] == "official_routes"
    assert "official page it was read on" in " ".join(spec["description"].split())
    assert list(spec["inputSchema"]["json"]["properties"]) == ["sender_id"]
