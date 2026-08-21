"""The command line the desk runs before there is a console in front of it.

`demo` runs the whole pipeline on a sample letter with a scripted reading, so the deterministic
half can be shown working with no cloud account. `read` runs the same pipeline against Bedrock on a
real file. Both end the same way: a printable card, a calendar reminder, and a short summary of
what was checked.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .bedrock import BedrockReadingModel
from .demo import cjib_model, sample_names, sample_text
from .kb import known_sender_ids
from .pipeline import Pipeline, UngroundedOutputError
from .reading_model import ReadingModel
from .render import desk_card_html, reminder_ics
from .schemas import DeskReading

DEFAULT_LANGUAGE = "ar"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="plainletter", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="run the pipeline on a sample letter, no cloud account")
    demo.add_argument("--sample", default="cjib-verkeersboete", choices=sample_names())
    _shared_arguments(demo)

    read = sub.add_parser("read", help="read a real letter with Bedrock")
    read.add_argument("path", type=Path, help="a text file holding the letter")
    _shared_arguments(read)

    args = parser.parse_args(argv)
    today = date.fromisoformat(args.today) if args.today else date.today()

    if args.command == "demo":
        letter_text = sample_text(args.sample)
        model: ReadingModel = cjib_model()
    else:
        letter_text = args.path.read_text(encoding="utf-8")
        model = BedrockReadingModel(sender_ids=known_sender_ids())

    try:
        reading = Pipeline(model=model).run(
            letter_text, letter_text, visitor_language=args.language, today=today
        )
    except UngroundedOutputError as refusal:
        print(f"Refused: {refusal}", file=sys.stderr)
        print("Nothing was printed. Send this letter to a person.", file=sys.stderr)
        return 2

    _write_outputs(reading, args.out, today)
    _summarise(reading)
    return 0


def _shared_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help="the visitor's language tag")
    parser.add_argument("--out", type=Path, default=Path("out"), help="where to write the card")
    parser.add_argument("--today", default=None, help="ISO date to count deadlines from")


def _write_outputs(reading: DeskReading, out: Path, today: date) -> None:
    out.mkdir(parents=True, exist_ok=True)
    card = out / "desk-card.html"
    card.write_text(desk_card_html(reading, today), encoding="utf-8")
    print(f"card    {card}")

    if reading.deadline is not None:
        reminder = out / "reminder.ics"
        reference = reading.facts.reference.value if reading.facts.reference else "plainletter"
        reminder.write_text(
            reminder_ics(reading, uid=f"{reference.replace(' ', '')}@plainletter"),
            encoding="utf-8",
        )
        print(f"reminder {reminder}")


def _summarise(reading: DeskReading) -> None:
    print(f"sender  {reading.sender_name}")
    print(f"type    {reading.letter_type}")
    if reading.deadline is not None:
        print(
            f"deadline {reading.deadline.on} "
            f"({reading.deadline.days_left} days, {reading.deadline.urgency.value})"
        )
    else:
        print("deadline none in the letter")
    checked = len(reading.verification.grounded)
    print(f"checked {checked} facts, {len(reading.verification.issues)} issues")
    for item in reading.facts.unreadable:
        print(f"unclear {item.field}: {item.ask_the_visitor}")
    if reading.handoff.required:
        print(f"handoff {reading.handoff.referral}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
