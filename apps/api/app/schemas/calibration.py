"""Typed contracts for versioned, synthetic AI calibration datasets."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.entities import DocumentType


class DocumentClassificationExpectation(BaseModel):
    """Human-reviewed expected document category for one synthetic sample."""

    model_config = ConfigDict(extra="forbid")

    document_type: DocumentType


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