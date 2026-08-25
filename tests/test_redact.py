from plainletter.locales.nl import BSN_MASK, looks_like_bsn
from plainletter.redact import is_valid_iban, redact


def test_the_elfproef_accepts_a_real_bsn_shape() -> None:
    # 111222333: 1*9 + 1*8 + 1*7 + 2*6 + 2*5 + 2*4 + 3*3 + 3*2 + 3*-1 = 66, divisible by eleven.
    assert looks_like_bsn("111222333")


def test_the_elfproef_rejects_a_number_that_only_looks_like_one() -> None:
    assert not looks_like_bsn("123456789")
    assert not looks_like_bsn("1112223")


def test_a_labelled_number_is_masked_whatever_its_checksum() -> None:
    masked = redact("BSN: 123456789 staat op deze brief")
    assert "123456789" not in masked
    assert BSN_MASK in masked


def test_a_bare_number_passing_the_elfproef_is_masked() -> None:
    assert "111222333" not in redact("nummer 111222333")


def test_a_reference_number_that_fails_the_check_is_left_alone() -> None:
    # The visitor has to quote this to pay. Masking it would break the one step that matters.
    assert "8194 5523 7761" in redact("Beschikkingsnummer: 8194 5523 7761")


def test_an_iban_is_masked_down_to_its_last_four() -> None:
    masked = redact("Maak over naar NL91ABNA0417164300 voor 15 september.")
    assert "NL91ABNA0417164300" not in masked
    assert "4300" in masked


def test_something_iban_shaped_that_fails_mod_97_is_left_alone() -> None:
    assert not is_valid_iban("NL00ABNA0417164300")
    assert "NL00ABNA0417164300" in redact("kenmerk NL00ABNA0417164300")
