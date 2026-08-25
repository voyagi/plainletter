"""The boundary the README claims, checked rather than promised.

The README tells a judge exactly which files carry the Netherlands. That sentence is worth nothing
unless something fails when it stops being true, so this is that something: it reads every module in
the package and refuses a Dutch word in any file that is not on the list.

The list below is the whole claim. Adding a file to it is a decision to be made in the open, in a
diff, with a reason.
"""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "plainletter"

# The files a second country replaces. Everything else in the package is country-neutral.
COUNTRY_SPECIFIC = {
    "locales/nl.py",
    # The five prompts name the country and the language the letter is written in. They are the
    # instructions a second country rewrites, not machinery it reuses.
    "reading_model.py",
}

# Words that only appear in Dutch, chosen from what the desk card, the referrals and the letters
# actually print. Short and common enough that any real leak trips at least one of them.
DUTCH_WORDS = frozenset(
    {
        "aan",
        "aantekeningen",
        "afzender",
        "balie",
        "bedrag",
        "brief",
        "brieven",
        "dagen",
        "deze",
        "doet",
        "gebeurt",
        "geen",
        "gemaakt",
        "het",
        "juridisch",
        "kenmerk",
        "laat",
        "loket",
        "niet",
        "onbekende",
        "uiterste",
        "uw",
        "verborgen",
        "wanneer",
        "wat",
        "zaaknummer",
    }
)

# Two Dutch words are load bearing in shared code and cannot move behind the boundary without
# changing what the model is asked for. Both are named here so the exception is visible rather than
# quietly absorbed into the word list.
#
# `dutch` is a field name on the bilingual pair in `schemas.py`: it reaches the model as part of the
# structured-output tool schema and is recorded in twelve sample readings, so renaming it changes
# the contract every one of those was verified against.
#
# `nl` is a BCP 47 tag in example text and in the sample data, which is a language code rather than
# a Dutch word.
ALLOWED_IN_SHARED_CODE = frozenset({"dutch", "nl"})


def _modules() -> list[Path]:
    return sorted(path for path in PACKAGE.rglob("*.py") if "__pycache__" not in path.parts)


def _strings(source: str) -> list[str]:
    """Every string literal in the module, docstrings included."""
    return [
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def test_the_boundary_list_points_at_files_that_exist() -> None:
    # A renamed file would otherwise silently drop out of the list and take its exemption with it.
    missing = [name for name in sorted(COUNTRY_SPECIFIC) if not (PACKAGE / name).exists()]
    assert not missing, f"the boundary names files that are gone: {missing}"


def test_no_dutch_word_reaches_shared_code() -> None:
    leaks: dict[str, set[str]] = {}
    for module in _modules():
        relative = module.relative_to(PACKAGE).as_posix()
        if relative in COUNTRY_SPECIFIC:
            continue
        words = {
            word.strip(".,:;!?()[]{}\"'").casefold()
            for text in _strings(module.read_text(encoding="utf-8"))
            for word in text.split()
        }
        found = (words & DUTCH_WORDS) - ALLOWED_IN_SHARED_CODE
        if found:
            leaks[relative] = found
    assert not leaks, (
        "Dutch reached shared code. Move it into src/plainletter/locales/nl.py, or add the file to "
        f"COUNTRY_SPECIFIC and to the README's list on purpose: {leaks}"
    )


def test_the_word_list_would_actually_catch_a_leak() -> None:
    # A detector nobody has seen fail is indistinguishable from a repo with nothing to find.
    planted = '"Het Juridisch Loket, 0800 8020"'
    words = {word.strip(".,").casefold() for text in _strings(planted) for word in text.split()}
    assert (words & DUTCH_WORDS) - ALLOWED_IN_SHARED_CODE
