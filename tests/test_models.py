"""The model id this build was checked against, and the probe that runs before anything is served.

The probe cannot catch a provider changing what an id points at. It catches the two things a
deployment can get wrong on its own: an id the region does not have, and an id nobody checked this
build against.
"""

from __future__ import annotations

from typing import Any

import pytest
from botocore.exceptions import ClientError, NoCredentialsError

from plainletter import app as runtime
from plainletter.bedrock import (
    READING_MODEL_ID,
    VERIFIED_MODEL_IDS,
    ModelCheck,
    probe_models,
)

REGION = "eu-central-1"


class KnowsEverything:
    def get_inference_profile(self, inferenceProfileIdentifier: str) -> dict[str, Any]:  # noqa: N803
        return {"inferenceProfileId": inferenceProfileIdentifier}


class KnowsNothing:
    def get_inference_profile(self, inferenceProfileIdentifier: str) -> dict[str, Any]:  # noqa: N803
        raise ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "no such profile"}},
            "GetInferenceProfile",
        )


class WillNotSay:
    def get_inference_profile(self, inferenceProfileIdentifier: str) -> dict[str, Any]:  # noqa: N803
        raise ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "not allowed"}},
            "GetInferenceProfile",
        )


class HasNoCredentials:
    def get_inference_profile(self, inferenceProfileIdentifier: str) -> dict[str, Any]:  # noqa: N803
        raise NoCredentialsError()


def test_the_reading_model_id_is_the_one_this_build_was_verified_against() -> None:
    assert READING_MODEL_ID in VERIFIED_MODEL_IDS
    # The 4.6 generation publishes no dated variant, so a date in the id would be an invention.
    assert READING_MODEL_ID == "eu.anthropic.claude-sonnet-4-6"


def test_a_model_the_region_knows_comes_back_reachable() -> None:
    [check] = probe_models((READING_MODEL_ID,), REGION, client=KnowsEverything())

    assert check.reachable is True
    assert check.as_verified is True


def test_a_model_the_region_does_not_have_comes_back_missing() -> None:
    [check] = probe_models(("eu.anthropic.claude-sonnet-9-9",), REGION, client=KnowsNothing())

    assert check.reachable is False
    assert check.as_verified is False


@pytest.mark.parametrize("client", [WillNotSay(), HasNoCredentials()])
def test_an_account_that_will_not_answer_is_unknown_rather_than_missing(client: Any) -> None:
    # The difference matters: unknown must never read as a missing model, or a read permission
    # nobody granted would take the desk down.
    [check] = probe_models((READING_MODEL_ID,), REGION, client=client)

    assert check.reachable is None


def test_the_server_refuses_to_start_against_a_model_that_does_not_resolve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "probe_models", lambda ids, region: _missing(ids))

    with pytest.raises(SystemExit) as refusal:
        runtime.check_models()

    assert READING_MODEL_ID in str(refusal.value)


def test_the_server_starts_when_the_account_will_not_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "probe_models", lambda ids, region: _unknown(ids))

    runtime.check_models()


def _missing(model_ids: tuple[str, ...]) -> tuple[ModelCheck, ...]:
    return tuple(ModelCheck(name, True, False, "ResourceNotFoundException") for name in model_ids)


def _unknown(model_ids: tuple[str, ...]) -> tuple[ModelCheck, ...]:
    return tuple(ModelCheck(name, True, None, "AccessDeniedException") for name in model_ids)
