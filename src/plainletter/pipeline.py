"""The order the stages run in, and the gate between them.

This is deliberately a plain function rather than something a model can re-plan at runtime. The
whole trust claim is that verification happens before anything is explained, planned, drafted or
printed, and a sequence written in Python is a guarantee where a sequence a model chooses is a
preference.

What the facts are checked against comes from the file wherever the file can give it: a text upload
or a born-digital PDF carries the letter's own words. Only pages that arrive as pictures are
transcribed, and then by a separate turn from the one that extracts the facts.

Two independent things enforce grounding, and they sit on different sides of the model. The guard
sits inside the agent: every structured answer is a tool call, and one carrying an ungrounded number
is refused there and sent back for rewriting. This function sits outside it: it re-reads everything
that came through and refuses the whole reading if a stray date or amount survived anyway. A
refused reading at a help desk is recoverable. A confident wrong deadline is not.
"""

from __future__ import annotations

from collections.abc import Generator, Iterable
from dataclasses import dataclass
from datetime import date

from . import urgency
from .intake import LetterInput
from .kb import Sender, get_sender, known_sender_ids
from .marks import mark_letter
from .reading_model import ReadingModel
from .schemas import (
    ActionStep,
    DeadlineView,
    DeskReading,
    DraftLetter,
    Explanation,
    Handoff,
    LetterFacts,
    ReadingProgress,
    VerificationResult,
)
from .verify import ungrounded_claims, verify

DUTCH = "nl"

NOT_GROUNDED_REFERRAL = (
    "Het Juridisch Loket, 0800 8020. Deze brief kon niet volledig gecontroleerd worden."
)
UNKNOWN_SENDER_REFERRAL = (
    "Het Juridisch Loket, 0800 8020. De afzender van deze brief staat niet in de kennisbank."
)


class UngroundedOutputError(RuntimeError):
    """Raised when a date or amount reached the output without passing the verifier."""

    def __init__(self, claims: frozenset[str]) -> None:
        self.claims = claims
        super().__init__(f"ungrounded values in the output: {', '.join(sorted(claims))}")


@dataclass(frozen=True)
class Pipeline:
    model: ReadingModel

    def run(
        self,
        letter: LetterInput,
        *,
        visitor_language: str,
        today: date,
    ) -> DeskReading:
        """The whole reading, waited for. The stages below are the only implementation of it."""
        stages = self.stages(letter, visitor_language=visitor_language, today=today)
        try:
            while True:
                next(stages)
        except StopIteration as finished:
            reading: DeskReading = finished.value
            return reading

    def stages(
        self,
        letter: LetterInput,
        *,
        visitor_language: str,
        today: date,
    ) -> Generator[ReadingProgress, None, DeskReading]:
        """Announce each stage the moment it finishes, and return the finished reading.

        The desk waits with a person in front of it, so the letter appearing marked up after two
        seconds beats a blank screen for eight. Nothing is announced early: a stage is sent when it
        has really happened, and the drafting stage is skipped outright when the check failed.
        """
        letter_text = letter.text if letter.text is not None else self.model.transcribe(letter)
        facts = self.model.read(letter)
        yield ReadingProgress(stage="facts", facts=facts)

        result = verify(facts, letter_text)
        marked = mark_letter(letter_text, facts, result)
        deadline = urgency.view(_grounded_deadline(facts, result), today)
        grounded = usable_values(facts, result, deadline)
        allowed = frozenset(grounded.values())

        sender = get_sender(facts.sender_id)
        sender_name = _sender_name(facts, sender)
        letter_type = facts.letter_type.value if facts.letter_type else "Onbekende brief"
        yield ReadingProgress(
            stage="letter",
            verification=result,
            letter=marked,
            sender_name=sender_name,
            letter_type=letter_type,
            visitor_language=visitor_language,
            handoff=handoff_for(result, sender),
            sources=sender.sources() if sender else (),
        )

        yield ReadingProgress(stage="deadline", deadline=deadline)

        languages = (DUTCH, visitor_language) if visitor_language != DUTCH else (DUTCH,)
        explanations = self.model.explain(facts, grounded, languages)
        _refuse_stray(_explanation_text(explanations), allowed)
        yield ReadingProgress(stage="explanations", explanations=explanations)

        steps = self.model.plan(facts, grounded, sender, deadline, visitor_language)
        _refuse_stray(_step_text(steps), allowed)
        yield ReadingProgress(stage="steps", steps=steps)

        # Whether a letter needs writing back to is the drafter's call, not a property of the
        # letter carrying an objection paragraph: an insurer's arrears notice has no appeal route
        # printed on it and a request for a payment plan is exactly the right reply. What is not
        # the drafter's call is writing one for a reading that did not check out.
        draft = (
            self.model.draft(facts, grounded, sender, visitor_language)
            if result.is_grounded
            else None
        )
        _refuse_stray(_draft_text(draft), allowed)
        yield ReadingProgress(stage="draft", draft=draft)

        return DeskReading(
            facts=facts,
            verification=result,
            letter=marked,
            deadline=deadline,
            sender_name=sender_name,
            letter_type=letter_type,
            visitor_language=visitor_language,
            explanations=explanations,
            steps=steps,
            draft=draft,
            handoff=handoff_for(result, sender),
            sources=sender.sources() if sender else (),
        )


