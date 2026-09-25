from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import delete, select

from app.adapters.rizzo import RizzoFlowUnavailable
from app.db.session import SessionLocal
from app.models.entities import AIExecution
from app.services.decisions import TypedDecisionRequest, decide_batch


class ClassificationDecision(BaseModel):
    """Representative non-clinical decision payload returned by local AI."""

    document_type: str
    confidence: float


class AvailableRizzo:
    """Local deterministic Rizzo implementation for contract-level testing."""

    model_id = "rizzo-flow"

    async def decide_batch(self, decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        assert decisions[0]["task"] == "document_classification"
        return [{"document_type": "INVOICE", "confidence": 0.98}]


class UnavailableRizzo:
    """Local Rizzo endpoint unavailable during a valid fallback scenario."""

    model_id = "rizzo-flow"

    async def decide_batch(self, _decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        raise RizzoFlowUnavailable("Service unavailable")


class LocalFallback:
    """Deterministic local model used to validate the fallback contract."""

    model_id = "local-fallback"

    async def models(self) -> list[str]:
        return [self.model_id]

    async def structured_completion(self, _prompt: str, _schema: dict[str, Any]) -> dict[str, Any]:
        return {"document_type": "UNKNOWN", "confidence": 0.0}


def _request() -> TypedDecisionRequest:
    return TypedDecisionRequest(
        task="document_classification",
        input_text="Ricevuta 2026-03-05: importo 180,00 EUR",
        output_schema=ClassificationDecision,
        prompt_name="document-classifier",
    )


@pytest.mark.asyncio
async def test_rizzo_batch_persists_successful_provenance() -> None:
    database = SessionLocal()
    try:
        result = await decide_batch(database, [_request()], AvailableRizzo(), LocalFallback())
        execution = database.scalar(
            select(AIExecution).where(AIExecution.provider == "rizzo-flow").order_by(AIExecution.created_at.desc())
        )
        assert result == [ClassificationDecision(document_type="INVOICE", confidence=0.98)]
        assert execution is not None
        assert execution.status == "SUCCEEDED"
        assert execution.model == "rizzo-flow"
    finally:
        database.execute(delete(AIExecution).where(AIExecution.prompt_name == "document-classifier"))
        database.commit()
        database.close()


@pytest.mark.asyncio
async def test_failed_rizzo_records_failure_before_local_fallback() -> None:
    database = SessionLocal()
    try:
        result = await decide_batch(database, [_request()], UnavailableRizzo(), LocalFallback())
        executions = database.scalars(
            select(AIExecution)
            .where(AIExecution.prompt_name == "document-classifier")
            .order_by(AIExecution.created_at)
        ).all()
        assert result == [ClassificationDecision(document_type="UNKNOWN", confidence=0.0)]
        assert [(item.provider, item.status, item.model) for item in executions] == [
            ("rizzo-flow", "FAILED", "rizzo-flow"),
            ("lmstudio", "SUCCEEDED", "local-fallback"),
        ]
    finally:
        database.execute(delete(AIExecution).where(AIExecution.prompt_name == "document-classifier"))
        database.commit()
        database.close()