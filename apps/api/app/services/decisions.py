"""Typed AI decision orchestration with local Rizzo-first fallback."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.adapters.lmstudio import LLMProvider, LLMUnavailable
from app.adapters.rizzo import RizzoFlowProvider, RizzoFlowUnavailable
from app.models.entities import AIExecution
from app.services.prompt_registry import get_prompt


class DecisionUnavailable(RuntimeError):
    """Raised when neither Rizzo Flow nor the configured fallback can decide."""


@dataclass(frozen=True)
class TypedDecisionRequest:
    """One locally sourced, schema-validated request in a decision batch."""

    task: str
    input_text: str
    output_schema: type[BaseModel]
    prompt_name: str
    prompt_version: str = "v1"
    document_id: UUID | None = None


def _create_executions(db: Session, requests: list[TypedDecisionRequest], provider: str, model: str) -> list[AIExecution]:
    """Persist start metadata without retaining confidential request content."""
    executions = [
        AIExecution(
            document_id=request.document_id,
            provider=provider,
            model=model,
            prompt_name=request.prompt_name,
            prompt_version=request.prompt_version,
            schema_version="v1",
            input_hash=hashlib.sha256(request.input_text.encode()).hexdigest(),
            status="STARTED",
        )
        for request in requests
    ]
    db.add_all(executions)
    db.commit()
    return executions


def _finish(executions: list[AIExecution], status: str, started: float) -> None:
    """Apply the same non-sensitive outcome metadata to a provider attempt."""
    duration_ms = int((time.monotonic() - started) * 1000)
    for execution in executions:
        execution.status = status
        execution.duration_ms = duration_ms


def _prompted_request(request: TypedDecisionRequest) -> dict[str, Any]:
    """Build one explicit local-flow request from a versioned prompt asset."""
    prompt = get_prompt(request.prompt_name, request.prompt_version).path.read_text()
    return {
        "task": request.task,
        "prompt": f"{prompt}\n\nInput:\n{request.input_text}",
        "schema": request.output_schema.model_json_schema(),
    }


async def decide_batch(
    db: Session,
    requests: list[TypedDecisionRequest],
    rizzo_provider: RizzoFlowProvider | None,
    fallback_provider: LLMProvider | None,
) -> list[BaseModel]:
    """Return typed batch decisions, falling back only after a failed Rizzo attempt."""
    if not requests:
        return []

    if rizzo_provider is not None:
        started = time.monotonic()
        executions = _create_executions(db, requests, "rizzo-flow", rizzo_provider.model_id)
        try:
            raw_outputs = await rizzo_provider.decide_batch([_prompted_request(request) for request in requests])
            outputs = [request.output_schema.model_validate(raw) for request, raw in zip(requests, raw_outputs, strict=True)]
        except (RizzoFlowUnavailable, ValidationError, ValueError):
            _finish(executions, "FAILED", started)
            db.commit()
        else:
            _finish(executions, "SUCCEEDED", started)
            db.commit()
            return outputs

    if fallback_provider is None:
        raise DecisionUnavailable("No local AI provider could produce typed decisions.")

    started = time.monotonic()
    executions = _create_executions(db, requests, "lmstudio", fallback_provider.model_id)
    try:
        outputs = [
            request.output_schema.model_validate(
                await fallback_provider.structured_completion(
                    _prompted_request(request)["prompt"], request.output_schema.model_json_schema()
                )
            )
            for request in requests
        ]
    except (LLMUnavailable, ValidationError, ValueError) as error:
        _finish(executions, "FAILED", started)
        db.commit()
        raise DecisionUnavailable("Fallback local AI decision failed.") from error
    _finish(executions, "SUCCEEDED", started)
    db.commit()
    return outputs