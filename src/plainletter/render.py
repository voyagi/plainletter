"""The two things the visitor takes home: one printed page and one calendar reminder.

Both are built from the reading with plain Python. No model is involved once the facts are
grounded, so the card cannot say anything the check did not allow, and redaction is applied here as
well as upstream because this is the last place the text passes through before a printer.
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


def desk_card_html(reading: DeskReading, today: date) -> str:
    """The one-page bilingual card, styled to print readably in black and white."""
    visitor = reading.visitor_language
    direction = "rtl" if is_rtl(visitor) else "ltr"
    dutch, other = _explanations(reading)

    deadline_block = _deadline_block(reading)
    rows = "\n".join(
        _pair_row(question, dutch_text, visitor_text, visitor, direction)
        for question, dutch_text, visitor_text in (
            ("Wat is dit?", dutch.what_is_this, other.what_is_this),
            ("Wat gebeurt er als u niets doet?", dutch.if_you_do_nothing, other.if_you_do_nothing),
            ("Voor wanneer?", dutch.by_when, other.by_when),
        )
    )
    steps = "\n".join(
        f"<li><span>{escape(redact(step.dutch))}</span>"
        f'<span lang="{escape(visitor)}" dir="{direction}">'
        f"{escape(redact(step.visitor))}</span></li>"
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
<title>{escape(reading.sender_name)} - {escape(reading.letter_type)}</title>
<style>{_CARD_CSS}</style>
</head>
<body>
<div class="sheet">
  <div class="band">
    <div>
      <div class="who">{escape(reading.sender_name)}</div>
      <div class="what">{escape(reading.letter_type)}</div>
    </div>
    <div class="ref">{escape(_reference(reading))}</div>
  </div>
  {deadline_block}
  <div class="rows">{rows}</div>
  <div class="acts"><h2>Wat u nu doet</h2><ol>{steps}</ol></div>
  <div class="foot">
    {handoff}
    <p class="notes-label">Aantekeningen aan de balie</p>
    <div class="notes"></div>
    <p class="small">Plainletter legt brieven uit en geeft geen juridisch advies.
    Gemaakt op {escape(format_date(today))}.</p>
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


def _pair_row(question: str, dutch: str, visitor: str, language: str, direction: str) -> str:
    return (
        f'<div class="prow"><div><h2>{escape(question)}</h2><p>{escape(redact(dutch))}</p></div>'
        f'<div lang="{escape(language)}" dir="{direction}"><p>{escape(redact(visitor))}</p></div>'
        f"</div>"
    )


# Print first: the band greys out, and every urgency state carries a word plus its own hatch or
# outline, so the page still reads on the black and white printer behind a library counter.
_CARD_CSS = """
@page { size: A4; margin: 12mm; }
body { font-family: "Atkinson Hyperlegible Next", system-ui, sans-serif;
       color: #14213D; margin: 0; }
.sheet { max-width: 190mm; margin: 0 auto; }
.band { background: #F5C400; border: 3px solid #14213D; padding: 12px 16px;
        display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.who { font-weight: 800; font-size: 22px; }
.what { font-size: 14px; }
.ref { font-variant-numeric: tabular-nums; font-size: 13px; text-align: right; }
.deadline { margin-top: 12px; border: 3px solid #14213D; padding: 10px 14px;
            display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.deadline.due_soon { background-color: #FFE9A8;
  background-image: repeating-linear-gradient(-45deg,
    rgba(180,83,9,.55) 0 7px, transparent 7px 16px); }
.deadline.overdue { background: #C8102E; color: #fff; }
.deadline.ample { background: #fff; }
.deadline .lead { font-weight: 800; font-size: 18px; }
.deadline .sub { font-size: 13px; }
.deadline .state { font-weight: 800; text-transform: uppercase; letter-spacing: .12em;
                   border: 2px solid currentColor; padding: 5px 10px; font-size: 12px; }
.prow { display: grid; grid-template-columns: 1fr 1fr; gap: 0 24px;
        padding: 10px 0; border-bottom: 1px solid #14213D; }
.prow h2 { font-size: 15px; margin: 0 0 4px; }
.prow p { margin: 0; font-size: 13px; line-height: 1.5; }
.acts h2 { font-size: 16px; margin: 14px 0 6px; }
.acts ol { margin: 0; padding: 0; list-style: none; counter-reset: s; }
.acts li { counter-increment: s; display: grid; grid-template-columns: 20px 1fr 1fr;
           gap: 8px 24px; padding: 7px 0; border-top: 1px solid #14213D; font-size: 13px; }
.acts li::before { content: counter(s); font-weight: 800; background: #14213D; color: #fff;
                   text-align: center; height: 18px; line-height: 18px; }
.foot { margin-top: 14px; border-top: 3px solid #14213D; padding-top: 10px; font-size: 12px; }
.handoff { border-left: 5px solid #B45309; padding-left: 10px; }
.notes-label { text-transform: uppercase; letter-spacing: .12em; font-size: 10px; color: #4B5670; }
.notes { border: 1px dashed #14213D; height: 26mm; }
.small { color: #4B5670; }
"""
