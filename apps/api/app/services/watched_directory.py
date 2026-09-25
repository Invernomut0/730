"""Stable-file detection for the local watched-document inbox."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class FileFingerprint:
    """Minimal metadata used to detect an unfinished file write."""

    size: int
    mtime_ns: int


@dataclass
class StableFileTracker:
    """Require two identical scans before a watched file can be ingested."""

    _observations: dict[Path, tuple[FileFingerprint, int]] = field(default_factory=dict)

    def observe(self, path: Path) -> bool:
        """Return true only after the file has remained unchanged across scans."""
        stat = path.stat()
        fingerprint = FileFingerprint(size=stat.st_size, mtime_ns=stat.st_mtime_ns)
        previous = self._observations.get(path)
        if previous and previous[0] == fingerprint:
            self._observations[path] = (fingerprint, previous[1] + 1)
            return previous[1] + 1 >= 2
        self._observations[path] = (fingerprint, 1)
        return False

    def forget(self, path: Path) -> None:
        """Discard tracking state after a file is moved or quarantined."""
        self._observations.pop(path, None)
