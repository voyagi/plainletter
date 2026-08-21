"""The four places a model is allowed to speak, behind one interface.

Everything else in this package is deterministic. Keeping the model calls behind a protocol is what
lets the pipeline be exercised end to end without a cloud account: the tests and the offline demo
supply a scripted reader, the deployed product supplies the Bedrock one, and the code between them
is identical in both cases.

The order matters as much as the interface. `read` runs before the verifier and may return
anything. `explain`, `plan` and `draft` run after it and are wrapped by the grounding guard, so a
date they invent is refused rather than printed.
"""

from __future__ import annotations

from typing import Any, Protocol

from .kb import Sender
from .schemas import ActionStep, DeadlineView, DraftLetter, Explanation, LetterFacts

READING_PROMPT = """You read official Dutch letters at a library help desk.

Return only what the letter actually shows. For every value you return, copy the exact passage it
came from into its source field, character for character, including the words around it that make
it readable. Never paraphrase a passage and never reconstruct one from memory of the layout.

If a value is missing, unreadable, cut off or obscured in the photograph, leave the field empty and
add an entry to `unreadable` saying which field it is, why, and what the volunteer should ask the
visitor. An empty field is a correct answer. A plausible guess is not.

Dates go in as separate day, month and year numbers. Amounts go in as whole cents, so 174,00 euro
is 17400. Set sender_id to one of: {sender_ids}, or leave it empty when the sender is none of them.
"""

EXPLAIN_PROMPT = """You explain an official Dutch letter to someone who is frightened by it.

Write at B1 level: short sentences, everyday words, active voice, no legal vocabulary unless you
immediately say what it means. Answer exactly three things: what this letter is, by when something
must happen, and what happens if the person does nothing.

You may only use dates and amounts from the grounded facts you are given. If a fact is not there,
say the letter does not give it. Never soften a consequence and never add reassurance the letter
does not support.
"""

PLAN_PROMPT = """You turn a read letter into the steps a person takes next.

Each step is one action, in the order it should happen, with the official route for it: the phone
number, website or postal address from the knowledge base entry. Write each step twice, once in
Dutch for the volunteer and once in the visitor's language.

Use only dates and amounts from the grounded facts. Never invent a phone number, a website or an
address; if the knowledge base does not have one, say where to look instead. Say plainly when a
step needs a person rather than a form.
"""

DRAFT_PROMPT = """You draft the letter the visitor sends back.

Write it in Dutch, then the same letter in the visitor's language so they know what they are
signing. Keep it short, factual and polite. State the reference number, the decision being
objected to and the reason in the visitor's own words. Never assert a fact about the visitor that
you were not given, and never quote a date or amount that is not in the grounded facts.
"""


class ReadingModel(Protocol):
    """What the pipeline needs a model to do, and nothing more."""

    def read(self, letter: Any) -> LetterFacts:
        """Extract the sourced facts from a letter, image or text."""
        ...

    def explain(
        self, facts: LetterFacts, grounded: dict[str, str], languages: tuple[str, ...]
    ) -> tuple[Explanation, ...]:
        """Answer the three questions in each language asked for."""
        ...

    def plan(
        self,
        facts: LetterFacts,
        grounded: dict[str, str],
        sender: Sender | None,
        deadline: DeadlineView | None,
        visitor_language: str,
    ) -> tuple[ActionStep, ...]:
        """Lay out the next steps with their official routes."""
        ...

    def draft(
        self,
        facts: LetterFacts,
        grounded: dict[str, str],
        sender: Sender | None,
        visitor_language: str,
    ) -> DraftLetter | None:
        """Write the reply or objection, or return None when one is not the right move."""
        ...
