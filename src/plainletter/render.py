"""The two things the visitor takes home: one printed page and one calendar reminder.

Both are built from the reading with plain Python. No model is involved once the facts are
grounded, so the card cannot say anything the check did not allow, and redaction is applied here as
well as upstream because this is the last place the text passes through before a printer.

The card is designed for the printer that actually stands behind a library counter, which is
monochrome. Nothing on it carries meaning in colour: urgency is a word plus a treatment that
survives greyscale, and the marks are numbered at the foot against the passages they came from, in
the same numbering the screen used, so a volunteer can say "number four" and both people find it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from html import escape

from icalendar import Alarm, Calendar, Event

from .dutch import format_date
from .redact import redact
from .schemas import DeskReading, Explanation, Urgency

RTL_LANGUAGES = frozenset({"ar", "fa", "he", "ur", "ps"})

REMINDER_LEAD_DAYS = 3

_URGENCY_WORD_NL = {
    Urgency.OVERDUE: "Te laat",
    Urgency.DUE_SOON: "Bijna te laat",
    Urgency.AMPLE: "Nog tijd",
    Urgency.UNKNOWN: "Geen datum",
}


def is_rtl(language: str) -> bool:
    return language.split("-")[0].lower() in RTL_LANGUAGES


def desk_card_html(reading: DeskReading, today: date, *, case_id: str | None = None) -> str:
    """The one-page bilingual card, styled to print readably in black and white.

    The case id is printed only when there is a case, so a visitor who declined to be remembered
    takes home nothing that says otherwise.
    """
    visitor = reading.visitor_language
    direction = "rtl" if is_rtl(visitor) else "ltr"
    dutch, other = _explanations(reading)
    case = (
        f'<p class="small"><strong>Zaaknummer {escape(case_id)}.</strong> '
        "Neem deze kaart mee als u terugkomt, dan gaat de balie verder waar u gebleven was.</p>"
        if case_id
        else ""
    )

    rows = "\n".join(
        _pair_row(question, dutch_text, visitor_text, visitor, direction)
        for question, dutch_text, visitor_text in (
            ("Wat is dit?", dutch.what_is_this, other.what_is_this),
            ("Wat gebeurt er als u niets doet?", dutch.if_you_do_nothing, other.if_you_do_nothing),
            ("Voor wanneer?", dutch.by_when, other.by_when),
        )
    )
    steps = "\n".join(
        f'<li><span class="no">{step.order}</span>'
        f"<span>{escape(redact(step.dutch))}{_route(step.official_route)}</span>"
        f'<span class="r" lang="{escape(visitor)}" dir="{direction}">'
        f"{escape(redact(step.visitor))}{_route(step.official_route)}</span></li>"
        for step in reading.steps
    )
    handoff = (
        f'<p class="handoff"><strong>Als het ingewikkeld wordt.</strong> '
        f"{escape(reading.handoff.referral)}</p>"
        if reading.handoff.required
        else ""
    )

    return f"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="De baliekaart bij deze brief: wat het is, voor wanneer, wat er
gebeurt als u niets doet, en wat u nu doet, in twee talen op een vel.">
<title>{escape(reading.sender_name)} - {escape(reading.letter_type)}</title>
<style>{_CARD_CSS}</style>
</head>
<body>
<div class="sheet">
  <div class="band">
    <div>
      <h1 class="who">{escape(reading.sender_name)}</h1>
      <div class="what">{escape(reading.letter_type)}</div>
    </div>
    <div class="ref">{escape(_reference(reading))}</div>
  </div>
  {_deadline_block(reading)}
  <div class="rows">{rows}</div>
  <div class="acts"><h2>Wat u nu doet</h2><ol>{steps}</ol></div>
  {_key_block(reading)}
  <div class="foot">
    <div>
      {handoff}
      {case}
      <p class="small">Plainletter legt brieven uit en geeft geen juridisch advies.
      Gemaakt op {escape(format_date(today))}.</p>
    </div>
    <div>
      <p class="notes-label">Aantekeningen aan de balie</p>
      <div class="notes"></div>
    </div>
  </div>
</div>
</body>
</html>
"""


