"""The offline demo, and the fixture the tests run the whole pipeline against.

A scripted reading model stands in for Bedrock. It returns exactly what a good reading of the
sample letter would return, so the deterministic half of the product, which is the half that
carries the trust claim, can be exercised end to end with no cloud account and no network. The
sample letters are invented: the names, addresses, reference numbers and number plates in them
belong to nobody.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .kb import Sender
from .schemas import (
    ActionStep,
    DeadlineView,
    DraftLetter,
    Explanation,
    LetterDate,
    LetterFacts,
    Money,
    NamedValue,
    SourceSpan,
    Unreadable,
)

SAMPLES_DIR = Path(__file__).parent / "samples"


def sample_text(name: str) -> str:
    return (SAMPLES_DIR / f"{name}.txt").read_text(encoding="utf-8")


def sample_names() -> tuple[str, ...]:
    return tuple(sorted(path.stem for path in SAMPLES_DIR.glob("*.txt")))


@dataclass(frozen=True)
class ScriptedReadingModel:
    """A reading model whose answers are fixed in advance."""

    facts: LetterFacts
    explanations: tuple[Explanation, ...]
    steps: tuple[ActionStep, ...]
    draft_letter: DraftLetter | None

    def read(self, letter: object) -> LetterFacts:
        return self.facts

    def explain(
        self, facts: LetterFacts, grounded: dict[str, str], languages: tuple[str, ...]
    ) -> tuple[Explanation, ...]:
        return tuple(item for item in self.explanations if item.language in languages)

    def plan(
        self,
        facts: LetterFacts,
        grounded: dict[str, str],
        sender: Sender | None,
        deadline: DeadlineView | None,
        visitor_language: str,
    ) -> tuple[ActionStep, ...]:
        return self.steps

    def draft(
        self,
        facts: LetterFacts,
        grounded: dict[str, str],
        sender: Sender | None,
        visitor_language: str,
    ) -> DraftLetter | None:
        return self.draft_letter


def cjib_facts() -> LetterFacts:
    """What a correct reading of the sample traffic fine returns, sourced passage by passage."""
    return LetterFacts(
        sender_id="cjib",
        sender_name=NamedValue(
            value="Centraal Justitieel Incassobureau",
            source=SourceSpan(page=1, text="Centraal Justitieel Incassobureau"),
        ),
        letter_type=NamedValue(
            value="Beschikking administratieve sanctie (Wet Mulder)",
            source=SourceSpan(page=1, text="Beschikking administratieve sanctie (Wet Mulder)"),
        ),
        reference=NamedValue(
            value="8194 5523 7761",
            source=SourceSpan(page=1, text="Beschikkingsnummer: 8194 5523 7761"),
        ),
        issued_on=LetterDate(
            day=4,
            month=8,
            year=2026,
            source=SourceSpan(page=1, text="Datum beschikking: 4 augustus 2026"),
        ),
        deadline=LetterDate(
            day=15,
            month=9,
            year=2026,
            source=SourceSpan(page=1, text="Betaal voor 15 september 2026."),
        ),
        total_amount=Money(
            cents=17400,
            label="Totaal te betalen",
            source=SourceSpan(page=1, text="Totaal te betalen: EUR 174,00"),
        ),
        line_amounts=(
            Money(
                cents=16500,
                label="Sanctiebedrag",
                source=SourceSpan(page=1, text="Sanctiebedrag: EUR 165,00"),
            ),
            Money(
                cents=900,
                label="Administratiekosten",
                source=SourceSpan(page=1, text="Administratiekosten: EUR 9,00"),
            ),
        ),
        consequences=(
            SourceSpan(
                page=1,
                text=(
                    "Betaalt u niet op tijd, dan wordt het bedrag verhoogd met 50 procent. "
                    "Bij een tweede verhoging komt daar nog eens 100 procent bij."
                ),
            ),
        ),
        objection_route=SourceSpan(
            page=1,
            text=(
                "U kunt binnen zes weken na de datum van deze beschikking beroep instellen bij de "
                "officier van justitie."
            ),
        ),
        unreadable=(
            Unreadable(
                field="kenteken",
                reason="the middle character of the number plate is blurred in the photograph",
                ask_the_visitor="Ask the visitor to read the number plate from the letter.",
            ),
        ),
    )


def cjib_model() -> ScriptedReadingModel:
    """The scripted reading of the sample traffic fine, in Dutch and Arabic."""
    return ScriptedReadingModel(
        facts=cjib_facts(),
        explanations=(
            Explanation(
                language="nl",
                what_is_this=(
                    "Een verkeersboete van het CJIB. U reed 14 km/u te hard op de Boezemweg in "
                    "Rotterdam. U moet EUR 174,00 betalen."
                ),
                by_when="Betaal voor 15 september 2026.",
                if_you_do_nothing=(
                    "Het bedrag wordt verhoogd met 50 procent. Betaalt u daarna nog niet, dan komt "
                    "er nog 100 procent bij."
                ),
            ),
            Explanation(
                language="ar",
                what_is_this=(
                    "غرامة مرور من CJIB. تجاوزت السرعة في شارع Boezemweg في روتردام. "
                    "عليك دفع EUR 174,00."
                ),
                by_when="ادفع قبل 15 september 2026.",
                if_you_do_nothing=(
                    "يزيد المبلغ 50 بالمئة. وإذا لم تدفع بعد ذلك يزيد 100 بالمئة أخرى."
                ),
            ),
        ),
        steps=(
            ActionStep(
                order=1,
                dutch="Betaal EUR 174,00 met beschikkingsnummer 8194 5523 7761.",
                visitor="ادفع EUR 174,00 بالرقم 8194 5523 7761.",
                official_route="https://www.cjib.nl/verkeersboete",
            ),
            ActionStep(
                order=2,
                dutch="Kunt u het niet in een keer betalen? Vraag een betalingsregeling aan.",
                visitor="لا تستطيع الدفع دفعة واحدة؟ اطلب خطة تقسيط.",
                official_route="https://www.cjib.nl/betalingsregeling",
            ),
            ActionStep(
                order=3,
                dutch=(
                    "Bent u het er niet mee eens? Stel beroep in bij de officier van justitie, "
                    "binnen zes weken na de datum van de beschikking."
                ),
                visitor=(
                    "غير موافق؟ قدّم اعتراضاً إلى المدعي العام خلال ستة أسابيع من تاريخ القرار."
                ),
                official_route="https://www.om.nl/onderwerpen/verkeer",
            ),
        ),
        draft_letter=DraftLetter(
            kind="objection",
            addressed_to="Officier van justitie",
            send_before=None,
            dutch=(
                "Geachte officier van justitie,\n\n"
                "Ik maak bezwaar tegen beschikking 8194 5523 7761. Mijn auto stond die dag niet op "
                "de Boezemweg. Ik verzoek u de sanctie in te trekken.\n\nMet vriendelijke groet,"
            ),
            visitor=(
                "حضرة المدعي العام،\n\n"
                "أعترض على القرار رقم 8194 5523 7761. لم تكن سيارتي في شارع Boezemweg في ذلك "
                "اليوم. أرجو إلغاء الغرامة.\n\nمع خالص التقدير،"
            ),
        ),
    )
