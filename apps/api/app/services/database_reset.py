"""Explicit, local-only reset of all application database tables."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.entities import Base


def reset_application_database(db: Session) -> None:
    """Atomically remove every application record while preserving the schema."""
    table_names = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    db.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))
    db.commit()