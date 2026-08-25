"""The few things that differ between the laptop, the local server and the deployed runtime.

Read once from the environment, or from a `.env` beside the code for local runs. Credentials are
never here: boto3 finds them on the machine or in the runtime's execution role. The memory store id
accepts the name the AgentCore deployment injects as well as the product's own, so a deployed
runtime needs no extra wiring to find the store it was deployed with.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .bedrock import DRAFTING_MODEL_ID, READING_MODEL_ID, SOURCE_REGION
from .spend import DEFAULT_READINGS_PER_DAY


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    region: str = Field(
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
