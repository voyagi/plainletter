"""The EU-only promise, made mechanical.

docs/deploy.md states as a fact that nothing is deployed outside the EU. It was a fact about the
deployment only: AWS_REGION is an alias for the region field, every AWS execution environment sets
it, and it beat the Frankfurt default silently, so the model was built for whatever region the
shell named.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from plainletter import settings as settings_module
from plainletter.bedrock import SOURCE_REGION
from plainletter.settings import Settings


@pytest.fixture(autouse=True)
def _no_ambient_region(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("AWS_REGION", "AWS_DEFAULT_REGION", "PLAINLETTER_REGION"):
        monkeypatch.delenv(name, raising=False)
    settings_module.settings.cache_clear()


def test_the_default_is_frankfurt() -> None:
    assert Settings().region == SOURCE_REGION
    assert SOURCE_REGION.startswith("eu-")


@pytest.mark.parametrize("variable", ["AWS_REGION", "PLAINLETTER_REGION"])
@pytest.mark.parametrize("outside", ["us-east-1", "ap-southeast-2", "sa-east-1"])
def test_a_region_outside_the_eu_refuses_to_start(
    variable: str, outside: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(variable, outside)
    with pytest.raises(ValidationError) as refused:
        Settings()
    assert outside in str(refused.value)
    assert "EU" in str(refused.value)


@pytest.mark.parametrize("inside", ["eu-central-1", "eu-west-1", "eu-north-1"])
def test_control_another_eu_region_is_allowed(inside: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # The rule is the European Union, not one city: a deployment moved to Ireland is still inside
    # the promise and must not be refused.
    monkeypatch.setenv("PLAINLETTER_REGION", inside)
    assert Settings().region == inside
