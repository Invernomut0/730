import base64
from pathlib import Path

import pytest

from app.services.backup import BackupError, create_encrypted_backup, decode_backup_key, verify_encrypted_backup
from app.adapters.google_drive import upload_encrypted_backup


def test_encrypted_backup_round_trip_and_tamper_detection(tmp_path: Path) -> None:
    source = tmp_path / "data"
    source.mkdir()
    (source / "record.txt").write_text("synthetic health document metadata", encoding="utf-8")
    key = bytes(range(32))
    backup = create_encrypted_backup({"data": source}, tmp_path / "backup.hdbak", key)

    assert backup.exists()
    assert verify_encrypted_backup(backup, key) == ["data", "data/record.txt"]
    payload = bytearray(backup.read_bytes())
    payload[-1] ^= 1
    backup.write_bytes(payload)
    with pytest.raises(BackupError, match="authentication"):
        verify_encrypted_backup(backup, key)


def test_backup_key_requires_exactly_256_bits() -> None:
    assert decode_backup_key(base64.urlsafe_b64encode(bytes(range(32))).decode()) == bytes(range(32))
    with pytest.raises(BackupError, match="32 bytes"):
        decode_backup_key(base64.urlsafe_b64encode(b"short").decode())


@pytest.mark.asyncio
async def test_google_upload_refuses_non_encrypted_or_uncredentialed_input(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="encrypted backup"):
        await upload_encrypted_backup(tmp_path / "plain.tar", "")