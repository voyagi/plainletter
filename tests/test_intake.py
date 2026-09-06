from datetime import date
from io import BytesIO

import pytest
from PIL import Image

from plainletter import intake
from plainletter.demo import sample_text, scripted_model
from plainletter.intake import (
    MAX_IMAGE_BYTES,
    MAX_IMAGES_PER_REQUEST,
    MAX_LONG_EDGE_PX,
    IntakeError,
)
from plainletter.pipeline import Pipeline

SAMPLE = "cjib-verkeersboete"


def born_digital_pdf(pages: list[list[str]]) -> bytes:
    """A PDF with a real text layer, written out by hand.

    Pillow can only put a picture into a PDF and pypdfium2 only reads them, so the one fixture that
    proves the text-layer path has to be assembled here. It is the plain five-object structure from
    the PDF specification with a correct cross-reference table.
    """
    objects: list[bytes] = []
    page_ids = [3 + index * 2 for index in range(len(pages))]
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)

    objects.append(b"<</Type/Catalog/Pages 2 0 R>>")
    objects.append(f"<</Type/Pages/Kids[{kids}]/Count {len(pages)}>>".encode("latin-1"))
    for page_id, lines in zip(page_ids, pages, strict=True):
        stream = _text_stream(lines)
        objects.append(
            (
                f"<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]"
                f"/Resources<</Font<</F1 {len(pages) * 2 + 3} 0 R>>>>"
                f"/Contents {page_id + 1} 0 R>>"
            ).encode("latin-1")
        )
        header = f"<</Length {len(stream)}>>stream\n".encode("latin-1")
        objects.append(header + stream + b"\nendstream")
    objects.append(b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>")

    body = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, payload in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{number} 0 obj".encode("latin-1") + payload + b"endobj\n"

    start = len(body)
    body += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("latin-1")
    for offset in offsets:
        body += f"{offset:010d} 00000 n \n".encode("latin-1")
    body += f"trailer<</Size {len(objects) + 1}/Root 1 0 R>>\nstartxref\n{start}\n%%EOF\n".encode(
        "latin-1"
    )
    return bytes(body)


def _text_stream(lines: list[str]) -> bytes:
    drawn = "".join(f"({_escape(line)}) Tj T*\n" for line in lines)
    return f"BT\n/F1 11 Tf\n50 780 Td\n14 TL\n{drawn}ET".encode("latin-1")


def _escape(line: str) -> str:
    safe = line.encode("latin-1", errors="replace").decode("latin-1")
    return safe.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def scanned_pdf(pages: int, size: tuple[int, int] = (600, 850)) -> bytes:
    sheets = [Image.new("RGB", size, "white") for _ in range(pages)]
    buffer = BytesIO()
    sheets[0].save(buffer, format="PDF", save_all=True, append_images=sheets[1:])
    return buffer.getvalue()


def photograph(size: tuple[int, int], *, orientation: int | None = None) -> bytes:
    image = Image.new("RGB", size, "white")
    # Straight noise rather than flat colour: a flat image compresses to almost nothing, which
    # would make the byte-budget assertions pass for the wrong reason.
    image.putdata(
        [(step * 7 % 256, step * 13 % 256, step * 29 % 256) for step in range(size[0] * size[1])]
    )
    buffer = BytesIO()
    if orientation is None:
        image.save(buffer, format="JPEG", quality=95)
    else:
        exif = Image.Exif()
        exif[0x0112] = orientation
        image.save(buffer, format="JPEG", quality=95, exif=exif)
    return buffer.getvalue()


def image_blocks(letter: intake.LetterInput) -> list[dict]:
    return [block["image"] for block in letter.blocks if "image" in block]


def decode(block: dict) -> Image.Image:
    return Image.open(BytesIO(block["source"]["bytes"]))


def test_a_text_file_needs_no_model_to_produce_the_letters_own_words() -> None:
    letter = intake.from_bytes(sample_text(SAMPLE).encode("utf-8"), filename="brief.txt")
    assert letter.kind == "text"
    assert letter.text is not None
    assert "Beschikkingsnummer: 8194 5523 7761" in letter.text


def test_a_letter_saved_in_windows_encoding_still_reads() -> None:
    saved = "Bedrag: 174 euro\nBijlage: caf\xe9".encode("cp1252")
    letter = intake.from_bytes(saved, filename="a.txt")
    assert letter.text is not None
    assert "caf\xe9" in letter.text


def test_a_born_digital_pdf_carries_its_own_text_and_a_picture_of_each_page() -> None:
    lines = [
        "Centraal Justitieel Incassobureau",
        "Beschikkingsnummer: 8194 5523 7761",
        "Totaal te betalen: EUR 174,00",
        "Betaal voor 15 september 2026.",
        "Betaalt u niet op tijd, dan wordt het bedrag verhoogd met 50 procent.",
        "Bent u het niet eens met deze beschikking? U kunt beroep instellen.",
        "Dit is een verzonnen voorbeeldbrief en de nummers bestaan niet.",
    ]
    letter = intake.from_bytes(born_digital_pdf([lines]), filename="brief.pdf")

    assert letter.kind == "pdf"
    assert letter.pages == 1
    assert letter.text is not None
    assert "Beschikkingsnummer: 8194 5523 7761" in letter.text
    assert len(image_blocks(letter)) == 1


def test_a_pdf_that_is_only_a_scan_has_nothing_to_check_against_yet() -> None:
    letter = intake.from_bytes(scanned_pdf(2), filename="scan.pdf")
    assert letter.kind == "pdf"
    assert letter.pages == 2
    assert letter.text is None
    assert len(image_blocks(letter)) == 2
    assert [block["text"] for block in letter.blocks if "text" in block] == [
        "Page 1 of 2:",
        "Page 2 of 2:",
    ]


def test_a_pdf_longer_than_the_model_accepts_says_what_it_left_out() -> None:
    pages = MAX_IMAGES_PER_REQUEST + 2
    letter = intake.from_bytes(scanned_pdf(pages), filename="dossier.pdf")
    assert letter.pages == pages
    assert len(image_blocks(letter)) == MAX_IMAGES_PER_REQUEST
    assert letter.pages_omitted == 2


def test_a_photograph_is_turned_the_way_the_phone_was_held() -> None:
    # Orientation 6 is the tag a phone writes when it stored a portrait photo as landscape pixels.
    letter = intake.from_bytes(photograph((400, 300), orientation=6), filename="IMG_4471.jpg")
    assert letter.kind == "image"
    assert decode(image_blocks(letter)[0]).size == (300, 400)


def test_the_photographs_metadata_does_not_travel_with_it() -> None:
    letter = intake.from_bytes(photograph((400, 300), orientation=6), filename="IMG_4471.jpg")
    assert dict(decode(image_blocks(letter)[0]).getexif()) == {}


def test_a_full_resolution_phone_photo_is_cut_to_what_the_model_reads() -> None:
    letter = intake.from_bytes(photograph((4032, 3024)), filename="IMG_0001.jpg")
    block = image_blocks(letter)[0]
    assert max(decode(block).size) == MAX_LONG_EDGE_PX
    assert len(block["source"]["bytes"]) <= MAX_IMAGE_BYTES


def test_a_screenshot_keeps_its_lossless_encoding() -> None:
    buffer = BytesIO()
    Image.new("RGBA", (500, 700), (255, 255, 255, 0)).save(buffer, format="PNG")
    letter = intake.from_bytes(buffer.getvalue(), filename="screenshot.png")
    assert image_blocks(letter)[0]["format"] == "png"
    assert decode(image_blocks(letter)[0]).mode == "RGB"


def test_a_file_no_model_can_look_at_says_what_to_do_about_it() -> None:
    with pytest.raises(IntakeError) as refused:
        intake.from_bytes(b"ftypheic not really an image", filename="IMG_0002.heic")
    assert "HEIC" in str(refused.value)


def test_an_empty_upload_is_refused_before_anything_else_happens() -> None:
    with pytest.raises(IntakeError):
        intake.from_bytes(b"", filename="IMG_0003.jpg")


def test_a_letter_that_arrived_as_a_picture_still_reaches_the_desk() -> None:
    # The whole point of intake: a photographed letter, transcribed by one turn, extracted by
    # another, and checked against the transcript before anything is printed.
    letter = intake.from_bytes(scanned_pdf(1), filename="scan.pdf")
    reading = Pipeline(model=scripted_model(SAMPLE)).run(
        letter, visitor_language="uk", today=date(2026, 8, 21)
    )
    assert letter.text is None
    assert reading.deadline is not None
    assert reading.deadline.on == date(2026, 9, 15)
    assert reading.verification.is_grounded


def test_a_photograph_that_stops_partway_is_answered_and_not_raised_at_the_desk() -> None:
    # A phone on a library wifi drops an upload mid-file. Pillow raises a plain OSError for that,
    # which is neither of the two the reader used to catch, so it left the entrypoint unhandled
    # and the desk saw a server error instead of a line telling the volunteer what to do.
    whole = photograph((900, 1200))
    with pytest.raises(IntakeError) as refused:
        intake.from_bytes(whole[: len(whole) // 2], filename="IMG_0004.jpg")
    assert "again" in str(refused.value)

    # The control: the same photograph, whole, still reads.
    assert intake.from_bytes(whole, filename="IMG_0004.jpg").kind == "image"


# ---------------------------------------------------------------------------------------------
# The swept property.
#
# app.py's docstring promises that an upload which is not a letter is answered rather than
# forwarded, and that a failure is reported by its type. A truncated photograph broke that promise
# and left the entrypoint as a raw OSError, which is what a phone dropping an upload on a library
# wifi produces. So rather than adding that one shape, this sweeps the shapes a desk really sees.
# ---------------------------------------------------------------------------------------------


def a_png(size: tuple[int, int] = (60, 60)) -> bytes:
    buffer = BytesIO()
    Image.new("RGBA", size, (255, 0, 0, 128)).save(buffer, format="PNG")
    return buffer.getvalue()


def broken_uploads() -> dict[str, tuple[str, bytes]]:
    jpeg = photograph((400, 600))
    pdf = scanned_pdf(1)
    return {
        # The two controls: whole files, which must still be read.
        "a whole photograph": ("letter.jpg", jpeg),
        "a whole pdf": ("letter.pdf", pdf),
        # A phone that lost the connection halfway through the upload.
        "a photograph cut in half": ("letter.jpg", jpeg[: len(jpeg) // 2]),
        "a photograph cut to its header": ("letter.jpg", jpeg[:200]),
        "a pdf cut in half": ("letter.pdf", pdf[: len(pdf) // 2]),
        "a pdf header and nothing else": ("letter.pdf", b"%PDF-1.4\n"),
        "a pdf header over rubbish": ("letter.pdf", b"%PDF-1.4\n" + b"\x00\x01\x02" * 400),
        # Files that are not what their name says.
        "a zip wearing a jpg name": ("letter.jpg", b"PK\x03\x04" + b"\x00" * 500),
        "an iphone heic": ("IMG_0001.heic", b"\x00\x00\x00\x18ftypheic" + b"\x00" * 300),
        "a photograph renamed to txt": ("letter.txt", jpeg),
        "a png with transparency": ("letter.png", a_png()),
        # Text that is not what a Dutch desk expects.
        "utf-16 text": ("letter.txt", "Beste meneer".encode("utf-16")),
        "a null byte inside text": ("letter.txt", b"Beste\x00 mevrouw"),
        # The edges.
        "one byte": ("letter.jpg", b"\xff"),
        "nothing at all": ("letter.jpg", b""),
        "no extension on the name": ("scan0001", jpeg),
    }


def test_no_upload_a_desk_can_receive_leaves_the_reader_as_a_raw_exception() -> None:
    # `_prepare` catches IntakeError and ValueError. Anything else escapes the entrypoint and the
    # desk sees a server error instead of a line the volunteer can act on.
    for label, (filename, data) in broken_uploads().items():
        try:
            intake.from_bytes(data, filename=filename)
        except intake.IntakeError:
            continue
        except Exception as escaped:
            raise AssertionError(f"{label}: {type(escaped).__name__}: {escaped}") from escaped


def test_every_refusal_says_something_a_volunteer_can_act_on() -> None:
    refused = 0
    for label, (filename, data) in broken_uploads().items():
        try:
            intake.from_bytes(data, filename=filename)
        except intake.IntakeError as answer:
            refused += 1
            said = str(answer)
            assert said, f"{label}: refused with an empty reason"
            # Not a stack trace, not a codec's own words, not a byte offset into somebody's file.
            assert "Traceback" not in said, f"{label}: {said}"
            assert "codec" not in said, f"{label}: {said}"
    # The control. A sweep where nothing is refused would pass whatever the reader did, and two of
    # these files are whole ones that must still be read.
    assert refused >= len(broken_uploads()) - 4, f"only {refused} of the shapes were refused"


def test_the_upload_sweep_still_reads_the_files_that_are_whole() -> None:
    # The other half of the control. A reader that refused everything would satisfy the two tests
    # above and be useless.
    whole = broken_uploads()
    for label, expected in (("a whole photograph", "image"), ("a whole pdf", "pdf")):
        filename, data = whole[label]
        assert intake.from_bytes(data, filename=filename).kind == expected, label
