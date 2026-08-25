"""What one reading may cost, and how many readings one runtime may hand out in a day.

Three bounds, deliberately different in kind, because they fail differently and only one of them is
absolute.

`max_tokens` travels with every model call, so it holds on the first request after a cold start as
firmly as on the thousandth. It is the bound on what one letter can cost, and it is the reason a
prompt that goes wrong stops rather than writes until the model runs out of things to say.

The daily ceiling below is counted in this process, and that is stated rather than hidden. The
runtime is recycled on its own lifecycle schedule and more than one of it can be running, so this
counter is not the deployment's budget for the day: it is the bound on one caller looping inside one
runtime, checked before the first model call so that reaching it costs nothing.

What actually caps the bill is an account budget alarm, which only the account holder can set. It is
on the human list for exactly that reason, and nothing here replaces it.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

# The writing stages answer with a filled-in schema rather than with prose, and the longest draft in
# the sample set is a two-language objection. This sits well above that and far below what a model
# writes when a prompt has gone wrong.
MAX_OUTPUT_TOKENS = 4096

# Transcription is the one stage whose answer grows with the upload, because it types out every line
# of every page. A page of a Dutch official letter is a few hundred words; the allowance per page is
# several times that so a dense page is never clipped.
TRANSCRIPTION_TOKENS_PER_PAGE = 2000

# Twenty pages is the Converse limit on images in one request, so this ceiling is only reached by a
# dossier somebody photographed as if it were one letter. Truncating there is the safe direction:
# the verifier grounds facts against the transcript, so a fact from a page that never got typed out
# is refused rather than printed.
MAX_TRANSCRIPTION_TOKENS = 16000

DEFAULT_READINGS_PER_DAY = 200


def transcription_tokens(pages: int) -> int:
    return min(max(pages, 1) * TRANSCRIPTION_TOKENS_PER_PAGE, MAX_TRANSCRIPTION_TOKENS)


@dataclass(frozen=True)
class ReadingClaim:
    """The answer to "may this letter be read", and what it was decided against."""

    allowed: bool
    # Readings used today including this one, or None when the claim was refused. None rather than
    # the ceiling, because a refusal establishes only that the count is at or above it.
    used: int | None
    limit: int
    day: str


def _utc_day() -> str:
    return datetime.now(UTC).date().isoformat()


@dataclass
class DailyReadings:
    """A ceiling on model-backed readings per UTC day, claimed before the first model call."""

    limit: int
    day_of: Callable[[], str] = _utc_day
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _day: str = ""
    _used: int = 0

    def claim(self) -> ReadingClaim:
        """Take one reading off today's ceiling, or refuse. Never raises for being over."""
        day = self.day_of()
        with self._lock:
            if day != self._day:
                self._day = day
                self._used = 0
            if self._used >= self.limit:
                return ReadingClaim(allowed=False, used=None, limit=self.limit, day=day)
            self._used += 1
            return ReadingClaim(allowed=True, used=self._used, limit=self.limit, day=day)
