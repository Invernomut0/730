"""Deterministic local thumbnail generation for document previews."""

from __future__ import annotations

from pathlib import Path

import fitz
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

_MAX_SIZE = (360, 480)


def thumbnail_path(storage_root: Path, sha256: str) -> Path:
    """Return the non-user-controlled path for a document preview."""
    return storage_root / "thumbnails" / f"{sha256}.png"


def generate_thumbnail(source: Path, mime_type: str, destination: Path) -> Path:
    """Create a bounded PNG preview once, retaining no mutable source copy."""
    if destination.exists():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    if mime_type == "application/pdf":
        with fitz.open(source) as pdf:
            if not pdf:
                raise ValueError("Cannot create a thumbnail for an empty PDF.")
            pixmap = pdf[0].get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
            pixmap.save(destination)
        return destination
    with Image.open(source) as image:
        preview = ImageOps.exif_transpose(image).convert("RGB")
        preview.thumbnail(_MAX_SIZE)
        preview.save(destination, "PNG", optimize=True)
    return destination
