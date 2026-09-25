"""Idempotent ARQ jobs for local document processing."""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings
from arq.cron import cron
from app.adapters.lmstudio import LMStudioProvider, LLMUnavailable
from app.adapters.ocr import OCRFailed, TesseractOCRProvider
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.entities import Document, DocumentPage, DocumentState, ReviewTask, ReviewType
from app.services.extraction import (
    ExtractionFailed,
    classify_document,
    extract_pdf_text,
    extract_with_ocr,
    text_is_insufficient,
)
from app.services.eventing import cluster_document
from app.services.ingestion import archive_inbox_file, ingest_content
from app.services.storage import UnsupportedDocument
from app.services.structuring import structure_document
from app.services.thumbnails import generate_thumbnail, thumbnail_path
from app.services.watched_directory import StableFileTracker

_stable_files = StableFileTracker()


async def process_document(_context: dict[str, object], document_id: str) -> None:
    """Perform native extraction and classification; retries do not duplicate pages."""
    db = SessionLocal()
    try:
        document = db.get(Document, UUID(document_id))
        if document is None or document.state in {DocumentState.COMPLETE, DocumentState.REVIEW_REQUIRED}:
            return
        document.state = DocumentState.EXTRACTING
        db.commit()
        path = get_settings().storage_root / document.storage_key
        generate_thumbnail(path, document.mime_type, thumbnail_path(get_settings().storage_root, document.sha256))
        pages = []
        if document.mime_type == "application/pdf":
            pages = extract_pdf_text(path)
        if document.mime_type.startswith("image/") or text_is_insufficient(pages):
            document.state = DocumentState.OCR
            db.commit()
            pages = extract_with_ocr(path, document.mime_type, TesseractOCRProvider())
        for page in pages:
            db.add(DocumentPage(document_id=document.id, page_number=page.page_number, text=page.text, source="ocr" if document.state == DocumentState.OCR else "native", confidence=page.confidence))
        text = "\n".join(page.text for page in pages)
        document.state = DocumentState.CLASSIFYING
        document.document_type = classify_document(text)
        if document.document_type.value == "UNKNOWN":
            document.state = DocumentState.REVIEW_REQUIRED
            db.add(ReviewTask(type=ReviewType.DOCUMENT_TYPE_UNCERTAIN, entity_type="Document", entity_id=document.id, context={"reason": "insufficient_deterministic_signals"}))
        else:
            document.state = DocumentState.STRUCTURING
            db.commit()
            try:
                await structure_document(db, document, text, LMStudioProvider(get_settings()))
                cluster_document(
                    db,
                    document,
                    get_settings().auto_confirm_threshold,
                    get_settings().suggest_threshold,
                )
                document.state = DocumentState.COMPLETE
            except LLMUnavailable:
                document.state = DocumentState.REVIEW_REQUIRED
                db.add(ReviewTask(type=ReviewType.DOCUMENT_TYPE_UNCERTAIN, entity_type="Document", entity_id=document.id, context={"reason": "structured_extraction_unavailable_or_invalid"}))
        db.commit()
    except (ExtractionFailed, OCRFailed):
        db.rollback()
        document = db.get(Document, UUID(document_id))
        if document is not None:
            document.state = DocumentState.REVIEW_REQUIRED
            db.add(ReviewTask(type=ReviewType.DOCUMENT_TYPE_UNCERTAIN, entity_type="Document", entity_id=document.id, context={"reason": "text_extraction_failed"}))
            db.commit()
        raise
    finally:
        db.close()


async def scan_watch_directory(_context: dict[str, object]) -> None:
    """Ingest only files that remain stable across two watched-directory scans."""
    settings = get_settings()
    settings.watch_directory.mkdir(parents=True, exist_ok=True)
    for path in settings.watch_directory.iterdir():
        if not path.is_file() or not _stable_files.observe(path):
            continue
        database = SessionLocal()
        try:
            document = ingest_content(database, settings, path.read_bytes(), path.name)
            redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            await redis.enqueue_job("process_document", str(document.id))
            await redis.close()
            archive_inbox_file(path, settings.watch_directory / "processed")
        except UnsupportedDocument:
            database.rollback()
            archive_inbox_file(path, settings.storage_root / "quarantine")
        except OSError:
            database.rollback()
        finally:
            _stable_files.forget(path)
            database.close()


class WorkerSettings:
    """ARQ worker configuration; queue connectivity is configured by environment."""

    functions: ClassVar[list[object]] = [process_document, scan_watch_directory]
    cron_jobs: ClassVar[list[object]] = [cron(scan_watch_directory, second={0})]
    redis_settings: ClassVar[RedisSettings] = RedisSettings.from_dsn(get_settings().redis_url)