def reminder_ics(reading: DeskReading, *, uid: str) -> str:
    """An all-day reminder on the deadline, with an alarm a few days ahead of it."""
    if reading.deadline is None:
        raise ValueError("a reminder needs a deadline; this reading has none")

    deadline = reading.deadline.on
    calendar = Calendar()
    calendar.add("prodid", "-//Plainletter//NL//EN")
    calendar.add("version", "2.0")

    event = Event()
    event.add("uid", uid)
    event.add("summary", f"{reading.sender_name}: {reading.letter_type}")
    event.add(
        "description",
        redact(
            f"Uiterste dag: {format_date(deadline)}. "
            + " ".join(step.dutch for step in reading.steps)
        ),
    )
    event.add("dtstart", deadline)
    event.add("dtend", deadline + timedelta(days=1))
    # A fixed stamp keeps the file byte-identical for the same reading, which is what lets a test
    # compare one instead of comparing "roughly this".
    event.add("dtstamp", datetime.combine(deadline, time(9, 0), tzinfo=UTC))

    alarm = Alarm()
    alarm.add("action", "DISPLAY")
    alarm.add("description", f"{reading.sender_name}: nog {REMINDER_LEAD_DAYS} dagen")
    alarm.add("trigger", timedelta(days=-REMINDER_LEAD_DAYS))
    event.add_component(alarm)

    calendar.add_component(event)
    ical: bytes = calendar.to_ical()
    return ical.decode("utf-8")


def _explanations(reading: DeskReading) -> tuple[Explanation, Explanation]:
    by_language = {item.language: item for item in reading.explanations}
    dutch = by_language.get("nl")
    other = by_language.get(reading.visitor_language, dutch)
    if dutch is None or other is None:
        raise ValueError("a desk card needs a Dutch explanation and one in the visitor's language")
    return dutch, other


def _reference(reading: DeskReading) -> str:
    reference = reading.facts.reference
    return f"Kenmerk {reference.value}" if reference else "Geen kenmerk in de brief"


def _route(url: str | None) -> str:
    return f'<br><span class="route">{escape(_short_route(url))}</span>' if url else ""


def _short_route(url: str) -> str:
    """A route a person types off paper, so the scheme and the www prefix are noise."""
    return url.removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")


def _deadline_block(reading: DeskReading) -> str:
    view = reading.deadline
    if view is None:
        return (
            '<div class="deadline none"><div class="lead">Deze brief noemt geen uiterste datum.'
            "</div></div>"
        )
    word = _URGENCY_WORD_NL[view.urgency]
    days = (
        f"Nog {view.days_left} dagen."
        if view.days_left >= 0
        else f"{abs(view.days_left)} dagen te laat."
    )
    post_by = (
        f" Post uw brief uiterlijk {format_date(view.post_by)}." if view.post_by is not None else ""
    )
    return f"""<div class="deadline {escape(view.urgency.value)}">
    <div><div class="lead">Uiterste dag: {escape(format_date(view.on))}</div>
    <div class="sub">{escape(days)}{escape(post_by)}</div></div>
    <div class="state">{escape(word)}</div>
  </div>"""


def _key_block(reading: DeskReading) -> str:
    """The key at the foot: each numeral against the words on the letter it was drawn under.

    A gap prints as a broken rule with no number, which is how the card says the desk could not
    read something. There is no wording that could be mistaken for a fact, because there is no
    fact.
    """
    keys = "\n".join(
        f'<div class="k"><span class="n">{key.number}</span>'
        f"<span>{escape(redact(_one_line(key.text)))}</span></div>"
        for key in reading.letter.keys
    )
    gaps = "\n".join(
        f'<div class="k"><span class="broken"></span>'
        f"<span>{escape(gap.field)}: {escape(gap.ask_the_visitor)}</span></div>"
        for gap in reading.letter.gaps
    )
    if not keys and not gaps:
        return ""
    return f'<div class="keys"><h2>De markeringen op de brief</h2>{keys}{gaps}</div>'


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _pair_row(question: str, dutch: str, visitor: str, language: str, direction: str) -> str:
    return (
        f'<div class="prow"><span class="q">{escape(question)}</span>'
        f"<span>{escape(redact(dutch))}</span>"
        f'<span class="r" lang="{escape(language)}" dir="{direction}">'
        f"{escape(redact(visitor))}</span></div>"
    )


