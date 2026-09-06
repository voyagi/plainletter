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
