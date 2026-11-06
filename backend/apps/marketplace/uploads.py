"""Safe file uploads for seller documents and product photos.

Rules (docs/MARKETPLACE_COMMERCE.md §Uploads):
* the type is decided from the file's first bytes, never from its name or the client's header;
* only PDF, JPEG, PNG (documents) and JPEG, PNG, WebP (photos); SVG, HTML and Office files are
  refused (they can carry scripts);
* PDFs carrying active content (JavaScript, launch actions, embedded files, XFA) are refused;
* photos must have readable dimensions within bounds (a header that does not parse is refused);
* size limits; the stored name is random (`<uuid>.<ext>`); the original name is kept for display
  only, stripped of paths and control characters;
* files live under PRIVATE_MEDIA_ROOT and are streamed only by permission-checked views with
  `X-Content-Type-Options: nosniff` and a restrictive Content-Security-Policy.
"""

from __future__ import annotations

import hashlib
import re
import struct
import uuid
from dataclasses import dataclass

from django.core.files.base import ContentFile

DOCUMENT_MAX_BYTES = 5 * 1024 * 1024
IMAGE_MAX_BYTES = 3 * 1024 * 1024
IMAGE_MIN_SIDE, IMAGE_MAX_SIDE = 64, 6000

PDF_ACTIVE_MARKERS = (b"/JavaScript", b"/JS", b"/Launch", b"/EmbeddedFile", b"/RichMedia", b"/XFA")


class UploadRejected(Exception):
    code = "invalid_file"


@dataclass
class CheckedFile:
    content: ContentFile
    content_type: str
    extension: str
    size: int
    sha256: str
    original_name: str
    width: int = 0
    height: int = 0


def sniff(head: bytes) -> str | None:
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


EXTENSIONS = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def _png_size(data: bytes) -> tuple[int, int]:
    if data[12:16] != b"IHDR":
        raise UploadRejected("This PNG file is damaged.")
    return struct.unpack(">II", data[16:24])


def _jpeg_size(data: bytes) -> tuple[int, int]:
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            raise UploadRejected("This JPEG file is damaged.")
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        length = struct.unpack(">H", data[i + 2 : i + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height, width = struct.unpack(">HH", data[i + 5 : i + 9])
            return width, height
        i += 2 + length
    raise UploadRejected("This JPEG file is damaged.")


def _webp_size(data: bytes) -> tuple[int, int]:
    chunk = data[12:16]
    if chunk == b"VP8 ":
        w, h = struct.unpack("<HH", data[26:30])
        return w & 0x3FFF, h & 0x3FFF
    if chunk == b"VP8L":
        b = data[21:25]
        w = 1 + (((b[1] & 0x3F) << 8) | b[0])
        h = 1 + (((b[3] & 0x0F) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
        return w, h
    if chunk == b"VP8X":
        w = 1 + int.from_bytes(data[24:27], "little")
        h = 1 + int.from_bytes(data[27:30], "little")
        return w, h
    raise UploadRejected("This WebP file is damaged.")


def _dimensions(content_type: str, data: bytes) -> tuple[int, int]:
    try:
        if content_type == "image/png":
            return _png_size(data)
        if content_type == "image/jpeg":
            return _jpeg_size(data)
        return _webp_size(data)
    except (struct.error, IndexError) as exc:
        raise UploadRejected("This image file is damaged.") from exc


def clean_name(name: str) -> str:
    name = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[\x00-\x1f\x7f<>:\"|?*]", "", name).strip(" .")
    return name[:150] or "document"


def _read(upload, limit: int) -> bytes:
    if upload is None:
        raise UploadRejected("Choose a file.")
    if getattr(upload, "size", 0) and upload.size > limit:
        raise UploadRejected(
            f"The file is larger than {limit // (1024 * 1024)} MB.",
        )
    data = upload.read(limit + 1)
    if len(data) > limit:
        raise UploadRejected(f"The file is larger than {limit // (1024 * 1024)} MB.")
    if not data:
        raise UploadRejected("The file is empty.")
    return data


def _checked(data: bytes, content_type: str, original: str, **dims) -> CheckedFile:
    ext = EXTENSIONS[content_type]
    return CheckedFile(
        content=ContentFile(data, name=f"{uuid.uuid4().hex}.{ext}"),
        content_type=content_type,
        extension=ext,
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        original_name=clean_name(original),
        **dims,
    )


def check_document(upload) -> CheckedFile:
    data = _read(upload, DOCUMENT_MAX_BYTES)
    content_type = sniff(data[:16])
    if content_type not in ("application/pdf", "image/jpeg", "image/png"):
        raise UploadRejected("Upload a PDF, JPEG or PNG file.")
    if content_type == "application/pdf":
        if b"%%EOF" not in data[-2048:]:
            raise UploadRejected("This PDF file is incomplete or damaged.")
        if any(marker in data for marker in PDF_ACTIVE_MARKERS):
            raise UploadRejected(
                "This PDF contains scripts, attachments or interactive forms. "
                "Print it to PDF (or scan it) and upload that copy.",
            )
        return _checked(data, content_type, getattr(upload, "name", ""))
    width, height = _dimensions(content_type, data)
    return _checked(data, content_type, getattr(upload, "name", ""), width=width, height=height)


def check_image(upload) -> CheckedFile:
    data = _read(upload, IMAGE_MAX_BYTES)
    content_type = sniff(data[:16])
    if content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise UploadRejected("Upload a JPEG, PNG or WebP photo.")
    width, height = _dimensions(content_type, data)
    if not (
        IMAGE_MIN_SIDE <= width <= IMAGE_MAX_SIDE and IMAGE_MIN_SIDE <= height <= IMAGE_MAX_SIDE
    ):
        raise UploadRejected(
            f"Photos must be between {IMAGE_MIN_SIDE} and {IMAGE_MAX_SIDE} pixels on each side."
        )
    return _checked(data, content_type, getattr(upload, "name", ""), width=width, height=height)


def stream(file_field, content_type: str, *, download_name: str | None = None):
    """A FileResponse that browsers will never sniff into something executable."""
    from django.http import FileResponse

    response = FileResponse(file_field.open("rb"), content_type=content_type)
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    response["Cache-Control"] = "private, max-age=300"
    if download_name:
        safe = clean_name(download_name).encode("ascii", "ignore").decode() or "document"
        response["Content-Disposition"] = f'attachment; filename="{safe}"'
    else:
        response["Content-Disposition"] = "inline"
    return response
