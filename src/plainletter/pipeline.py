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

The same reasoning covers routes, and it is why a step's phone number or address is checked against
the knowledge base here rather than trusted because the prompt asked for it. The letter is the one
input to this pipeline that somebody else wrote, so a number printed on it is a claim, not a route.
"""

from __future__ import annotations

import re
from collections.abc import Generator, Iterable
from dataclasses import dataclass
from datetime import date

from . import urgency
from .intake import LetterInput
from .kb import Sender, get_sender, known_sender_ids
from .locales import active
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


class RefusedReadingError(RuntimeError):
    """A reading a deterministic layer stopped. This is the product working, not the product
    failing, so it is answered as a verdict rather than raised at a visitor as an error."""

    def __init__(self, claims: frozenset[str], message: str) -> None:
        self.claims = claims
        self.message = message
        super().__init__(f"{message} ({', '.join(sorted(claims))})")


class UngroundedOutputError(RefusedReadingError):
    """Raised when a date or amount reached the output without passing the verifier."""

    def __init__(self, claims: frozenset[str]) -> None:
        super().__init__(
            claims,
            "The reading was refused because a date or amount in it does not stand in the letter.",
        )


class UnofficialRouteError(RefusedReadingError):
    """Raised when a step named a way to reach the sender that the lookup never handed out.

    The letter is the one input an attacker writes, so a phone number printed on it is not a route
    however official the page looks. A wrong deadline costs a visitor a fine; a wrong phone number
    on a printed card costs them whatever the person answering it asks for.
    """

    def __init__(self, routes: frozenset[str]) -> None:
        super().__init__(
            routes,
            "The reading was refused because a step named a way to reach the sender that the "
            "knowledge base never gave out.",
        )


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

        words = active().words
        sender = get_sender(facts.sender_id)
        sender_name = _sender_name(facts, sender)
        letter_type = facts.letter_type.value if facts.letter_type else words.unknown_letter_type
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

        official = words.language
        languages = (official, visitor_language) if visitor_language != official else (official,)
        explanations = self.model.explain(facts, grounded, languages)
        _refuse_stray(_explanation_text(explanations), allowed)
        yield ReadingProgress(stage="explanations", explanations=explanations)

        steps = official_steps(
            self.model.plan(facts, grounded, sender, deadline, visitor_language), sender
        )
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
    words = active().words
    if not result.is_grounded:
        return Handoff(
            required=True,
            referral=words.referral_not_grounded,
            reason="not every fact in the letter could be checked against the page itself",
        )
    if sender is None:
        return Handoff(
            required=True,
            referral=words.referral_unknown_sender,
            reason=f"the sender is not one of {', '.join(known_sender_ids())}",
        )
    if not sender.verified:
        referral = sender.referrals[0] if sender.referrals else None
        return Handoff(
            required=True,
            referral=(
                f"{referral.name}, {referral.phone}"
                if referral and referral.phone
                else words.referral_last_resort
            ),
            reason=sender.handoff_reason_en
            or "this sender's procedure has not been checked against an official source",
        )
    return Handoff(
        required=False,
        referral=sender.referrals[0].name if sender.referrals else words.referral_last_resort_name,
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
    if facts.sender_name:
        return facts.sender_name.value
    return active().words.unknown_sender_name


def _refuse_stray(parts: Iterable[str], allowed: frozenset[str]) -> None:
    """Stop the reading the moment a stage writes a date or amount the check never allowed.

    Checking each stage as it finishes rather than all of them at the end is what makes streaming
    safe: an explanation is on the volunteer's screen the instant it is sent, so it has to have
    been checked before it is sent, not after the draft comes back.
    """
    stray = ungrounded_claims(" ".join(parts), allowed)
    if stray:
        raise UngroundedOutputError(stray)


# Anything left in a route after the permitted values are taken out that could itself be a way to
# reach somebody: a digit, an address, a scheme, or a bare host name. Labels and punctuation are
# not.
#
# The last alternative is the one that is easy to leave out and it is why this is a pattern rather
# than a list of three obvious things: `spoedbetaling-belastingdienst.nl` carries no digit, no `@`,
# no `://` and no `www.`, and it is a perfectly good way to send somebody to the wrong place. Two
# letters after the dot is enough to catch every host and short enough not to catch `z.o.z.`.
#
# The host label is `\w`, not `a-z`, so an internationalised name counts. A pattern spelled in ASCII
# would have let a route through on the strength of the alphabet it was written in, which is not a
# security property anybody would defend out loud.
_REACHABLE = re.compile(r"\d|@|://|\b[^\W_][\w-]*\.[^\W\d_]{2,}", re.UNICODE)


def route_is_official(route: str, permitted: frozenset[str]) -> bool:
    """Whether every way of reaching somebody inside this route came from the lookup.

    An exact match is the ordinary case. The rest of this exists because of what the first deployed
    run did: asked for one route, the model wrote the referral's phone and website into the single
    field, as `0800 8020 | https://www.juridischloket.nl/` and in ten other arrangements. Both
    halves were values the lookup had just returned, an exact comparison matched neither, and twenty
    of twenty-two letters were refused over formatting. That is a worse failure than the one this
    check prevents: a desk that refuses nine letters in ten helps nobody.

    So the values are taken out and what remains is judged. If nothing that could reach a person is
    left, every route in the string came from the lookup and the arrangement is just prose. A number
    printed on the letter survives that removal and is still refused, which is the property worth
    keeping: the letter is the one input somebody else wrote.
    """
    if route in permitted:
        return True
    remainder = route
    # Longest first, so a value that contains another is removed whole rather than in pieces.
    for value in sorted(permitted, key=len, reverse=True):
        remainder = remainder.replace(value, " ")
    return not _REACHABLE.search(remainder)


def single_route(route: str, permitted: frozenset[str]) -> str | None:
    """The one lookup value this route should carry, out of however many it was written with.

    Accepting a combined route is not the same as printing one. The console renders this field as
    the target of a link and the desk card prints it as the one place to go, so
    `0800 8020 | https://www.juridischloket.nl/` arriving intact is a dead link on a screen in front
    of a frightened person: better than refusing the letter, and still wrong.

    The first permitted value in the string wins, which keeps the order the planner chose rather
    than imposing one, and it is always exactly a value the lookup returned. A route that is already
    one value is returned untouched, and one that carries none is left alone for the check above to
    refuse.
    """
    if route in permitted:
        return route
    found = [(route.find(value), value) for value in permitted if value in route]
    if not found:
        return None
    # Earliest wins, and the longest of the ones that tie. Two permitted routes can share a prefix,
    # `https://example.test/` and `https://example.test/pay`, and both then match at the same
    # position: ordering on the string instead would quietly hand back the shorter one and send the
    # visitor to a different official page than the step meant.
    return min(found, key=lambda match: (match[0], -len(match[1])))[1]


def official_steps(steps: tuple[ActionStep, ...], sender: Sender | None) -> tuple[ActionStep, ...]:
    """Refuse a step naming a route the knowledge base never handed out, and reduce the rest to one.

    The planning prompt says every route has to come from the lookup, and a prompt is a preference.
    This is the check. A sender the knowledge base does not carry has no routes at all, so a route
    on one of those letters is by definition invented, and those letters already go to a person.

    The reduction is here rather than at the two places that display a route, because a step leaving
    this function with two of them in one field is a bug wherever it is eventually printed.
    """
    permitted = sender.route_values() if sender is not None else frozenset()
    invented = frozenset(
        step.official_route
        for step in steps
        if step.official_route and not route_is_official(step.official_route, permitted)
    )
    if invented:
        raise UnofficialRouteError(invented)

    def reduced(step: ActionStep) -> ActionStep:
        if not step.official_route or step.official_route in permitted:
            return step
        one = single_route(step.official_route, permitted)
        return step.model_copy(update={"official_route": one})

    return tuple(reduced(step) for step in steps)


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
