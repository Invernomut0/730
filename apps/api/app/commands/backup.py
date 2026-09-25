"""Local-only operational commands for encrypted backup lifecycle tasks."""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from pathlib import Path

from app.adapters.google_drive import GoogleDriveUnavailable, upload_encrypted_backup
from app.core.config import get_settings
from app.services.backup import (
    BackupError,
    create_database_dump,
    create_encrypted_backup,
    decode_backup_key,
    encrypted_backup_filename,
    verify_encrypted_backup,
)


def _key() -> bytes:
    return decode_backup_key(get_settings().backup_encryption_key)


def create_backup() -> Path:
    """Create an encrypted archive of the data volume and PostgreSQL state."""
    settings = get_settings()
    with tempfile.TemporaryDirectory() as directory:
        database_dump = Path(directory) / "database.dump"
        create_database_dump(settings.database_url, database_dump)
        return create_encrypted_backup(
            {"data": settings.storage_root, "database.dump": database_dump},
            settings.backup_root / encrypted_backup_filename(),
            _key(),
        )


def backup_main() -> int:
    try:
        print(create_backup())
        return 0
    except BackupError as error:
        print(f"Backup failed: {error}", file=sys.stderr)
        return 2


def verify_main() -> int:
    parser = argparse.ArgumentParser(description="Authenticate and inspect an encrypted HealthDocs backup.")
    parser.add_argument("backup", type=Path)
    arguments = parser.parse_args()
    try:
        print(f"Verified {len(verify_encrypted_backup(arguments.backup, _key()))} archive entries.")
        return 0
    except BackupError as error:
        print(f"Verification failed: {error}", file=sys.stderr)
        return 2


def upload_main() -> int:
    parser = argparse.ArgumentParser(description="Upload an already encrypted HealthDocs backup to Google Drive.")
    parser.add_argument("backup", type=Path)
    arguments = parser.parse_args()
    settings = get_settings()
    try:
        print(asyncio.run(upload_encrypted_backup(arguments.backup, settings.google_drive_access_token, settings.google_drive_folder_id)))
        return 0
    except (GoogleDriveUnavailable, ValueError) as error:
        print(f"Upload failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(backup_main())