"""The tool the planning and drafting agents call: the sender's official routes.

The routes come out of the knowledge base through a lookup rather than being pasted into the
prompt. That is not a stylistic choice. A tool call is the one thing the model does that the
grounding guard inspects and the audit trail records, so a route a step names was fetched, and the
fetch is on the record. A route the model never fetched is a route it made up, and the planning
prompt says exactly that.

The lookup never raises for an unknown sender. A letter from a body the knowledge base does not
carry is the normal case for a help desk, and the honest answer is "not here, say where to look",
which the tool returns as data rather than as a stack trace.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from strands import tool

from .kb import ObjectionRoute, PaymentRoute, Referral, get_sender
from .locales import active


class OfficialRoutes(BaseModel):
    """What the knowledge base knows about where a letter from this sender goes next."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sender_id: str
    known: bool = Field(description="false when the knowledge base has no entry for this sender")
    verified: bool = Field(
        default=False,
        description="true only when every route below was read on an official page",
    )
    name_nl: str | None = None
    objection: ObjectionRoute | None = None
    payment: PaymentRoute | None = None
    referrals: tuple[Referral, ...] = ()
    handoff_reason_en: str | None = None
    note: str = Field(description="what to do with these routes, in one sentence")


UNKNOWN_SENDER_NOTE = (
    "This sender is not in the knowledge base. Do not invent a route: tell the visitor to check "
    "the letter itself for the address, website or phone number, and refer them to {referral} if "
    "the letter gives none."
)
UNVERIFIED_SENDER_NOTE = (
    "The routes for this sender have not been checked against an official page. Use them only to "
    "say where a person can confirm them, and say that a person must confirm them."
)
VERIFIED_SENDER_NOTE = (
    "Every route here was read on an official page on the date given. Use these and no others."
)


@tool
def official_routes(sender_id: str) -> OfficialRoutes:
    """Look up the official routes for the body that sent the letter.

    Returns where an objection goes and within how many days, how to pay or ask for a payment
    plan, and who to refer the visitor to when a person should take over, each with the official
    page it was read on. Call this before writing any step or letter that names a route.

    Args:
        sender_id: the sender's id as read from the letter, for example cjib or belastingdienst
    """
    sender = get_sender(sender_id)
    if sender is None:
        return OfficialRoutes(
            sender_id=sender_id,
            known=False,
            note=UNKNOWN_SENDER_NOTE.format(referral=active().words.referral_last_resort),
        )
    return OfficialRoutes(
        sender_id=sender.id,
        known=True,
        verified=sender.verified,
        name_nl=sender.name_nl,
        objection=sender.objection,
        payment=sender.payment,
        referrals=sender.referrals,
        handoff_reason_en=sender.handoff_reason_en,
        note=VERIFIED_SENDER_NOTE if sender.verified else UNVERIFIED_SENDER_NOTE,
    )
