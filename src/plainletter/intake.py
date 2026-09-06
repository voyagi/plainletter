"""What the visitor hands over, turned into something the model can read.

A phone photograph arrives sideways, far bigger than any model will look at, and carrying the
coordinates of the house it was taken in. A PDF arrives as a page description rather than a picture.
Both have to become Bedrock content blocks that fit the Converse limits, and nothing may touch the
disk on the way.

Two decisions here are load bearing:

* A born-digital PDF carries its own text layer, so the grounding check downstream can run against
  the document itself instead of against something a model said about it. Only a scan or a
  photograph needs a transcription turn at all.
* Every image is re-encoded rather than passed through. That is what drops the EXIF block, and with
  it the location the photograph was taken.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Literal

import pypdfium2
from PIL import Image, ImageOps, UnidentifiedImageError
from strands.types.content import ContentBlock
from strands.types.media import ImageFormat

# Amazon Bedrock's Converse API takes at most 20 images in one request, each no larger than 3.75 MB
# and 8000 px per side:
# https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html
MAX_IMAGES_PER_REQUEST = 20
MAX_IMAGE_BYTES = 3_750_000

# The reading model downscales anything with a longer edge than this before it looks at it, so a
# bigger upload costs upload time and buys no legibility:
# https://platform.claude.com/docs/en/build-with-claude/vision
MAX_LONG_EDGE_PX = 1568

# 72 dpi is scale 1 in PDFium. A4 at scale 1.86 lands on the long edge above; the ceiling only
# matters for a page small enough that hitting the target would mean rendering it at 300 dpi plus.
MAX_RENDER_SCALE = 4.0

# Below this the text layer is a header or a watermark rather than the letter, and the pages need
# transcribing. A real letter page carries well over a thousand characters.
MIN_TEXT_LAYER_CHARS = 200

JPEG_QUALITY_LADDER = (90, 80, 70)

TEXT_SUFFIXES = frozenset({".txt", ".md"})
PDF_MAGIC = b"%PDF-"

SourceKind = Literal["image", "pdf", "text"]


class IntakeError(ValueError):
    """The upload could not be turned into pages, with a line the volunteer can act on."""


@dataclass(frozen=True)
class LetterInput:
    """One letter ready for the model, plus whatever the file itself could tell us.

    `text` is set only when the letter's own words are available without asking a model: a text
    upload, or a PDF with a usable text layer. When it is None the pipeline has to transcribe the
    pages before it can check anything against them.
    """

    blocks: tuple[ContentBlock, ...]
    kind: SourceKind
    pages: int
    text: str | None = None
    pages_omitted: int = 0


def from_path(path: Path) -> LetterInput:
    try:
        data = path.read_bytes()
    except OSError as error:
        raise IntakeError(f"{path} could not be opened: {error}") from error
    return from_bytes(data, filename=path.name)


def from_bytes(data: bytes, *, filename: str) -> LetterInput:
    """Read an upload by what it actually is, falling back to the name only for plain text.

    The name is the weakest signal at a help desk, where files arrive as `scan0001` and
    `IMG_4471.jpg` in whatever the visitor's phone decided to call them.
    """
    if not data:
        raise IntakeError(f"{filename} is empty. Take the photograph again or pick another file.")
    if data.startswith(PDF_MAGIC):
        return _from_pdf(data)
    if Path(filename).suffix.lower() in TEXT_SUFFIXES:
        return _from_text(data)
    return _from_image(data, filename)


def from_text(text: str) -> LetterInput:
    """A letter whose words are already in hand, which is what the sample letters are."""
    if not text.strip():
        raise IntakeError("that file holds no text")
    return LetterInput(blocks=({"text": text},), kind="text", pages=1, text=text)


def _from_text(data: bytes) -> LetterInput:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        # Dutch office software still writes Windows-1252, and every byte is valid in it, so this
        # cannot fail again.
        text = data.decode("cp1252")
    return from_text(text)


def _from_pdf(data: bytes) -> LetterInput:
    try:
        document = pypdfium2.PdfDocument(data)
        page_count = len(document)
    except pypdfium2.PdfiumError as error:
        raise IntakeError(
            f"this PDF could not be opened ({error}). If it asks for a password, open it, "
            "save a copy without one, and upload that."
        ) from error

    texts: list[str] = []
    blocks: list[ContentBlock] = []
    shown = min(page_count, MAX_IMAGES_PER_REQUEST)
    try:
        for index in range(page_count):
            page = document[index]
            textpage = page.get_textpage()
            texts.append(textpage.get_text_bounded())
            textpage.close()
            if index < shown:
                blocks += _page_blocks(index + 1, shown, _render(page), prefer_lossless=True)
            page.close()
    finally:
        document.close()

    text = "\n\n".join(texts).strip()
    usable = len(text) >= MIN_TEXT_LAYER_CHARS
    if usable:
        blocks.append({"text": f"The text layer of the same PDF, as the file stores it:\n{text}"})

    return LetterInput(
        blocks=tuple(blocks),
        kind="pdf",
        pages=page_count,
        text=text if usable else None,
        pages_omitted=page_count - shown,
    )


def _from_image(data: bytes, filename: str) -> LetterInput:
    try:
        with Image.open(BytesIO(data)) as opened:
            opened.load()
            source_format = opened.format
            image = _upright(opened)
    except UnidentifiedImageError as error:
        raise IntakeError(
            f"{filename} is not a picture this can read. An iPhone saves photos as HEIC by "
            "default, which no model reads: in the Photos app choose Share, then Options, then "
            "Most Compatible, and send the JPEG."
        ) from error
    except Image.DecompressionBombError as error:
        raise IntakeError(
            f"{filename} claims more pixels than any letter has. Photograph the page again."
        ) from error
    except OSError as error:
        # A half-transferred photograph is the ordinary case here, not an exotic one: a phone on
        # a library's wifi drops an upload mid-file and the bytes decode as a valid JPEG header
        # over a truncated body. Pillow raises a plain OSError for that, which is neither of the
        # two above, so before this it left the entrypoint as an unhandled failure and the desk
        # saw a server error instead of a line telling the volunteer to take the photo again.
        raise IntakeError(
            f"{filename} stops partway through, so the page is incomplete. Take the photograph "
            "again and upload the whole file."
        ) from error

    blocks = _page_blocks(1, 1, image, prefer_lossless=source_format != "JPEG")
    return LetterInput(blocks=tuple(blocks), kind="image", pages=1)


def _upright(image: Image.Image) -> Image.Image:
    """Apply the EXIF orientation a phone records instead of rotating the pixels it stores."""
    rotated = ImageOps.exif_transpose(image)
    return rotated if rotated is not None else image.copy()


def _render(page: Any) -> Image.Image:
    width, height = page.get_size()
    if not width or not height:
        raise IntakeError("this PDF has a page with no size, so it cannot be drawn")
    scale = min(MAX_LONG_EDGE_PX / max(width, height), MAX_RENDER_SCALE)
    rendered: Image.Image = page.render(scale=scale).to_pil()
    return rendered


def _page_blocks(
    number: int, total: int, image: Image.Image, *, prefer_lossless: bool
) -> list[ContentBlock]:
    """One page: the label first, then the picture, which is the order the model reads best in."""
    image_format, data = _encode(image, prefer_lossless=prefer_lossless)
    label = f"Page {number} of {total}:" if total > 1 else "The letter:"
    return [{"text": label}, {"image": {"format": image_format, "source": {"bytes": data}}}]


def _encode(image: Image.Image, *, prefer_lossless: bool) -> tuple[ImageFormat, bytes]:
    prepared = _fit(_flatten(image))
    if prefer_lossless:
        lossless = _save(prepared, "PNG", optimize=True)
        if len(lossless) <= MAX_IMAGE_BYTES:
            return "png", lossless

    encoded = b""
    for quality in JPEG_QUALITY_LADDER:
        encoded = _save(prepared, "JPEG", quality=quality, optimize=True)
        if len(encoded) <= MAX_IMAGE_BYTES:
            return "jpeg", encoded
    raise IntakeError(
        f"a page is still {len(encoded)} bytes at the lowest quality worth reading, over the "
        f"{MAX_IMAGE_BYTES} the model accepts. Photograph the page on its own."
    )


def _fit(image: Image.Image) -> Image.Image:
    long_edge = max(image.size)
    if long_edge <= MAX_LONG_EDGE_PX:
        return image
    ratio = MAX_LONG_EDGE_PX / long_edge
    size = (max(1, round(image.width * ratio)), max(1, round(image.height * ratio)))
    return image.resize(size, Image.Resampling.LANCZOS)


def _flatten(image: Image.Image) -> Image.Image:
    if image.mode in {"RGB", "L"}:
        return image
    if image.mode == "P" or "A" in image.mode:
        # Dropping the alpha channel turns a transparent scan black. The paper was white.
        with_alpha = image.convert("RGBA")
        canvas = Image.new("RGB", with_alpha.size, "white")
        canvas.paste(with_alpha, mask=with_alpha.getchannel("A"))
        return canvas
    return image.convert("RGB")


def _save(image: Image.Image, image_format: str, **options: Any) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format=image_format, **options)
    return buffer.getvalue()
