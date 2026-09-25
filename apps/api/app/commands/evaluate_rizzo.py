"""Evaluate the local Rizzo Flow service on synthetic calibration data."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.adapters.rizzo import RizzoFlowAdapter
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.schemas.calibration import DocumentClassificationDecision
from app.services.calibration import load_document_classification_calibration
from app.services.decisions import DecisionUnavailable, TypedDecisionRequest, decide_batch
from app.services.evaluation import evaluate_document_classification


def build_parser() -> argparse.ArgumentParser:
    """Build the local-only command interface without exposing sample text."""
    parser = argparse.ArgumentParser(description="Evaluate local Rizzo Flow on synthetic classification data.")
    parser.add_argument("--minimum-accuracy", type=float, default=0.95)
    parser.add_argument("--output", type=Path)
    return parser


async def evaluate(minimum_accuracy: float):
    """Run Rizzo without fallback so unavailable or invalid results fail clearly."""
    settings = get_settings()
    if not settings.rizzo_flow_enabled or not settings.rizzo_flow_base_url:
        raise ValueError("Rizzo Flow must be enabled and configured for evaluation.")

    samples = load_document_classification_calibration()
    requests = [
        TypedDecisionRequest(
            task=sample.task,
            input_text=sample.input_text,
            output_schema=DocumentClassificationDecision,
            prompt_name=sample.prompt_name,
            prompt_version=sample.prompt_version,
        )
        for sample in samples
    ]
    provider = RizzoFlowAdapter(settings)
    database = SessionLocal()
    try:
        outputs = await decide_batch(database, requests, provider, None)
        decisions = [DocumentClassificationDecision.model_validate(output) for output in outputs]
    finally:
        database.close()
    return evaluate_document_classification(samples, decisions, provider.model_id, minimum_accuracy)


def main() -> int:
    """Write a privacy-safe JSON report and return a CI-friendly status code."""
    arguments = build_parser().parse_args()
    try:
        report = asyncio.run(evaluate(arguments.minimum_accuracy))
    except (DecisionUnavailable, ValueError) as error:
        print(f"Evaluation failed: {error}", file=sys.stderr)
        return 2

    serialized = json.dumps(report.model_dump(mode="json"), sort_keys=True)
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(f"{serialized}\n", encoding="utf-8")
    print(serialized)
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())