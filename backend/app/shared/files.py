"""Content-type detection from file signatures. The declared type and file name are never trusted."""

from __future__ import annotations

import io
from dataclasses import dataclass

SNIFF_BYTES = 4096


def sniff_mime(head: bytes) -> str | None:
    """Detect the real type from magic bytes. Returns None for anything not on the allowlist below."""
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand == b"qt  ":
            return "video/quicktime"
        if brand in (b"avif", b"avis", b"heic", b"heix", b"mif1"):
            return None
        return "video/mp4"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    if head.startswith(b"wOF2"):
        return "font/woff2"
    if head.startswith(b"wOFF"):
        return "font/woff"
    if head.startswith(b"OTTO"):
        return "font/otf"
    if head.startswith(b"\x00\x01\x00\x00") or head.startswith(b"true"):
        return "font/ttf"
    return None


@dataclass
class ImageInfo:
    width: int
    height: int
    format: str


class InvalidImage(Exception):
    pass


MAX_IMAGE_PIXELS = 80_000_000  # ~ 9000 x 9000; guards against decompression bombs


def inspect_image(data: bytes) -> ImageInfo:
    """Fully decode the image (catches truncated or crafted files) and return its dimensions."""
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        with Image.open(io.BytesIO(data)) as im:
            fmt = im.format or ""
            width, height = im.size
            if width * height > MAX_IMAGE_PIXELS:
                raise InvalidImage("Image dimensions are too large")
            im.verify()
        with Image.open(io.BytesIO(data)) as im:
            im.load()
    except InvalidImage:
        raise
    except Exception as e:  # noqa: BLE001 - Pillow raises many types for bad input
        raise InvalidImage("The image could not be read; it may be corrupt") from e
    return ImageInfo(width=width, height=height, format=fmt.lower())
