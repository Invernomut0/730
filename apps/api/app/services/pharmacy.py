"""Deterministic local pharmacy catalog, matching, and allocation services."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    DrugPackage,
    PharmacyReceipt,
    Prescription,
    PrescriptionItem,
    ReceiptLine,
    ReviewTask,
    ReviewType,
)

_AIC_PATTERN = re.compile(r"(?<!\d)(\d{9})(?!\d)")


@dataclass(frozen=True)
class AllocationResult:
    allocated_amount: Decimal
    review_required: bool


def normalize_aic(value: str | None) -> str | None:
    """Extract a canonical nine-digit Italian AIC from OCR text."""
    if not value:
        return None
    match = _AIC_PATTERN.search(value.replace(" ", ""))
    return match.group(1) if match else None


def import_aifa_csv(db: Session, source: Path, catalog_version: str) -> int:
    """Upsert a local AIFA-compatible CSV with AIC and package metadata."""
    count = 0
    with source.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            aic = normalize_aic(row.get("aic"))
            if not aic or not row.get("name"):
                continue
            package = db.scalar(select(DrugPackage).where(DrugPackage.aic == aic))
            if package is None:
                package = DrugPackage(aic=aic, name=row["name"].strip(), catalog_version=catalog_version)
                db.add(package)
            else:
                package.name, package.catalog_version = row["name"].strip(), catalog_version
            package.active_ingredient = (row.get("active_ingredient") or "").strip() or None
            package.manufacturer = (row.get("manufacturer") or "").strip() or None
            count += 1
    db.commit()
    return count


def add_receipt_line(
    db: Session,
    receipt: PharmacyReceipt,
    description: str,
    amount: Decimal | None,
    aic_text: str | None,
    patient_id: UUID | None = None,
) -> ReceiptLine:
    """Create one atomic receipt line and validate its AIC against the local catalog."""
    aic = normalize_aic(aic_text)
    package = db.scalar(select(DrugPackage).where(DrugPackage.aic == aic)) if aic else None
    line = ReceiptLine(
        receipt_id=receipt.id,
        payer_id=receipt.payer_id,
        patient_id=patient_id,
        aic=aic,
        description=description.strip(),
        amount=amount,
        drug_package_id=package.id if package else None,
        aic_validated=package is not None,
    )
    db.add(line)
    return line


def match_receipt_lines(db: Session, receipt_id: UUID) -> int:
    """Match validated receipt lines to prescription items by AIC, then normalized name."""
    lines = list(db.scalars(select(ReceiptLine).where(ReceiptLine.receipt_id == receipt_id)))
    matched = 0
    for line in lines:
        candidates = list(
            db.scalars(
                select(PrescriptionItem).join(Prescription).where(
                    PrescriptionItem.aic == line.aic if line.aic else PrescriptionItem.requested_name.ilike(f"%{line.description}%")
                )
            )
        )
        if len(candidates) == 1:
            item = candidates[0]
            line.prescription_item_id = item.id
            prescription = db.get(Prescription, item.prescription_id)
            line.patient_id = prescription.patient_id if prescription else line.patient_id
            matched += 1
        if line.patient_id is None:
            db.add(ReviewTask(type=ReviewType.PATIENT_PAYER_CONFLICT, entity_type="ReceiptLine", entity_id=line.id, priority=80, context={"reason": "patient_unresolved", "aic": line.aic, "payer_id": str(line.payer_id) if line.payer_id else None}))
        elif line.payer_id and line.patient_id != line.payer_id:
            db.add(ReviewTask(type=ReviewType.PATIENT_PAYER_CONFLICT, entity_type="ReceiptLine", entity_id=line.id, priority=60, context={"reason": "patient_differs_from_payer", "aic": line.aic}))
    db.commit()
    return matched


def allocate_receipt(db: Session, receipt_id: UUID, allocations: dict[UUID, UUID]) -> AllocationResult:
    """Allocate mixed receipt lines to explicit patients, preserving payer separately."""
    total = Decimal(0)
    review_required = False
    for line_id, patient_id in allocations.items():
        line = db.get(ReceiptLine, line_id)
        if line is None or line.receipt_id != receipt_id:
            raise ValueError("Receipt line does not belong to this receipt.")
        line.patient_id = patient_id
        total += Decimal(str(line.amount or 0))
        review_required = review_required or (line.payer_id is not None and line.payer_id != patient_id)
    db.commit()
    return AllocationResult(allocated_amount=total, review_required=review_required)
