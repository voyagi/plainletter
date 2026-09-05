"""The few things that differ between the laptop, the local server and the deployed runtime.

Read once from the environment, or from a `.env` beside the code for local runs. Credentials are
never here: boto3 finds them on the machine or in the runtime's execution role. The memory store id
accepts the name the AgentCore deployment injects as well as the product's own, so a deployed
runtime needs no extra wiring to find the store it was deployed with.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import AfterValidator, AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .bedrock import DRAFTING_MODEL_ID, READING_MODEL_ID, SOURCE_REGION
from .spend import DEFAULT_READINGS_PER_DAY

# The prefix every AWS region in the European Union carries. Frankfurt, Ireland, London, Paris,
# Stockholm, Milan, Spain and Zurich all begin with it, and no region outside Europe does.
EU_PREFIX = "eu-"


def in_the_eu(region: str) -> str:
    """Refuse a region outside the EU rather than quietly reading letters in one.

    The letters carry personal data and processing them outside the EU is the one trade this
    product does not make, which docs/deploy.md states as a fact about the deployment. It was a
    fact about the deployment only. `AWS_REGION` is set by every AWS execution environment and by
    most developer shells, it is an alias for this field, and it silently beat the Frankfurt
    default: the model was then built for whatever region the shell named. The startup model probe
    caught some of that by accident, because the `eu.` inference profiles do not resolve elsewhere,
    but only when the model ids were not also overridden and only when the account answered at all.

    A promise nothing checks is a promise until the day somebody exports a variable.
    """
    if not region.startswith(EU_PREFIX):
        raise ValueError(
            f"{region} is not an EU region. This product reads letters carrying personal data and "
            f"processes them in the EU only, so it will not start pointed at {region}. Set "
            f"PLAINLETTER_REGION to an {EU_PREFIX} region, or unset it to use {SOURCE_REGION}."
        )
    return region


EuRegion = Annotated[str, AfterValidator(in_the_eu)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    region: EuRegion = Field(
        default=SOURCE_REGION,
        validation_alias=AliasChoices("PLAINLETTER_REGION", "AWS_REGION"),
    )
    reading_model: str = Field(
        default=READING_MODEL_ID, validation_alias=AliasChoices("PLAINLETTER_READING_MODEL")
    )
    drafting_model: str = Field(
        default=DRAFTING_MODEL_ID, validation_alias=AliasChoices("PLAINLETTER_DRAFTING_MODEL")
    )
    memory_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PLAINLETTER_MEMORY_ID", "MEMORY_PLAINLETTERMEMORY_ID"),
    )
    # Zero closes the reading service without taking it down, which is a setting an operator who is
    # watching a bill climb actually wants.
    max_readings_per_day: int = Field(
        default=DEFAULT_READINGS_PER_DAY,
        ge=0,
        validation_alias=AliasChoices("PLAINLETTER_MAX_READINGS_PER_DAY"),
    )


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()
