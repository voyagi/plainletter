"""The curated sender knowledge base.

One YAML file per Dutch sender, hand written, every procedural claim carrying the official page it
came from and the date that page was checked. This is where the product's actual value sits: a
translation app can tell a visitor what the words mean, and none of them can tell the volunteer
that an objection to this particular body goes to that particular address within that particular
number of weeks.

The important field is `verified`. A sender whose procedure has not been checked against an
official source says so, and the pipeline routes those letters to a human instead of stating a
deadline it cannot back. An unverified entry is not a gap to fill with a plausible guess.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

SENDERS_DIR = Path(__file__).parent / "senders"


class SourcedFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text_nl: str
    text_en: str
    source: str = Field(description="official URL the claim comes from")
    checked_on: str = Field(description="ISO date the URL was last confirmed to exist")


class ObjectionRoute(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    window_days: int = Field(ge=1)
    counted_from: Literal["issued_on", "deadline"]
    body_nl: str
    postal_address: str | None = None
    online_route: str | None = None
    source: str
    checked_on: str


class PaymentRoute(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    website: str | None = None
    phone: str | None = None
    payment_plan: bool = False
    source: str
    checked_on: str


class Referral(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    phone: str | None = None
    website: str | None = None
    when_nl: str
    when_en: str


class Sender(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name_nl: str
    short_name: str
    verified: bool = Field(
        description="true only when every procedural claim below was read on an official page"
    )
    checked_on: str
    what_they_do_en: str
    letter_types: tuple[str, ...] = ()
    consequences: tuple[SourcedFact, ...] = ()
    objection: ObjectionRoute | None = None
    payment: PaymentRoute | None = None
    referrals: tuple[Referral, ...] = ()
    handoff_reason_en: str | None = Field(
        default=None,
        description="why this sender always needs a person, when it does",
    )

    def route_values(self) -> frozenset[str]:
        """Every way of reaching somebody that the official-route lookup can hand out for this
        sender, and therefore the only ones a step may name.

        The `source` URLs count: the lookup returns them, and the page a claim was read on is a
        real place a visitor can go. A number printed on the letter does not count, however
        official it looks, because a letter is the one thing in this pipeline an attacker writes.
        """
        values: list[str | None] = []
        if self.objection:
            values += [
                self.objection.postal_address,
                self.objection.online_route,
                self.objection.source,
            ]
        if self.payment:
            values += [self.payment.website, self.payment.phone, self.payment.source]
        for referral in self.referrals:
            values += [referral.phone, referral.website]
        return frozenset(value for value in values if value)

    def sources(self) -> tuple[str, ...]:
        urls = [fact.source for fact in self.consequences]
        if self.objection:
            urls.append(self.objection.source)
        if self.payment:
            urls.append(self.payment.source)
        return tuple(dict.fromkeys(urls))


@functools.lru_cache(maxsize=1)
def load_senders() -> dict[str, Sender]:
    """Every sender file, keyed by id. Cached: the files never change while the process runs."""
    senders: dict[str, Sender] = {}
    for path in sorted(SENDERS_DIR.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        sender = Sender.model_validate(raw)
        if sender.id in senders:
            raise ValueError(f"two sender files claim the id {sender.id!r}")
        senders[sender.id] = sender
    return senders


def get_sender(sender_id: str | None) -> Sender | None:
    if sender_id is None:
        return None
    return load_senders().get(sender_id)


def known_sender_ids() -> tuple[str, ...]:
    return tuple(load_senders())