def handoff_for(result: VerificationResult, sender: Sender | None) -> Handoff:
    """When this letter stops being something a volunteer can finish alone.

    Three cases, and none of them is a judgement call the model gets to make: the reading did not
    fully check out, the sender is not in the knowledge base at all, or the sender is one whose
    procedure has not been verified against an official source. In every case the desk says so and
    names where to go.
    """
    if not result.is_grounded:
        return Handoff(
            required=True,
            referral=NOT_GROUNDED_REFERRAL,
            reason="not every fact in the letter could be checked against the page itself",
        )
    if sender is None:
        return Handoff(
            required=True,
            referral=UNKNOWN_SENDER_REFERRAL,
            reason=f"the sender is not one of {', '.join(known_sender_ids())}",
        )
    if not sender.verified:
        referral = sender.referrals[0] if sender.referrals else None
        return Handoff(
            required=True,
            referral=(
                f"{referral.name}, {referral.phone}"
                if referral and referral.phone
                else "Het Juridisch Loket, 0800 8020"
            ),
            reason=sender.handoff_reason_en
            or "this sender's procedure has not been checked against an official source",
        )
    return Handoff(
        required=False,
        referral=sender.referrals[0].name if sender.referrals else "Het Juridisch Loket",
        reason="the letter was read, checked and matched to a verified sender",
    )


POST_BY = "post_by (the last day a posted reply still arrives in time, from the calendar)"


def usable_values(
    facts: LetterFacts, result: VerificationResult, deadline: DeadlineView | None
) -> dict[str, str]:
    """The values the writing stages may use, keyed so the model knows what each one is.

    The key carries the letter's own label for an amount or a labelled date. A bare
    `line_amount_2: EUR 32,00` invites the model to guess what the money is for, and on the first
    live tax letter it guessed a health insurance contribution for what the page called interest.

    The posting date is the one value here that does not stand in the letter. The calendar logic
    derives it from the grounded deadline, the desk card prints it, and a planner handed it must
    be allowed to repeat it. Everything else is exactly what the verifier grounded.
    """
    labels = {
        f"line_amount_{index}": money.label for index, money in enumerate(facts.line_amounts, 1)
    }
    labels.update(
        {f"other_date_{index}": dated.label for index, dated in enumerate(facts.other_dates, 1)}
    )
    if facts.total_amount is not None:
        labels["total_amount"] = facts.total_amount.label

    values: dict[str, str] = {}
    for fact in result.grounded:
        label = labels.get(fact.name)
        values[f"{fact.name} ({label})" if label else fact.name] = fact.display
    if deadline is not None and deadline.post_by_written is not None:
        values[POST_BY] = deadline.post_by_written
    return values


def _grounded_deadline(facts: LetterFacts, result: VerificationResult) -> date | None:
    """The deadline only counts once it survived the check, so an unverified one never counts."""
    if facts.deadline is None:
        return None
    if not any(fact.name == "deadline" for fact in result.grounded):
        return None
    return facts.deadline.to_date()


def _sender_name(facts: LetterFacts, sender: Sender | None) -> str:
    if sender is not None:
        return sender.name_nl
    return facts.sender_name.value if facts.sender_name else "Onbekende afzender"


def _refuse_stray(parts: Iterable[str], allowed: frozenset[str]) -> None:
    """Stop the reading the moment a stage writes a date or amount the check never allowed.

    Checking each stage as it finishes rather than all of them at the end is what makes streaming
    safe: an explanation is on the volunteer's screen the instant it is sent, so it has to have
    been checked before it is sent, not after the draft comes back.
    """
    stray = ungrounded_claims(" ".join(parts), allowed)
    if stray:
        raise UngroundedOutputError(stray)


def _explanation_text(explanations: tuple[Explanation, ...]) -> list[str]:
    return [
        part
        for item in explanations
        for part in (item.what_is_this, item.by_when, item.if_you_do_nothing)
    ]


def _step_text(steps: tuple[ActionStep, ...]) -> list[str]:
    return [
        part for step in steps for part in (step.dutch, step.visitor, step.official_route or "")
    ]


def _draft_text(draft: DraftLetter | None) -> list[str]:
    return [draft.dutch, draft.visitor] if draft is not None else []
