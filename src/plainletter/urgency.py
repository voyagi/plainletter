"""Turning a deadline into the two numbers a frightened person actually needs.

How many days are left, and which day a posted reply has to leave the house. Both are plain
calendar arithmetic on a date the verifier has already grounded in the letter, so nothing here can
invent a deadline that the letter does not carry.

Easter comes from python-dateutil rather than a hand-rolled computus: the Dutch public holidays
that shift each year all hang off it, and a calendar rule is not the place to be clever.
"""

from __future__ import annotations

from datetime import date, timedelta

from dateutil.easter import EASTER_WESTERN, easter

from .schemas import DeadlineView, Urgency

# A posted objection has to arrive, not merely be sent, and neither the post nor the reader is
# instant. Five working days is the margin the desk card prints. It is a safety margin chosen here,
# not a delivery time quoted from a carrier.
POSTING_MARGIN_WORKING_DAYS = 5

# Inside two weeks a letter stops being something to deal with later. The band drives the word and
# the treatment on the board and the card, never the colour alone.
DUE_SOON_DAYS = 14


def dutch_public_holidays(year: int) -> frozenset[date]:
    """The national public holidays that close Dutch offices and post in a given year."""
    easter_sunday = easter(year, method=EASTER_WESTERN)
    holidays = {
        date(year, 1, 1),
        easter_sunday + timedelta(days=1),  # Tweede Paasdag
        easter_sunday + timedelta(days=39),  # Hemelvaartsdag
        easter_sunday + timedelta(days=50),  # Tweede Pinksterdag
        date(year, 12, 25),
        date(year, 12, 26),
        _kings_day(year),
    }
    if year % 5 == 0:
        # Bevrijdingsdag is a national day off in the lustrum years and an ordinary working day
        # in between.
        holidays.add(date(year, 5, 5))
    return frozenset(holidays)


def is_working_day(day: date) -> bool:
    return day.weekday() < 5 and day not in dutch_public_holidays(day.year)


def working_days_before(deadline: date, count: int) -> date:
    """The date that is `count` working days before the deadline."""
    if count < 0:
        raise ValueError("count must not be negative")
    day = deadline
    remaining = count
    while remaining > 0:
        day -= timedelta(days=1)
        if is_working_day(day):
            remaining -= 1
    return day


def view(deadline: date | None, today: date) -> DeadlineView | None:
    """The deadline as the desk shows it, or None when the letter carries no deadline at all."""
    if deadline is None:
        return None

    days_left = (deadline - today).days
    if days_left < 0:
        urgency = Urgency.OVERDUE
    elif days_left <= DUE_SOON_DAYS:
        urgency = Urgency.DUE_SOON
    else:
        urgency = Urgency.AMPLE

    post_by = working_days_before(deadline, POSTING_MARGIN_WORKING_DAYS) if days_left >= 0 else None
    # A posting date already in the past is worse than none: it reads as an instruction the visitor
    # has failed rather than as the fact that only the counter or the website is left.
    if post_by is not None and post_by < today:
        post_by = None

    return DeadlineView(on=deadline, days_left=days_left, urgency=urgency, post_by=post_by)


def _kings_day(year: int) -> date:
    """27 April, or the Saturday before it when that falls on a Sunday."""
    day = date(year, 4, 27)
    return day - timedelta(days=1) if day.weekday() == 6 else day
