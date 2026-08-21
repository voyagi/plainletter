import json
from pathlib import Path

import pytest
from scripts.export_web_data import DATA, landing_reading, sample_index

FILES = {"samples.json": sample_index, "sample-reading.json": landing_reading}


@pytest.mark.parametrize("name", sorted(FILES))
def test_the_exported_page_data_still_matches_what_the_agent_produces(name: str) -> None:
    # The landing page shows a real reading rather than a picture of one, so the file on disk is
    # the agent's output. Regenerate it with `npm run export:web-data` when this fails; a stale
    # export would put a reading on a public page that the product no longer produces.
    path: Path = DATA / name
    assert path.exists(), f"{name} is missing; run npm run export:web-data"
    assert json.loads(path.read_text(encoding="utf-8")) == json.loads(
        json.dumps(FILES[name](), ensure_ascii=False)
    )


def test_the_landing_letter_shows_both_a_mark_and_a_broken_key() -> None:
    # The refusal is the most important thing on the page, and it is shown rather than asserted, so
    # the letter the page is built from has to actually contain one.
    exported = json.loads((DATA / "sample-reading.json").read_text(encoding="utf-8"))
    letter = exported["reading"]["letter"]
    assert letter["keys"], "the landing letter has no marks to walk"
    assert letter["gaps"], "the landing letter has nothing the desk refused to read"
    assert any(line["gap"] for line in letter["lines"])
