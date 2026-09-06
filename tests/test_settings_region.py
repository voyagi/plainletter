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
@pytest.mark.parametrize(
    "outside",
    [
        "us-east-1",
        "ap-southeast-2",
        "sa-east-1",
        # AWS calls these "Europe" and they begin with eu-, but the promise is the Union. The
        # United Kingdom left it and Switzerland was never in it, so a prefix check would have
        # read a letter in either while the page still said EU.
        "eu-west-2",
        "eu-central-2",
    ],
)
def test_a_region_outside_the_eu_refuses_to_start(
    variable: str, outside: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(variable, outside)
    with pytest.raises(ValidationError) as refused:
        Settings()
    assert outside in str(refused.value)
    assert "EU" in str(refused.value)


@pytest.mark.parametrize(
    "inside", ["eu-central-1", "eu-west-1", "eu-west-3", "eu-north-1", "eu-south-1", "eu-south-2"]
)
def test_control_every_member_state_region_is_allowed(
    inside: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The control, and it is the half that keeps the check honest: the rule is the European Union,
    # not one city. A deployment moved to Ireland or Paris is still inside the promise, so a check
    # that refused everything would pass the test above and fail this one.
    monkeypatch.setenv("PLAINLETTER_REGION", inside)
    assert Settings().region == inside
