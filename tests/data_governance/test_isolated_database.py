from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from travel_agent.data_governance.isolated_database import (
    IsolatedDatabaseError,
    validate_isolated_database_target,
)


def test_isolated_database_rejects_business_database(tmp_path: Path) -> None:
    business = tmp_path / "business.db"

    with pytest.raises(IsolatedDatabaseError, match="business database"):
        validate_isolated_database_target(business, local_database=business)


def test_isolated_database_rejects_existing_schema(tmp_path: Path) -> None:
    database = tmp_path / "existing.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE example (id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()

    with pytest.raises(IsolatedDatabaseError, match="already contains tables"):
        validate_isolated_database_target(
            database, local_database=tmp_path / "business.db"
        )


def test_isolated_database_allows_new_target(tmp_path: Path) -> None:
    target = validate_isolated_database_target(
        tmp_path / "research.db", local_database=tmp_path / "business.db"
    )

    assert target == (tmp_path / "research.db").resolve()
