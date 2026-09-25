"""Local CSV import and conservative reconciliation for pre-filled 730 rows."""
from __future__ import annotations
import csv
import hashlib
import re
from datetime import date
from decimal import Decimal
from io import StringIO
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.entities import Precompiled730Import, Precompiled730Row, TaxAllocation


def normalize_description(value: str) -> str:
    """Normalize descriptions without changing their source evidence."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", value.lower())).strip()


def import_csv(db: Session, tax_year: int, filename: str, content: bytes) -> Precompiled730Import:
    """Import a UTF-8 CSV with date, amount, description and optional fiscal_code."""
    digest = hashlib.sha256(content).hexdigest()
    existing = db.scalar(select(Precompiled730Import).where(Precompiled730Import.content_hash == digest))
    if existing:
        return existing
    imported = Precompiled730Import(tax_year=tax_year, source_filename=filename, content_hash=digest)
    db.add(imported); db.flush()
    for row in csv.DictReader(StringIO(content.decode("utf-8-sig"))):
        amount = Decimal((row.get("amount") or "0").replace(",", "."))
        parsed_date = date.fromisoformat(row["expense_date"]) if row.get("expense_date") else None
        db.add(Precompiled730Row(import_id=imported.id, tax_year=tax_year, fiscal_code=row.get("fiscal_code") or None, expense_date=parsed_date, amount=amount, normalized_description=normalize_description(row.get("description") or "")))
    db.commit(); return imported


def reconcile(db: Session, tax_year: int) -> int:
    """Match exactly one local allocation by amount; flag all other rows for review."""
    matched = 0
    allocations = list(db.scalars(select(TaxAllocation).where(TaxAllocation.tax_year == tax_year)))
    for row in db.scalars(select(Precompiled730Row).where(Precompiled730Row.tax_year == tax_year)):
        candidates = [item for item in allocations if Decimal(str(item.eligible_amount)) == Decimal(str(row.amount))]
        if len(candidates) == 1:
            row.tax_allocation_id, row.status = candidates[0].id, "MATCHED"; matched += 1
        elif candidates:
            row.status = "REVIEW_REQUIRED"
        else:
            row.status = "PRECOMPILED_ONLY"
    db.commit(); return matched
