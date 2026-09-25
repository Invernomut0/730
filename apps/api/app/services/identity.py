"""Deterministic household patient resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import HouseholdMember


@dataclass(frozen=True)
class Resolution:
    member_id: UUID | None
    confidence: float
    conflict: bool
    evidence: list[str]


def normalize_fiscal_code(value: str) -> str:
    """Normalize and validate the shape of an Italian fiscal code."""
    normalized = re.sub(r"\s+", "", value).upper()
    if not re.fullmatch(r"[A-Z0-9]{16}", normalized):
        raise ValueError("Fiscal code must contain exactly 16 letters or digits.")
    return normalized


def resolve_patient(db: Session, fiscal_code: str | None, full_name: str | None) -> Resolution:
    """Resolve only exact identifiers/names; competing matches require review."""
    if fiscal_code:
        try:
            code = normalize_fiscal_code(fiscal_code)
        except ValueError:
            code = ""
        member = db.scalar(select(HouseholdMember).where(HouseholdMember.fiscal_code == code))
        if member:
            return Resolution(member.id, 1.0, False, ["exact_fiscal_code"])
    if full_name:
        parts = full_name.strip().split(maxsplit=1)
        if len(parts) == 2:
            candidates = list(db.scalars(select(HouseholdMember).where(HouseholdMember.first_name.ilike(parts[0]), HouseholdMember.last_name.ilike(parts[1]))))
            if len(candidates) == 1:
                return Resolution(candidates[0].id, 0.9, False, ["exact_full_name"])
            if len(candidates) > 1:
                return Resolution(None, 0.0, True, ["ambiguous_full_name"])
    return Resolution(None, 0.0, False, [])
