from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine

from travel_agent.data_governance.research_readiness import (
    load_research_readiness,
    render_research_readiness_markdown,
)
from travel_agent.infrastructure.database import create_schema

ROOT = Path(__file__).resolve().parents[2]


def _candidate_database(tmp_path: Path) -> Path:
    database = tmp_path / "research-readiness.db"
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    create_schema(engine)
    engine.dispose()
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "import_candidate_revisions.py"),
            "--database",
            str(database),
            "--limit",
            "2",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return database


def test_report_reuses_six_check_readiness_for_selected_candidates(tmp_path: Path) -> None:
    report = load_research_readiness(
        _candidate_database(tmp_path),
        candidate_ids=("hz-cand-001", "revision-hz-cand-002"),
        lifecycle_status="candidate",
    )

    assert len(report.items) == 2
    assert report.lifecycle_counts == {"candidate": 2}
    assert report.readiness_counts == {"needs_evidence": 2}
    assert report.missing_check_counts == {
        "access_point": 2,
        "basic": 2,
        "geometry": 2,
        "relation": 2,
        "time": 2,
    }
    assert all(item.completed_checks == 1 for item in report.items)
    assert all(item.verified_checks == 1 for item in report.items)


def test_markdown_report_is_business_readable(tmp_path: Path) -> None:
    report = load_research_readiness(
        _candidate_database(tmp_path),
        candidate_ids=("hz-cand-001",),
    )

    rendered = render_research_readiness_markdown(report)

    assert "研究目录审核就绪报告" in rendered
    assert "西湖" in rendered
    assert "地点几何" in rendered
    assert "access_point" not in rendered


def test_cli_outputs_machine_readable_json(tmp_path: Path) -> None:
    database = _candidate_database(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "report_research_readiness.py"),
            "--database",
            str(database),
            "--candidate-id",
            "hz-cand-002",
            "--format",
            "json",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["total"] == 1
    assert payload["items"][0]["candidate_id"] == "hz-cand-002"