# Print first, and monochrome first. Every urgency state carries a word plus a treatment that
# survives greyscale, because the only printer this page ever reaches has no colour to lose.
_CARD_CSS = """
@page { size: A4; margin: 12mm; }
* { box-sizing: border-box; }
body { font-family: "Atkinson Hyperlegible Next", system-ui, sans-serif;
       font-variant-numeric: tabular-nums; color: #1a1a1a; background: #fff;
       margin: 0; font-size: 11.5px; line-height: 1.5; }
.sheet { max-width: 190mm; margin: 0 auto; }
.band { border: 2.5px solid #1a1a1a; padding: 10px 13px; display: flex;
        justify-content: space-between; align-items: baseline; gap: 16px; }
.who { font-weight: 700; font-size: 19px; margin: 0; line-height: 1.25; }
.what { font-size: 12px; }
.ref { text-align: right; font-size: 12px; font-weight: 700; }
.deadline { border: 2.5px solid #1a1a1a; border-top: 0; padding: 10px 13px; display: flex;
            justify-content: space-between; align-items: center; gap: 16px; }
.deadline.due_soon { background-image:
  repeating-linear-gradient(-45deg, #d8d8d8 0 6px, transparent 6px 14px); }
.deadline.overdue { background-image:
  repeating-linear-gradient(-45deg, #b4b4b4 0 3px, transparent 3px 9px); }
.deadline.overdue .lead { text-decoration: line-through; }
.deadline .lead { font-weight: 700; font-size: 18px; }
.deadline .sub { font-size: 12px; }
.deadline .state { border: 2px solid #1a1a1a; background: #fff; padding: 5px 10px;
                   font-weight: 700; font-size: 11px; letter-spacing: .1em;
                   text-transform: uppercase; white-space: nowrap; }
.prow { display: grid; grid-template-columns: 1fr 1fr; gap: 3px 20px; padding: 11px 0;
        border-bottom: 1px solid #c9c9c9; }
.prow .q { grid-column: 1 / -1; font-size: 10px; font-weight: 700; text-transform: uppercase;
           letter-spacing: .1em; color: #4a4a4a; }
.r { text-align: right; }
.acts h2 { font-size: 13px; margin: 16px 0 8px; }
.acts ol { margin: 0; padding: 0; list-style: none; }
.acts li { display: grid; grid-template-columns: 20px 1fr 1fr; gap: 6px 20px; padding: 8px 0;
           border-top: 1px solid #c9c9c9; }
.acts li:first-child { border-top: 1.5px solid #1a1a1a; }
.no { width: 18px; height: 18px; background: #1a1a1a; color: #fff; font-size: 11px;
      font-weight: 700; line-height: 18px; text-align: center; }
.route { font-weight: 700; }
.keys { margin-top: 14px; border-top: 2.5px solid #1a1a1a; padding-top: 9px; }
.keys h2 { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .1em;
           color: #4a4a4a; margin: 0 0 6px; }
.keys .k { display: grid; grid-template-columns: 20px 1fr; gap: 8px; padding: 3px 0;
           font-size: 10.5px; color: #333; }
.keys .n { width: 18px; height: 18px; border: 1px solid #1a1a1a; font-size: 10px;
           font-weight: 700; line-height: 16px; text-align: center; }
.keys .broken { width: 18px; border-top: 1px dashed #777; margin-top: 8px; }
.foot { margin-top: 12px; display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.handoff { border-left: 4px solid #1a1a1a; padding-left: 10px; font-size: 11px; margin: 0 0 8px; }
.notes-label { font-size: 9.5px; text-transform: uppercase; letter-spacing: .1em; color: #555;
               margin: 0 0 4px; }
.notes { border: 1px dashed #8a8a8a; height: 24mm; }
.small { font-size: 10px; color: #555; margin: 0; }
"""
