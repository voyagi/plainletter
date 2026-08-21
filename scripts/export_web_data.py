"""Write the two files the public pages are built from, straight out of the agent's own corpus.

The landing page shows a real reading of a real sample letter rather than a picture of one, and the
console lists the letters a visitor can try. Both are the agent's output, exported once with a
pinned reading date so the page is a dated example instead of a live claim that quietly goes stale.

Run it with `npm run export:web-data`. A test refuses any drift between these files and the agent.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from plainletter.app import read_letter
from plainletter.demo import sample_names, scripted_reading

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "web" / "src" / "data"

# The landing page's letter, and the day it was read. Pinning the date is what keeps "nog 25 dagen"
# honest: the page says when the reading was made, so nobody reads the count as today's.
LANDING_SAMPLE = "cjib-verkeersboete"
READ_ON = date(2026, 8, 21)


def sample_index() -> list[dict[str, str]]:
    index = []
    for name in sample_names():
        reading = scripted_reading(name)
        facts = reading.facts
        index.append(
            {
                "id": name,
                "sender": facts.sender_name.value if facts.sender_name else name,
                "type": facts.letter_type.value if facts.letter_type else "Brief",
                "language": reading.visitor_language,
            }
        )
    return index


def landing_reading() -> dict[str, Any]:
    answer = read_letter({"sample": LANDING_SAMPLE, "today": READ_ON.isoformat()})
    if not isinstance(answer, dict) or "reading" not in answer:
        raise SystemExit(f"the agent did not read {LANDING_SAMPLE}: {answer}")
    return {"read_on": READ_ON.isoformat(), **answer}


def write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    write(DATA / "samples.json", sample_index())
    write(DATA / "sample-reading.json", landing_reading())


if __name__ == "__main__":
    main()
