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
    """Resolve exact or reversed full names; unmatched fiscal codes remain reviewable conflicts."""
    normalized_code = ""
    if fiscal_code:
        try:
            normalized_code = normalize_fiscal_code(fiscal_code)
        except ValueError:
            normalized_code = ""
        member = db.scalar(select(HouseholdMember).where(HouseholdMember.fiscal_code == normalized_code))
        if member:
            return Resolution(member.id, 1.0, False, ["exact_fiscal_code"])
    if full_name:
        parts = full_name.strip().split(maxsplit=1)
        if len(parts) == 2:
            direct = list(db.scalars(select(HouseholdMember).where(HouseholdMember.first_name.ilike(parts[0]), HouseholdMember.last_name.ilike(parts[1]))))
            reversed_name = list(db.scalars(select(HouseholdMember).where(HouseholdMember.first_name.ilike(parts[1]), HouseholdMember.last_name.ilike(parts[0]))))
            candidates = {candidate.id: candidate for candidate in [*direct, *reversed_name]}
            if len(candidates) == 1:
                member = next(iter(candidates.values()))
                evidence = ["exact_full_name" if direct else "reversed_full_name"]
                if normalized_code and normalized_code != member.fiscal_code:
                    return Resolution(member.id, 0.9, True, [*evidence, "unmatched_fiscal_code"])
                return Resolution(member.id, 0.9, False, evidence)
            if len(candidates) > 1:
                return Resolution(None, 0.0, True, ["ambiguous_full_name"])
    return Resolution(None, 0.0, False, [])
