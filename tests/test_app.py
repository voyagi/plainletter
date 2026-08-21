import base64

import pytest
from starlette.testclient import TestClient

from plainletter.app import MAX_UPLOAD_BYTES, LetterUpload, _decode, app, read_letter
from plainletter.demo import sample_text

TODAY = "2026-08-21"


def test_the_runtime_serves_the_letter_over_its_own_http_contract() -> None:
    # Not the handler on its own: the route AgentCore Runtime posts to, through the app it builds.
    with TestClient(app) as client:
        assert client.get("/ping").status_code == 200
        answer = client.post(
            "/invocations", json={"sample": "gemeente-parkeerboete", "today": TODAY}
        )

    assert answer.status_code == 200
    body = answer.json()
    assert body["reading"]["letter_type"] == "Naheffingsaanslag parkeerbelasting"
    assert body["reading"]["deadline"]["urgency"] == "due_soon"


def test_a_sample_letter_comes_back_read_checked_printed_and_datestamped() -> None:
    answer = read_letter({"sample": "cjib-verkeersboete", "today": TODAY})

    assert answer["source"] == "sample"
    assert answer["reading"]["sender_name"] == "Centraal Justitieel Incassobureau"
    assert answer["reading"]["deadline"]["on"] == "2026-09-15"
    assert "<!doctype html>" in answer["desk_card_html"]
    assert "BEGIN:VCALENDAR" in answer["reminder_ics"]


def test_the_answer_says_which_language_it_was_read_for() -> None:
    answer = read_letter({"sample": "belastingdienst-aanslag", "today": TODAY})
    languages = {item["language"] for item in answer["reading"]["explanations"]}
    assert languages == {"nl", "uk"}


def test_a_citizen_service_number_never_leaves_in_the_response() -> None:
    # The Belastingdienst sample prints one, and the reading quotes passages from the letter.
    answer = read_letter({"sample": "belastingdienst-aanslag", "today": TODAY})
    assert "1234 56 780" not in str(answer["reading"])


def test_an_empty_payload_is_answered_rather_than_crashed() -> None:
    assert read_letter({})["error"]["kind"] == "payload"


def test_asking_for_both_a_sample_and_a_letter_is_refused() -> None:
    answer = read_letter({"sample": "cjib-verkeersboete", "letter": {"text": "hallo"}})
    assert answer["error"]["kind"] == "payload"


def test_an_unknown_sample_names_the_ones_that_exist() -> None:
    answer = read_letter({"sample": "no-such-letter"})
    assert "cjib-verkeersboete" in answer["error"]["detail"]


def test_an_unknown_field_in_the_payload_is_refused() -> None:
    answer = read_letter({"sample": "cjib-verkeersboete", "modelId": "something-else"})
    assert answer["error"]["kind"] == "payload"


def test_a_broken_upload_is_named_as_an_upload_problem() -> None:
    answer = read_letter({"letter": {"filename": "a.pdf", "content_base64": "not base64 at all"}})
    assert answer["error"]["kind"] == "upload"


def test_an_upload_too_large_to_be_a_letter_is_refused_before_it_is_decoded() -> None:
    oversized = {"filename": "a.pdf", "content_base64": "A" * (MAX_UPLOAD_BYTES + 1)}
    assert read_letter({"letter": oversized})["error"]["kind"] == "upload"


@pytest.mark.parametrize(
    "payload", [{"letter": {"filename": "a.txt"}}, {"letter": {"text": "   "}}]
)
def test_a_letter_with_nothing_in_it_is_refused(payload: dict) -> None:
    assert "error" in read_letter(payload)


def test_an_uploaded_letter_arrives_with_its_own_words_intact() -> None:
    # Only the decode step: everything past it is a Bedrock call, which belongs to a live run and
    # not to a test suite.
    encoded = base64.b64encode(sample_text("cjib-verkeersboete").encode("utf-8")).decode("ascii")
    letter = _decode(LetterUpload(filename="brief.txt", content_base64=encoded))
    assert letter.kind == "text"
    assert letter.text is not None
    assert "Betaal voor 15 september 2026." in letter.text
