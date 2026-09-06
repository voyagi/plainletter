"""What happens to a .txt upload that is not text.

`_from_text` falls back to Windows-1252 when a file is not UTF-8, and the comment beside that
fallback said every byte is valid in it, so it could not fail again. Five byte values are
undefined in Python's cp1252 codec, and a file carrying one raised a raw codec error that reached
the volunteer with a byte offset in it, filed as a payload problem rather than an upload one.
"""

from __future__ import annotations

import base64

import pytest

from plainletter import intake
from plainletter.app import read_letter


def _decodes(data: bytes) -> bool:
    try:
        data.decode("cp1252")
    except UnicodeDecodeError:
        return False
    return True


def test_the_windows_1252_codec_really_does_refuse_some_bytes() -> None:
    # The premise of the whole file. If this ever becomes empty the fallback is total after all
    # and the guard below is dead code that should go.
    refused = [byte for byte in range(256) if not _decodes(bytes([byte]))]
    assert refused == [0x81, 0x8D, 0x8F, 0x90, 0x9D]


@pytest.mark.parametrize("byte", [0x81, 0x8D, 0x8F, 0x90, 0x9D])
def test_a_txt_that_is_not_text_is_refused_with_a_line_a_volunteer_can_act_on(byte: int) -> None:
    data = b"Beste mevrouw" + bytes([byte]) + b" Jansen"
    with pytest.raises(intake.IntakeError) as refused:
        intake.from_bytes(data, filename="brief.txt")
    assert "not readable as text" in str(refused.value)


def test_binary_that_happens_to_decode_is_still_not_a_letter() -> None:
    # Decoding is not the same as being text. Windows-1252 maps almost every byte to something
    # printable, so a file that merely avoids the five undefined ones came through as a letter
    # and went to the model. Measured: 148 of 500 random 64-byte blobs decode without complaint.
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (60, 60), "white").save(buffer, format="PNG")

    for label, data in (
        ("a null in the middle", b"Beste mevrouw\x00 Jansen, dit is een brief."),
        ("a png renamed to .txt", buffer.getvalue()),
        ("control characters only", bytes(range(1, 9)) * 8),
    ):
        with pytest.raises(intake.IntakeError) as refused:
            intake.from_bytes(data, filename="brief.txt")
        assert "not readable as text" in str(refused.value), label

    # And it is not just those three. These blobs deliberately AVOID the five undefined bytes, so
    # every one of them decodes without complaint and can only be caught by the control-character
    # rule. That is the half the decoder cannot do.
    usable = [byte for byte in range(256) if byte not in {0x81, 0x8D, 0x8F, 0x90, 0x9D}]
    checked = 0
    for offset in range(0, len(usable), 4):
        blob = bytes(usable[(offset + step) % len(usable)] for step in range(64))
        assert _decodes(blob), "this blob is meant to decode, or it tests the wrong half"
        if not any(intake._is_control(char) for char in blob.decode("cp1252")):
            # A window of purely printable bytes IS text, as far as anything at this layer can
            # tell. Skipped rather than asserted either way, and named below so the limit of this
            # rule is on the record instead of implied.
            continue
        checked += 1
        with pytest.raises(intake.IntakeError):
            intake.from_bytes(blob, filename="brief.txt")
    assert checked > 20, "the sweep has to actually exercise the rule, not skip past it"


def test_the_control_character_rule_cannot_see_an_all_printable_file_and_says_so() -> None:
    # Written down rather than left implied. A file made only of printable bytes is text by every
    # test available here, so this rule does not claim to be a binary detector. What it catches is
    # binary that carries control bytes, which real formats overwhelmingly do: the PNG above came
    # through as 175 characters carrying 58 of them.
    printable = bytes(range(0x20, 0x60))
    letter = intake.from_bytes(printable, filename="brief.txt")
    assert letter.text is not None


def test_control_no_sample_letter_carries_a_disallowed_control_character() -> None:
    # The rule is only safe because a real letter has none. If a sample ever grows one, this says
    # so here rather than by refusing that letter at a desk.
    from plainletter.demo import sample_names, sample_text

    for name in sample_names():
        offenders = [char for char in sample_text(name) if intake._is_control(char)]
        assert offenders == [], f"{name} carries {offenders!r}"


def test_control_windows_1252_text_is_still_read() -> None:
    # The fallback exists because Dutch office software writes this, so the guard must not take
    # it away. Accented characters that are not valid UTF-8 on their own.
    dutch = "Beste mevrouw Jansen, \xe9\xe8\xfc".encode("cp1252")
    letter = intake.from_bytes(dutch, filename="brief.txt")
    assert letter.text is not None
    assert "Jansen" in letter.text


def test_control_utf_8_text_never_reaches_the_fallback() -> None:
    letter = intake.from_bytes("Beste mevrouw, € 174,00".encode(), filename="brief.txt")
    assert letter.text is not None
    assert "€ 174,00" in letter.text


def test_a_photograph_renamed_to_txt_is_an_upload_problem_not_a_payload_one() -> None:
    # This is how it arrives in practice: not a hand-made byte, a picture with a .txt name. The
    # answer used to be `payload` carrying a raw codec message with a byte offset in it.
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (60, 60), "white").save(buffer, format="JPEG")
    encoded = base64.b64encode(buffer.getvalue()).decode()

    answer = read_letter({"letter": {"filename": "letter.txt", "content_base64": encoded}})
    assert isinstance(answer, dict)
    assert answer["error"]["kind"] == "upload"
    assert "codec" not in answer["error"]["detail"]
    assert "not readable as text" in answer["error"]["detail"]
