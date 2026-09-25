from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.storage import ImmutableStorage, UnsupportedDocument


def test_store_pdf_uses_hash_and_immutable_non_user_path(tmp_path: Path) -> None:
    content = b"%PDF-1.4\nsynthetic fixture\n"
    stored = ImmutableStorage(Settings(storage_root=tmp_path)).store(content, "../../Laura Bianchi.pdf")
    assert stored.mime_type == "application/pdf"
    assert stored.sha256 == "0bc27e7de6ab8f9f5d794d774152b377d72cd73e42ff7af3838daab498c27a34"
    assert stored.original_filename == "Laura_Bianchi.pdf"
    assert stored.storage_key.startswith("originals/")
    assert (tmp_path / stored.storage_key).read_bytes() == content


def test_store_rejects_unrecognized_binary(tmp_path: Path) -> None:
    with pytest.raises(UnsupportedDocument, match="Only PDF"):
        ImmutableStorage(Settings(storage_root=tmp_path)).store(b"not a supported file", "document.exe")
