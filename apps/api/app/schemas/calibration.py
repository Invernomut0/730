"""Typed contracts for versioned, synthetic AI calibration datasets."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.entities import DocumentType


class DocumentClassificationExpectation(BaseModel):
    """Human-reviewed expected document category for one synthetic sample."""

    model_config = ConfigDict(extra="forbid")

    document_type: DocumentType


class DocumentClassificationDecision(BaseModel):
    """Schema-constrained Rizzo output for document classification."""

    model_config = ConfigDict(extra="forbid")

    document_type: DocumentType
    confidence: float = Field(ge=0, le=1)


class DocumentClassificationCalibrationSample(BaseModel):
    """One privacy-safe sample for evaluating the document-classifier prompt."""

    model_config = ConfigDict(extra="forbid")

    dataset_version: Literal["v1"]
    sample_id: str = Field(pattern=r"^CAL-CLF-\d{3}$")
    task: Literal["document_classification"]
    prompt_name: Literal["document-classifier"]
    prompt_version: Literal["v1"]
    input_text: str = Field(min_length=1, max_length=4_000)
    expected_output: DocumentClassificationExpectation
    source: Literal["synthetic"]
    tags: list[str] = Field(min_length=1)


class ClassificationMismatch(BaseModel):
    """Privacy-safe comparison of one synthetic sample outcome."""

    sample_id: str
    expected_document_type: DocumentType
    actual_document_type: DocumentType


class DocumentClassificationEvaluation(BaseModel):
    """Aggregate result emitted by the local Rizzo calibration command."""

    dataset_version: str
    prompt_name: str
    prompt_version: str
    provider: str
    model: str
    sample_count: int
    correct_count: int
    accuracy: float
    minimum_accuracy: float = Field(ge=0, le=1)
    passed: bool
    mismatches: list[ClassificationMismatch]