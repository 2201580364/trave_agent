"""Guardrails for creating isolated catalog databases."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


class IsolatedDatabaseError(ValueError):
    """Raised when a database path cannot be safely initialized."""


@dataclass(frozen=True)
class DatabaseEnvironment:
    name: str
    database: Path


def validate_isolated_database_target(database: Path, *, local_database: Path) -> Path:
    """Validate that ``database`` is a new, non-business SQLite target."""

    target = database.resolve()
    if target == local_database.resolve():
        raise IsolatedDatabaseError("isolated database cannot reuse the local business database")
    if target.exists():
        if target.is_dir():
            raise IsolatedDatabaseError("isolated database target is a directory")
        connection = sqlite3.connect(target)
        try:
            has_tables = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' LIMIT 1"
            ).fetchone()
        finally:
            connection.close()
        if has_tables:
            raise IsolatedDatabaseError(
                "isolated database target already contains tables; refusing to overwrite"
            )
    return target
