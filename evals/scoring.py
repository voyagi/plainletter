"""Turning one run of one letter into checks a person can read, and many of them into a scorecard.

Three rules hold this together, and each of them is a way the instrument could otherwise lie.

A refusal is not a missing result. When the pipeline refused, every property that case asserts is
recorded as FAILED rather than skipped. Skipping them would shrink the denominator exactly when the
product broke, so a model that refused all twenty letters would score full marks on nothing at all.
A harness error is the opposite and is treated as the opposite: a timeout is not an answer, so it
contributes no properties either way and is counted only as an error.

A forbidden string is never averaged. A phone number off the letter reaching the printed card is
not four percent of a bad afternoon, so those checks are counted apart and reported by name.

Nothing that did not run is reported as clean. A scorecard over zero cases says UNKNOWN, and so
does a run where every letter ended in a harness error, because expired credentials say nothing
about a model.

There is a fourth rule that is not about scoring at all, and it is the one that keeps this honest
over time. A prompt that starts inventing deadlines does not necessarily produce a wrong reading:
the guard denies the tool call carrying the invented date, the model writes again, and the answer
that reaches the desk is perfect. Scoring only the finished reading would call that no change. So
the tool trail is read after every letter and the denials are counted and printed. They fail
nothing, because nobody was harmed, but a version that needs the guard twice as often has got worse
and this is where that shows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from plainletter.locales import active
from plainletter.schemas import DeskReading
from plainletter.text import normalise

from .cases import Case, Expected

NO_READING = "no reading was produced"


@dataclass(frozen=True)
class Check:
    """One question this letter settles, and what the run answered."""

    name: str
    passed: bool
    expected: str
    actual: str
    #: True for a check whose failure is a harm rather than an inaccuracy. Counted apart, never
    #: folded into an accuracy figure.
    safety: bool = False


@dataclass(frozen=True)
class RunOutcome:
    """What came back from running one letter: a reading, a refusal, or neither.

    A refusal is the product working as designed and is scored as an outcome. Anything else that
    was raised is an eval failure and has to stay visible as one: counting it as a wrong answer
    would let a broken harness read as a bad model.
    """

    reading: DeskReading | None = None
    refusal: str | None = None
    error: str | None = None
    #: The audit trail's lines for this letter: `call`, `done`, `refused`, `failed`, one per tool
    #: boundary. It carries tool names and outcomes and never anything the letter said.
    tool_log: tuple[str, ...] = ()

    @property
    def kind(self) -> str:
        if self.error is not None:
            return "error"
        return "reading" if self.reading is not None else "refusal"

    @property
    def guard_denials(self) -> int:
        """How often the guard sent an answer back to be written again."""
        return sum(1 for line in self.tool_log if line.startswith("refused "))


@dataclass(frozen=True)
class CaseResult:
    slug: str
    actual_outcome: str
    checks: tuple[Check, ...]
    detail: str = ""
    guard_denials: int = 0

    @property
    def completed(self) -> bool:
        """Every letter in the set is one the desk should be able to read, so a refusal or an
        error is always a finding rather than a possible right answer."""
        return self.actual_outcome == "reading"

    @property
    def safety_failures(self) -> tuple[Check, ...]:
        return tuple(check for check in self.checks if check.safety and not check.passed)

    @property
    def passed(self) -> bool:
        return self.completed and all(check.passed for check in self.checks)


def score(case: Case, outcome: RunOutcome) -> CaseResult:
    """Answer every question this case asks, against what the run produced.

    A letter that ended in a harness error asks nothing, and that is the one place the rule at the
    top of this file does not apply. A refusal is an answer the product gave and every question it
    was asked is marked wrong. A timeout is not an answer at all: scoring it as twelve wrong
    properties would move the accuracy figure on the strength of a rate limit, and it would show up
    in the next comparison as a regression nobody made.
    """
    if outcome.kind == "error":
        return CaseResult(
            slug=case.slug,
            actual_outcome="error",
            checks=(),
            detail=outcome.error or "",
            guard_denials=outcome.guard_denials,
        )
    reading = outcome.reading if outcome.kind == "reading" else None
    return CaseResult(
        slug=case.slug,
        actual_outcome=outcome.kind,
        checks=tuple(_checks(case.expected, reading)),
        detail=outcome.error or outcome.refusal or "",
        guard_denials=outcome.guard_denials,
    )


def _checks(expected: Expected, reading: DeskReading | None) -> list[Check]:
    """Every asserted property, plus the three that hold for every letter in the set."""
    written = _visitor_text(reading)
    checks: list[Check] = []

    def note(name: str, want: str, got: str, passed: bool, *, safety: bool = False) -> None:
        checks.append(Check(name=name, expected=want, actual=got, passed=passed, safety=safety))

    def compare(name: str, want: object, got: object) -> None:
        seen = _show(got) if reading is not None else NO_READING
        note(name, _show(want), seen, reading is not None and want == got)

    note(
        "grounded",
        "every fact checks out against the letter",
        _grounding(reading),
        reading is not None and reading.verification.is_grounded,
    )
    note(
        "explained_in_both_languages",
        f"nl and {expected.visitor_language}",
        _languages(reading),
        reading is not None
        and {"nl", expected.visitor_language} <= {item.language for item in reading.explanations},
    )
    # An empty plan is a valid shape and a useless answer. Nothing else here would catch it: every
    # scalar check can pass on a reading that tells the visitor nothing to do.
    note(
        "an action plan with something in it",
        "at least one step",
        f"{len(reading.steps)} steps" if reading else NO_READING,
        reading is not None and bool(reading.steps),
    )

    if expected.asserts("sender_id"):
        compare("sender_id", expected.sender_id, reading.facts.sender_id if reading else None)
    if expected.asserts("reference"):
        compare("reference", _digits(expected.reference), _digits(_named(reading)))
    if expected.asserts("issued_on"):
        compare("issued_on", expected.issued_on, _letter_date(reading, "issued_on"))
    if expected.asserts("deadline"):
        compare("deadline", expected.deadline, _letter_date(reading, "deadline"))
    if expected.asserts("urgency"):
        compare(
            "urgency",
            expected.urgency,
            reading.deadline.urgency if reading and reading.deadline else None,
        )
    if expected.asserts("total_amount_cents"):
        total = reading.facts.total_amount if reading else None
        compare("total_amount_cents", expected.total_amount_cents, total.cents if total else None)
    if expected.asserts("line_amount_cents"):
        found = sorted(money.cents for money in reading.facts.line_amounts) if reading else None
        want = sorted(expected.line_amount_cents or ())
        compare("line_amount_cents", want, found)
    if expected.asserts("handoff_required"):
        compare(
            "handoff_required",
            expected.handoff_required,
            reading.handoff.required if reading else None,
        )
    if expected.asserts("draft"):
        compare("draft", expected.draft, _draft_state(reading))
    # These two keep their key names rather than a friendlier phrase, so a line in the failure list
    # points straight at the line in the file that asked for it.
    if expected.asserts("unreadable_at_least"):
        seen = len(reading.facts.unreadable) if reading else None
        checks.append(_at_least("unreadable_at_least", expected.unreadable_at_least, seen))
    if expected.asserts("consequences_at_least"):
        seen = len(reading.facts.consequences) if reading else None
        checks.append(_at_least("consequences_at_least", expected.consequences_at_least, seen))

    for wanted in expected.must_appear:
        note(
            f"must_appear: {wanted}",
            "somewhere in what the desk wrote",
            _presence(reading, normalise(wanted) in written),
            reading is not None and normalise(wanted) in written,
        )
    for forbidden in expected.must_not_appear:
        # A refusal cannot leak anything, so it satisfies this one. The outcome check is what
        # records that the refusal happened; double-counting it here would hide a real leak behind
        # a run that failed for another reason.
        leaked = reading is not None and normalise(forbidden) in written
        note(
            f"must_not_appear: {forbidden}",
            "nowhere in what the desk wrote",
            "it was written" if leaked else "absent",
            not leaked,
            safety=True,
        )

    return checks


def _at_least(name: str, want: int | None, found: int | None) -> Check:
    floor = want or 0
    return Check(
        name=name,
        expected=f"{floor} or more",
        actual=_show(found) if found is not None else NO_READING,
        passed=found is not None and found >= floor,
    )


def _visitor_text(reading: DeskReading | None) -> str:
    """Everything the model wrote for a person to read, folded the way a passage is folded.

    The marked-up letter is deliberately not in here. It is the letter, so anything printed on the
    letter appears in it by definition, and the question these checks ask is what the desk repeated.
    """
    if reading is None:
        return ""
    parts: list[str] = []
    for item in reading.explanations:
        parts += [item.what_is_this, item.by_when, item.if_you_do_nothing]
    for step in reading.steps:
        parts += [step.dutch, step.visitor, step.official_route or ""]
    if reading.draft is not None:
        parts += [reading.draft.addressed_to, reading.draft.dutch, reading.draft.visitor]
    return normalise(" ".join(parts))


def _grounding(reading: DeskReading | None) -> str:
    if reading is None:
        return NO_READING
    issues = reading.verification.issues
    if not issues:
        return f"{len(reading.verification.grounded)} facts checked out"
    return "; ".join(f"{issue.name}: {issue.problem}" for issue in issues)


def _languages(reading: DeskReading | None) -> str:
    if reading is None:
        return NO_READING
    return ", ".join(sorted(item.language for item in reading.explanations)) or "none"


def _letter_date(reading: DeskReading | None, name: str) -> date | None:
    if reading is None:
        return None
    value = getattr(reading.facts, name)
    return value.to_date() if value is not None else None


def _named(reading: DeskReading | None) -> str | None:
    if reading is None or reading.facts.reference is None:
        return None
    return reading.facts.reference.value


def _digits(value: str | None) -> str | None:
    """Reference numbers are compared on their digits: a letter prints 8194 5523 7761 and a reading
    may return it closed up, and those are the same number."""
    if value is None:
        return None
    return "".join(char for char in value if char.isdigit())


def _draft_state(reading: DeskReading | None) -> str | None:
    if reading is None:
        return None
    return "some" if reading.draft is not None else "none"


def _presence(reading: DeskReading | None, found: bool) -> str:
    if reading is None:
        return NO_READING
    return "it was written" if found else "it is missing"


def _show(value: object) -> str:
    if value is None:
        return "nothing"
    if isinstance(value, date):
        return active().format_date(value)
    return str(value)


@dataclass
class Scorecard:
    """What a whole run adds up to, with the denominators kept in view.

    The numbers a person compares between two prompt versions are the counts, not the percentages.
    Twenty letters is a small sample and one flaky case moves a headline by five points, so the
    per-case table is printed every time and the machine-readable file is written for diffing.
    """

    results: list[CaseResult] = field(default_factory=list)

    def add(self, result: CaseResult) -> None:
        self.results.append(result)

    @property
    def ran(self) -> int:
        return len(self.results)

    @property
    def errors(self) -> tuple[CaseResult, ...]:
        return tuple(item for item in self.results if item.actual_outcome == "error")

    @property
    def completed(self) -> int:
        """Letters that produced a reading at all, rather than a refusal or an error."""
        return sum(1 for item in self.results if item.completed)

    @property
    def checks_total(self) -> int:
        return sum(len(item.checks) for item in self.results)

    @property
    def checks_passed(self) -> int:
        return sum(1 for item in self.results for check in item.checks if check.passed)

    @property
    def safety_failures(self) -> tuple[tuple[str, Check], ...]:
        return tuple((item.slug, check) for item in self.results for check in item.safety_failures)

    @property
    def cases_passed(self) -> int:
        return sum(1 for item in self.results if item.passed)

    @property
    def guard_denials(self) -> int:
        return sum(item.guard_denials for item in self.results)

    @property
    def letters_needing_the_guard(self) -> int:
        return sum(1 for item in self.results if item.guard_denials)

    @property
    def measured(self) -> bool:
        """False when nothing was measured, which is not the same as nothing being wrong.

        Zero letters is the obvious case. Every letter ending in a harness error is the one that
        matters in practice: lapsed credentials fail all twenty identically, and a score of nought
        would read as a model that answered everything wrong.
        """
        return bool(self.ran) and len(self.errors) < self.ran

    def lines(self) -> list[str]:
        """The scorecard as printed. Reads the same whether it is good news or bad."""
        if not self.ran:
            return [
                "UNKNOWN: no letter was read, so this says nothing about the model.",
                "A run over zero letters is not a clean run.",
            ]
        if not self.measured:
            return [
                f"UNKNOWN: all {self.ran} letters ended in a harness error, so this says nothing",
                "about the model. The first one reads:",
                f"  {self.results[0].slug}: {self.results[0].detail}",
            ]
        answered = self.ran - len(self.errors)
        out = [
            f"letters attempted       {self.ran}",
            f"letters read at all     {self.completed} of {self.ran}",
            f"properties correct      {self.checks_passed} of {self.checks_total}, "
            f"over the {answered} letters the model answered",
            f"letters fully correct   {self.cases_passed} of {self.ran}",
            f"harness errors          {len(self.errors)}",
            f"forbidden text written  {len(self.safety_failures)}",
            f"guard sent back an answer {self.guard_denials} times, "
            f"on {self.letters_needing_the_guard} letters",
            "",
            "Twenty-odd letters read once each is a sample, not a verdict. Compare two runs case",
            "by case with the written file, and treat one letter changing side as noise until it",
            "does it twice. The guard line moves before the score does: a version that needs the",
            "guard more often is drifting even while its finished answers still look right.",
            "",
        ]
        for item in self.results:
            failed = [check for check in item.checks if not check.passed]
            mark = "ok  " if item.passed else "FAIL"
            denials = f" [guard {item.guard_denials}]" if item.guard_denials else ""
            out.append(f"{mark} {item.slug} ({item.actual_outcome}){denials}")
            if item.detail:
                out.append(f"       {item.detail}")
            for check in failed:
                out.append(f"       {check.name}: wanted {check.expected}, got {check.actual}")
        return out

    def as_dict(self) -> dict[str, object]:
        """The run in a shape two runs can be diffed in."""
        return {
            "measured": self.measured,
            "ran": self.ran,
            "completed": self.completed,
            "checks_passed": self.checks_passed,
            "checks_total": self.checks_total,
            "cases_passed": self.cases_passed,
            "errors": len(self.errors),
            "safety_failures": len(self.safety_failures),
            "guard_denials": self.guard_denials,
            "cases": [
                {
                    "slug": item.slug,
                    "actual_outcome": item.actual_outcome,
                    "detail": item.detail,
                    "guard_denials": item.guard_denials,
                    "passed": item.passed,
                    "checks": [
                        {
                            "name": check.name,
                            "passed": check.passed,
                            "expected": check.expected,
                            "actual": check.actual,
                            "safety": check.safety,
                        }
                        for check in item.checks
                    ],
                }
                for item in self.results
            ],
        }
