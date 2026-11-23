"""Which files each asset kind accepts. The detected (magic-byte) type must be on the kind's allowlist.

SVG is deliberately not accepted: it can carry scripts. Upload a PNG or WebP logo instead.
"""

from __future__ import annotations

from dataclasses import dataclass

MB = 1024 * 1024


@dataclass(frozen=True)
class KindRule:
    mime_types: dict[str, tuple[str, ...]]  # canonical MIME -> accepted file extensions
    max_bytes: int
    decode_image: bool = False
    hash_content: bool = True

    @property
    def extensions(self) -> dict[str, str]:
        return {ext: mime for mime, exts in self.mime_types.items() for ext in exts}


_IMAGES = {"image/png": ("png",), "image/jpeg": ("jpg", "jpeg"), "image/webp": ("webp",)}

RULES: dict[str, KindRule] = {
    "logo": KindRule(_IMAGES, 5 * MB, decode_image=True),
    "image": KindRule({**_IMAGES, "image/gif": ("gif",)}, 20 * MB, decode_image=True),
    "video": KindRule({"video/mp4": ("mp4", "m4v"), "video/quicktime": ("mov",), "video/webm": ("webm",)},
                      500 * MB, hash_content=False),
    "document": KindRule({"application/pdf": ("pdf",)}, 25 * MB),
    "font": KindRule({"font/woff2": ("woff2",), "font/woff": ("woff",), "font/ttf": ("ttf",), "font/otf": ("otf",)},
                     5 * MB),
}

INLINE_PREFIXES = ("image/", "video/")


def canonical_type(kind: str, filename: str) -> str | None:
    """The Content-Type to sign into the upload policy, from the file extension; None when not allowed.

    The browser-declared type is recorded but not trusted; the stored file is verified by magic bytes on completion.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return RULES[kind].extensions.get(ext)
