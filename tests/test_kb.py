from urllib.parse import urlparse

from plainletter.kb import known_sender_ids, load_senders

VERIFIED = {"cjib", "belastingdienst", "gemeente"}


def test_every_sender_file_loads_and_ids_are_unique() -> None:
    senders = load_senders()
    assert len(senders) == len(known_sender_ids())
    assert set(senders) >= VERIFIED


def test_only_the_senders_whose_procedure_was_checked_are_marked_verified() -> None:
    # The claim this file makes is exactly as strong as the checking behind it. A sender flips to
    # verified when somebody reads its official page, not when the entry looks complete.
    senders = load_senders()
    assert {sid for sid, sender in senders.items() if sender.verified} == VERIFIED


def test_a_verified_sender_carries_a_source_for_every_procedural_claim() -> None:
    for sender_id in VERIFIED:
        sender = load_senders()[sender_id]
        assert sender.sources(), f"{sender_id} claims to be verified with no sources"
        for url in sender.sources():
            parsed = urlparse(url)
            assert parsed.scheme == "https", f"{sender_id} cites a non-https source: {url}"
            assert parsed.netloc


def test_an_unverified_sender_states_no_procedure_at_all() -> None:
    for sender in load_senders().values():
        if sender.verified:
            continue
        assert sender.objection is None
        assert sender.payment is None
        assert sender.consequences == ()
        assert sender.handoff_reason_en


def test_every_sender_names_somewhere_a_person_can_go() -> None:
    for sender_id, sender in load_senders().items():
        assert sender.referrals, f"{sender_id} has no referral"
