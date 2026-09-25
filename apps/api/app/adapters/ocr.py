"""Local OCR provider port and Tesseract implementation."""

from __future__ import annotations

import subprocess
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PIL import Image

class OCRFailed(RuntimeError):
    """Raised when the configured local OCR engine cannot extract text."""


@dataclass(frozen=True)
class OCRResult:
    text: str
    blocks: dict[str, object]


class OCRProvider(Protocol):
    """Port for replaceable local OCR implementations."""

    def extract(self, image_path: Path) -> str: ...


class TesseractOCRProvider:
    """Run the locally installed Tesseract binary without cloud transport."""

    def extract(self, image_path: Path) -> str:
        return self.extract_with_boxes(image_path).text

    def extract_with_boxes(self, image_path: Path) -> OCRResult:
        """Return OCR text plus word-level pixel boxes from Tesseract TSV output."""
        try:
            result = subprocess.run(
                ["tesseract", str(image_path), "stdout", "-l", "ita+eng", "tsv"],
                check=True,
                capture_output=True,
                text=True,
                timeout=90,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            raise OCRFailed("Local Tesseract OCR failed.") from error
        with Image.open(image_path) as image:
            image_width, image_height = image.size
        rows = csv.DictReader(result.stdout.splitlines(), delimiter="\t")
        words = [
            {
                "text": row["text"].strip(),
                "left": int(row["left"]) / image_width,
                "top": int(row["top"]) / image_height,
                "width": int(row["width"]) / image_width,
                "height": int(row["height"]) / image_height,
                "confidence": float(row["conf"]),
            }
            for row in rows
            if row.get("text", "").strip() and row.get("conf", "-1") != "-1"
        ]
        return OCRResult(
            text=" ".join(str(word["text"]) for word in words),
            blocks={"coordinate_space": "normalized", "words": words},
        )
