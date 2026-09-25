"""Local OCR provider port and Tesseract implementation."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Protocol


class OCRFailed(RuntimeError):
    """Raised when the configured local OCR engine cannot extract text."""


class OCRProvider(Protocol):
    """Port for replaceable local OCR implementations."""

    def extract(self, image_path: Path) -> str: ...


class TesseractOCRProvider:
    """Run the locally installed Tesseract binary without cloud transport."""

    def extract(self, image_path: Path) -> str:
        try:
            result = subprocess.run(
                ["tesseract", str(image_path), "stdout", "-l", "ita+eng"],
                check=True,
                capture_output=True,
                text=True,
                timeout=90,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            raise OCRFailed("Local Tesseract OCR failed.") from error
        return result.stdout.strip()
