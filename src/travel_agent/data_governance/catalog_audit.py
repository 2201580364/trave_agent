"""Read-only checks for separating research data from browser test fixtures."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CatalogAuditReport:
    """Counts and violations found in a catalog database."""

    database: str
    published_revision_count: int
    published_business_count: int
    candidate_count: int
    human_verified_count: int
    violations: tuple[dict[str, str], ...]

    @property
    def passed(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict[str, Any]:
        return {
            "database": self.database,
            "published_revision_count": self.published_revision_count,
            "published_business_count": self.published_business_count,
            "candidate_count": self.candidate_count,
            "human_verified_count": self.human_verified_count,
            "violations": list(self.violations),
            "passed": self.passed,
        }


def audit_catalog_database(database: Path) -> CatalogAuditReport:
    """Audit published rows without changing the database.

    Browser E2E data is identified by explicit fixture provenance, the stable
    ``browser-e2e`` place namespace, or the historical placeholder/garbled
    labels that were used by the browser fixture.  The checks intentionally
    fail closed for published data; candidate and human-verified rows are
    counted but do not fail this audit.
    """

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        revisions = connection.execute(
            """
            SELECT r.place_revision_id, r.place_id, r.canonical_name, r.admin_area,
                   r.lifecycle_status,
                   EXISTS (
                       SELECT 1 FROM place_source_records s
                       WHERE s.place_id = r.place_id AND s.source_id = 'browser_fixture'
                   ) AS has_browser_source
            FROM place_revisions r
            WHERE r.lifecycle_status = 'published'
            ORDER BY r.place_revision_id
            """
        ).fetchall()
        counts = {
            row["lifecycle_status"]: int(row["count"])
            for row in connection.execute(
                "SELECT lifecycle_status, COUNT(*) AS count "
                "FROM place_revisions GROUP BY lifecycle_status"
            )
        }
    finally:
        connection.close()

    violations: list[dict[str, str]] = []
    for row in revisions:
        reasons: list[str] = []
        place_id = str(row["place_id"])
        name = str(row["canonical_name"] or "")
        area = str(row["admin_area"] or "")
        if bool(row["has_browser_source"]):
            reasons.append("browser_fixture_source")
        if place_id.startswith("browser-e2e"):
            reasons.append("browser_e2e_place_id")
        if name.startswith("Browser E2E"):
            reasons.append("browser_e2e_name")
        if "?" in area or "\ufffd" in name or "\ufffd" in area:
            reasons.append("garbled_business_label")
        if reasons:
            violations.append(
                {
                    "place_revision_id": str(row["place_revision_id"]),
                    "place_id": place_id,
                    "reasons": ",".join(reasons),
                }
            )

    return CatalogAuditReport(
        database=str(database),
        published_revision_count=len(revisions),
        published_business_count=len(revisions) - len(violations),
        candidate_count=counts.get("candidate", 0),
        human_verified_count=counts.get("human_verified", 0),
        violations=tuple(violations),
    )
