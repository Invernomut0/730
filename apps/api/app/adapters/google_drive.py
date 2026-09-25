"""Google Drive upload for already encrypted backup artifacts only."""

from __future__ import annotations

from pathlib import Path

import httpx


class GoogleDriveUnavailable(RuntimeError):
    """Raised when the Google Drive resumable upload cannot complete."""


async def upload_encrypted_backup(path: Path, access_token: str, folder_id: str = "") -> str:
    """Upload one local `.hdbak` file through a resumable Google Drive session."""
    if path.suffix != ".hdbak" or not path.is_file() or not access_token:
        raise ValueError("A local encrypted backup and Google access token are required.")
    metadata: dict[str, object] = {"name": path.name, "mimeType": "application/octet-stream"}
    if folder_id:
        metadata["parents"] = [folder_id]
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Upload-Content-Type": "application/octet-stream",
        "X-Upload-Content-Length": str(path.stat().st_size),
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            session = await client.post(
                "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable",
                json=metadata,
                headers=headers,
            )
            session.raise_for_status()
            location = session.headers["Location"]
            with path.open("rb") as source:
                uploaded = await client.put(location, content=source, headers={"Content-Type": "application/octet-stream"})
            uploaded.raise_for_status()
            file_id = uploaded.json()["id"]
        return str(file_id)
    except (httpx.HTTPError, KeyError, OSError, ValueError) as error:
        raise GoogleDriveUnavailable("Encrypted backup upload failed.") from error