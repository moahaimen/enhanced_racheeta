"""Tiny, valid, fictional files for the LOCAL demo (no third-party libraries).

* `licence_pdf(title, lines)`: a one-page PDF that says, in large letters, that it is a FICTIONAL
  demonstration document and not a real licence. No scripts, forms or attachments.
* `photo_png(rgb, accent)`: a flat illustration-style PNG (colour field with a band), so uploaded
  product photos exist without shipping any real image.
"""

from __future__ import annotations

import struct
import zlib


def licence_pdf(title: str, lines: list[str]) -> bytes:
    def esc(text: str) -> str:
        return (
            text.encode("ascii", "replace")
            .decode()
            .replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )

    rows = [("FICTIONAL DEMO DOCUMENT - NOT A REAL LICENCE", 20), (title, 16)] + [
        (line, 12) for line in lines
    ]
    y = 780
    text = ["BT"]
    for line, size in rows:
        text.append(f"/F1 {size} Tf 50 {y} Td ({esc(line)}) Tj 0 0 Td")
        text.append("ET BT")
        y -= size + 14
    text.append("ET")
    stream = "\n".join(text).encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(out)


def photo_png(rgb: tuple[int, int, int], accent: tuple[int, int, int], size=(480, 360)) -> bytes:
    width, height = size
    rows = []
    for y in range(height):
        band = height * 0.55 <= y <= height * 0.75
        colour = bytes(accent if band else rgb)
        rows.append(b"\x00" + colour * width)
    raw = b"".join(rows)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
