"""Masking the identifiers a letter carries that nobody at the desk needs to see.

A bank account number and whatever national number the country prints are the highest-value data on
an official letter and neither is needed to explain it, so both are masked before anything is shown,
printed, logged or remembered. The bank account is handled here because an IBAN is the same object
wherever it is issued; the national number is the locale's, because it is not.

Reference numbers are deliberately NOT masked: the visitor has to quote one to pay, and it travels
as a structured field rather than inside free text. That separation is what lets the national number
rule be aggressive about bare digit runs without breaking the payment step.
"""

from __future__ import annotations

import re

from .locales import active

_IBAN = re.compile(r"\b([A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,3})?)\b")

IBAN_MASK_PREFIX = "IBAN "


def redact(text: str) -> str:
    """Return the text with every bank account and national identifier masked."""
    return active().mask_identifiers(_IBAN.sub(_mask_iban, text))


def is_valid_iban(candidate: str) -> bool:
    """The ISO 13616 mod-97 check, so a reference that merely looks like an IBAN is left alone."""
    bare = re.sub(r"[^A-Z0-9]", "", candidate.upper())
    if len(bare) < 15 or len(bare) > 34 or not bare[:2].isalpha() or not bare[2:4].isdigit():
        return False
    rotated = bare[4:] + bare[:4]
    digits = "".join(str(int(char, 36)) for char in rotated)
    return int(digits) % 97 == 1


def _mask_iban(match: re.Match[str]) -> str:
    candidate = match.group(1)
    if not is_valid_iban(candidate):
        return candidate
    bare = re.sub(r"[^A-Z0-9]", "", candidate.upper())
    return f"{IBAN_MASK_PREFIX}{bare[:2]}** **** **** {bare[-4:]}"
