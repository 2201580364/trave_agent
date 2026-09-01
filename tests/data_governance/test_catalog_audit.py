from __future__ import annotations

import sqlite3
from pathlib import Path

from travel_agent.data_governance.catalog_audit import audit_catalog_database


def _database(path: Path, rows: list[tuple[str, str, str, str, str]]) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE place_revisions (
            place_revision_id TEXT PRIMARY KEY,
            place_id TEXT NOT NULL,
            canonical_name TEXT NOT NULL,
            admin_area TEXT NOT NULL,
            lifecycle_status TEXT NOT NULL
        );
        CREATE TABLE place_source_records (
            place_id TEXT NOT NULL,
            source_id TEXT NOT NULL
        );
        """
    )
    connection.executemany("INSERT INTO place_revisions VALUES (?, ?, ?, ?, ?)", rows)
    connection.commit()
    connection.close()


def test_catalog_audit_rejects_published_browser_fixture(tmp_path: Path) -> None:
    database = tmp_path / "catalog.db"
    _database(
        database,
        [
            ("r1", "browser-e2e-place", "Browser E2E Revision 3", "???", "published"),
            ("r2", "real-place", "西湖音乐喷泉表演", "上城区", "published"),
            ("r3", "candidate-place", "候选地点", "西湖区", "candidate"),
        ],
    )
    report = audit_catalog_database(database)

    assert report.published_revision_count == 2
    assert report.published_business_count == 1
    assert report.candidate_count == 1
    assert report.violations[0]["place_revision_id"] == "r1"
    assert "browser_e2e_place_id" in report.violations[0]["reasons"]
    assert "garbled_business_label" in report.violations[0]["reasons"]
    assert not report.passed


def test_catalog_audit_passes_clean_published_catalog(tmp_path: Path) -> None:
    database = tmp_path / "catalog.db"
    _database(
        database,
        [("r1", "real-place", "西湖音乐喷泉表演", "上城区", "published")],
    )

    report = audit_catalog_database(database)

    assert report.passed
    assert report.published_business_count == 1
    assert report.human_verified_count == 0
