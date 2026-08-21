"""Masking the two identifiers a letter carries that nobody at the desk needs to see.

A citizen service number (BSN) and a bank account number are the highest-value data on a Dutch
official letter and neither is needed to explain it, so they are masked before anything is shown,
printed, logged or remembered.

Reference numbers are deliberately NOT masked: the visitor has to quote one to pay, and it travels
as a structured field rather than inside free text. That separation is what lets this module be
aggressive about nine-digit runs without breaking the payment step.
"""

from __future__ import annotations

import re

_BSN_LABELLED = re.compile(
    r"\b(?P<label>bsn|burgerservicenummer|sofinummer)\b(?P<gap>[\s:.]*)(?P<digits>\d[\d\s.-]{7,13}\d)",
    re.IGNORECASE,
)
_NINE_DIGITS = re.compile(r"(?<!\d)(\d{9})(?!\d)")
_IBAN = re.compile(r"\b([A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,3})?)\b")

BSN_MASK = "BSN verborgen"
IBAN_MASK_PREFIX = "IBAN "


def redact(text: str) -> str:
    """Return the text with every citizen service number and bank account number masked."""
    without_iban = _IBAN.sub(_mask_iban, text)
    without_labelled = _BSN_LABELLED.sub(_mask_labelled_bsn, without_iban)
    return _NINE_DIGITS.sub(_mask_bare_bsn, without_labelled)


def looks_like_bsn(digits: str) -> bool:
    """The elfproef the Dutch government uses to validate a BSN.

    Nine digits weighted 9 down to 2, the last one subtracted, and the total divisible by eleven.
    A random nine-digit reference passes about one time in eleven, which is why a false mask is
    accepted here and a missed BSN is not.
    """
    bare = re.sub(r"\D", "", digits)
    if len(bare) != 9:
        return False
    weights = [9, 8, 7, 6, 5, 4, 3, 2, -1]
    total = sum(int(digit) * weight for digit, weight in zip(bare, weights, strict=True))
    return total % 11 == 0


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


def _mask_labelled_bsn(match: re.Match[str]) -> str:
    # A number sitting behind the words "BSN" or "burgerservicenummer" is masked whatever it is:
    # the label is stronger evidence than any checksum, and a mislabelled number is still personal.
    return f"{match.group('label')}{match.group('gap')}{BSN_MASK}"


def _mask_bare_bsn(match: re.Match[str]) -> str:
    digits = match.group(1)
    return BSN_MASK if looks_like_bsn(digits) else digits
