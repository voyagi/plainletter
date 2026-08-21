"""The command line the desk runs before there is a console in front of it.

`demo` runs the whole pipeline on a sample letter with a scripted reading, so the deterministic
half can be shown working with no cloud account. `read` takes a photograph, a PDF or a text file and
runs the same pipeline against Bedrock. Both end the same way: a printable card, a calendar
reminder, and a short summary of what was checked.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from . import intake
from .bedrock import BedrockReadingModel
from .demo import sample_input, sample_names, scripted_model, scripted_reading
from .intake import IntakeError, LetterInput
from .kb import known_sender_ids
from .pipeline import Pipeline, UngroundedOutputError
from .reading_model import ReadingModel
from .render import desk_card_html, reminder_ics
from .schemas import DeskReading

DEFAULT_SAMPLE = "cjib-verkeersboete"

REFUSED = 2
UNREADABLE = 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="plainletter", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="run the pipeline on a sample letter, no cloud account")
    demo.add_argument("--sample", default=DEFAULT_SAMPLE, choices=sample_names())
    demo.add_argument(
        "--language", default=None, help="visitor's language tag, default the sample's own"
    )
    _shared_arguments(demo)

    read = sub.add_parser("read", help="read a real letter with Bedrock")
    read.add_argument("path", type=Path, help="a photograph, a PDF, or a text file")
    read.add_argument("--language", required=True, help="the visitor's language tag, e.g. ar")
    _shared_arguments(read)

    args = parser.parse_args(argv)
    today = date.fromisoformat(args.today) if args.today else date.today()

    model: ReadingModel
    if args.command == "demo":
        letter = sample_input(args.sample)
        model = scripted_model(args.sample)
        language = args.language or scripted_reading(args.sample).visitor_language
    else:
        try:
            letter = intake.from_path(args.path)
        except IntakeError as problem:
            print(f"Cannot read that file. {problem}", file=sys.stderr)
            return UNREADABLE
        model = BedrockReadingModel(sender_ids=known_sender_ids())
        language = args.language

    try:
        reading = Pipeline(model=model).run(letter, visitor_language=language, today=today)
    except UngroundedOutputError as refusal:
        print(f"Refused: {refusal}", file=sys.stderr)
        print("Nothing was printed. Send this letter to a person.", file=sys.stderr)
        return REFUSED

    _write_outputs(reading, args.out, today)
    _summarise(reading, letter)
    return 0


def _shared_arguments(parser: argparse.ArgumentParser) -> None:
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


def _summarise(reading: DeskReading, letter: LetterInput) -> None:
    print(f"pages   {letter.pages} ({letter.kind})")
    if letter.pages_omitted:
        print(f"note    {letter.pages_omitted} further pages were not sent to the model")
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
