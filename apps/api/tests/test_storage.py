import stat
from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.storage import ImmutableStorage, UnsupportedDocument, UploadTooLarge, sniff_mime, validate_declared_request_size


def test_store_pdf_uses_hash_and_immutable_non_user_path(tmp_path: Path) -> None:
    content = b"%PDF-1.4\nsynthetic fixture\n"
    stored = ImmutableStorage(Settings(storage_root=tmp_path)).store(content, "../../Laura Bianchi.pdf")
    assert stored.mime_type == "application/pdf"
    assert stored.sha256 == "0bc27e7de6ab8f9f5d794d774152b377d72cd73e42ff7af3838daab498c27a34"
    assert stored.original_filename == "Laura_Bianchi.pdf"
    assert stored.storage_key.startswith("originals/")
    assert (tmp_path / stored.storage_key).read_bytes() == content
    assert stat.S_IMODE((tmp_path / stored.storage_key).stat().st_mode) == 0o600


def test_store_rejects_unrecognized_binary(tmp_path: Path) -> None:
    with pytest.raises(UnsupportedDocument, match="Only PDF"):
        ImmutableStorage(Settings(storage_root=tmp_path)).store(b"not a supported file", "document.exe")


@pytest.mark.parametrize(
    ("content", "mime_type"),
    [
        (b"II*\x00synthetic fixture", "image/tiff"),
        (b"\x00\x00\x00\x18ftypheicsynthetic fixture", "image/heic"),
    ],
)
def test_sniff_mime_recognizes_tiff_and_heic(content: bytes, mime_type: str) -> None:
    assert sniff_mime(content) == mime_type


def test_declared_request_size_rejects_oversized_or_invalid_values() -> None:
    with pytest.raises(UploadTooLarge, match="exceeds"):
        validate_declared_request_size("104", max_upload_bytes=100, request_overhead_bytes=3)
    with pytest.raises(UnsupportedDocument, match="invalid"):
        validate_declared_request_size("not-a-size", max_upload_bytes=100, request_overhead_bytes=3)


def test_declared_request_size_allows_unknown_or_multipart_overhead() -> None:
    validate_declared_request_size(None, max_upload_bytes=100, request_overhead_bytes=3)
    validate_declared_request_size("103", max_upload_bytes=100, request_overhead_bytes=3)
