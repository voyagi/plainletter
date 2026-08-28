"""Read every letter in the set with a real model, and print what it got right.

Nothing here runs by accident. Reaching Bedrock costs money on somebody's account, so the toggle
has to be set and the run says how many letters it is about to read before it reads them.

The model is passed in rather than built here, which is what lets the harness be proven without a
cloud account: the tests drive this same function with a model that answers badly and check that
the scorecard says so. A harness that has only ever been run against a good model has never been
shown to notice a bad one.

    PLAINLETTER_EVAL=1 uv run python -m evals.run --json out/eval-before.json
    PLAINLETTER_EVAL=1 uv run python -m evals.run --only cjib-eerste-aanmaning
    uv run python -m evals.run --compare out/eval-before.json out/eval-after.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from plainletter.bedrock import BedrockReadingModel
from plainletter.guard import AuditTrail
from plainletter.intake import from_text
from plainletter.kb import known_sender_ids
from plainletter.pipeline import Pipeline, RefusedReadingError
from plainletter.reading_model import ReadingModel
from plainletter.settings import settings

from . import fingerprint
from .cases import TOGGLE, Case, cases, live_run_enabled, slugs
from .scoring import RunOutcome, Scorecard, score

MakeModel = Callable[[], ReadingModel]

COULD_NOT_RUN = 2


def tool_log(model: ReadingModel) -> tuple[str, ...]:
    """The audit trail this model kept, when it keeps one.

    Read off the model rather than passed alongside it, because the trail belongs to the model that
    made the calls and a second channel for it would be a second thing to keep in step. A model with
    no trail, which is every stand-in the tests use unless they want one, gives nothing and costs
    nothing.
    """
    audit = getattr(model, "audit", None)
    return tuple(audit.entries) if isinstance(audit, AuditTrail) else ()


def read_one(case: Case, model: ReadingModel) -> RunOutcome:
    """One letter through the whole pipeline, with the three endings kept apart.

    A refusal is the product working and is recorded as an outcome. Anything else is the harness
    failing, and it stays labelled that way so a broken eval never reads as a bad model.
    """
    pipeline = Pipeline(model=model)
    try:
        reading = pipeline.run(
            from_text(case.text),
            visitor_language=case.expected.visitor_language,
            today=case.expected.today,
        )
    except RefusedReadingError as refusal:
        return RunOutcome(refusal=str(refusal), tool_log=tool_log(model))
    except Exception as broken:
        # One bad letter must not end the run, and it must not be scored as a wrong answer either.
        return RunOutcome(error=f"{type(broken).__name__}: {broken}", tool_log=tool_log(model))
    return RunOutcome(reading=reading, tool_log=tool_log(model))


def run(selected: Iterable[Case], make_model: MakeModel) -> Scorecard:
    """Score every case given. A fresh model per letter, so nothing carries over between them."""
    card = Scorecard()
    for case in selected:
        model = make_model()
        card.add(score(case, read_one(case, model)))
    return card


def bedrock_model() -> ReadingModel:
    return BedrockReadingModel(sender_ids=known_sender_ids())


def stamp(card: Scorecard) -> dict[str, Any]:
    """The run, plus what it was a run of. The hashes are what make two files comparable."""
    live = settings()
    return {
        "prompts": fingerprint.prompts(),
        "corpus": fingerprint.corpus(),
        "reading_model": live.reading_model,
        "drafting_model": live.drafting_model,
        "region": live.region,
        **card.as_dict(),
    }


def compare(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Which letters changed side, which is the only comparison worth making.

    A headline moving from 17 to 19 is four letters changing in both directions as often as it is
    two improving, and the second reading is the one people reach for.
    """
    out: list[str] = []
    for name in ("prompts", "corpus"):
        was, now = before.get(name), after.get(name)
        out.append(f"{name:8s} {was} -> {now}" + ("" if was == now else "   CHANGED"))
    if before.get("corpus") != after.get("corpus"):
        out.append("The letters themselves changed, so the two scores are not measuring the same")
        out.append("thing. Read the case list below as a list of differences, not of regressions.")
    out.append("")

    was_passed = {item["slug"]: bool(item["passed"]) for item in before.get("cases", [])}
    now_passed = {item["slug"]: bool(item["passed"]) for item in after.get("cases", [])}
    both = sorted(set(was_passed) & set(now_passed))

    broke = [slug for slug in both if was_passed[slug] and not now_passed[slug]]
    fixed = [slug for slug in both if not was_passed[slug] and now_passed[slug]]
    out.append(f"still correct   {sum(1 for s in both if was_passed[s] and now_passed[s])}")
    out.append(f"still wrong     {sum(1 for s in both if not was_passed[s] and not now_passed[s])}")
    out.append(f"newly correct   {len(fixed)}")
    out.append(f"newly wrong     {len(broke)}")
    for slug in broke:
        out.append(f"  worse  {slug}")
    for slug in fixed:
        out.append(f"  better {slug}")

    only_before = sorted(set(was_passed) - set(now_passed))
    only_after = sorted(set(now_passed) - set(was_passed))
    for slug in only_before:
        out.append(f"  gone   {slug} (in the earlier run only)")
    for slug in only_after:
        out.append(f"  new    {slug} (in the later run only)")

    safety = int(after.get("safety_failures", 0))
    if safety:
        out.append("")
        out.append(f"{safety} forbidden strings reached the desk in the later run. That is not a")
        out.append("score to weigh against the others: fix it before the change goes anywhere.")

    out.append("")
    out.append(
        f"guard sent back an answer {before.get('guard_denials')} times, then "
        f"{after.get('guard_denials')}"
    )
    out.append("A version that leans on the guard more often has got worse even when the finished")
    out.append("answers still look the same.")
    return out


def _load(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evals.run", description="Read the eval set with Bedrock")
    parser.add_argument("--only", action="append", default=[], help="one slug, repeatable")
    parser.add_argument("--json", type=Path, default=None, help="write the run for later diffing")
    parser.add_argument(
        "--compare",
        nargs=2,
        type=Path,
        metavar=("EARLIER", "LATER"),
        default=None,
        help="compare two written runs and exit, reading no letters and calling no model",
    )
    args = parser.parse_args(argv)

    if args.compare is not None:
        earlier, later = args.compare
        for line in compare(_load(earlier), _load(later)):
            print(line)
        return 0

    if not live_run_enabled():
        print(
            f"Not running. This reads every letter with a real model and costs money, so set "
            f"{TOGGLE}=1 to ask for it.",
            file=sys.stderr,
        )
        return COULD_NOT_RUN

    unknown = sorted(set(args.only) - set(slugs()))
    if unknown:
        print(f"No such letter: {', '.join(unknown)}", file=sys.stderr)
        return COULD_NOT_RUN

    wanted = set(args.only)
    selected = [case for case in cases() if not wanted or case.slug in wanted]
    if not selected:
        print("No letters to read, which is not a clean run.", file=sys.stderr)
        return COULD_NOT_RUN

    print(
        f"Reading {len(selected)} letters with the live model. Each one costs a turn for reading, "
        "explaining, planning and drafting, and a further turn whenever a route is looked up or "
        "the guard sends an answer back to be written again."
    )
    card = run(selected, bedrock_model)

    print()
    for line in card.lines():
        print(line)

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(stamp(card), indent=2), encoding="utf-8")
        print(f"\nwritten {args.json}")

    if not card.measured:
        return COULD_NOT_RUN
    return 0 if card.cases_passed == card.ran and not card.errors else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
