from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "place_catalog"))

from prepare_candidate_projections import build_candidate_projection  # noqa: E402, I001
from test_place_catalog import (  # noqa: E402
    _access_points,
    _geometry,
    _place,
    _revision,
    _source,
    _time_rule,
)
from travel_agent.domain.place_catalog import (  # noqa: E402
    PlaceRevisionEvidence,
    canonical_projection_sha256,
)
from travel_agent.infrastructure.database import create_schema  # noqa: E402
from travel_agent.infrastructure.database.place_catalog import (  # noqa: E402
    SqlAlchemyPlaceCatalogRepository,
    SolverPlaceProjectionRow,
)


def _evidence() -> PlaceRevisionEvidence:
    return PlaceRevisionEvidence(
        revision=_revision(),
        source_records=(_source(),),
        geometries=(_geometry(),),
        access_points=_access_points(),
        time_rules=(_time_rule(),),
        closures=(),
        date_exceptions=(),
        projection=None,
        relations=(),
    )


def test_build_candidate_projection_is_gate_clean_and_hash_stable() -> None:
    projection = build_candidate_projection(
        _revision(),
        _evidence(),
        place=_place(),
        data_snapshot_version="hangzhou-research-candidate-v1",
        solver_node_id=1001,
    )

    assert projection.status == "candidate"
    assert projection.gate_reason_codes == ()
    assert projection.arrival_access_point_id == "access_westlake_arrival"
    assert projection.departure_access_point_id == "access_westlake_departure"
    assert projection.solver_payload["data_verified"] is True
    assert canonical_projection_sha256(projection) == projection.projection_hash


def test_build_candidate_projection_requires_human_verified_revision() -> None:
    candidate = replace(_revision(), lifecycle_status="candidate")
    with pytest.raises(ValueError, match="human_verified"):
        build_candidate_projection(
            candidate,
            _evidence(),
            place=_place(),
            data_snapshot_version="hangzhou-research-candidate-v1",
            solver_node_id=1001,
        )


def test_build_candidate_projection_requires_verified_access_point() -> None:
    evidence = replace(_evidence(), access_points=())
    with pytest.raises(ValueError, match="verified access point"):
        build_candidate_projection(
            _revision(),
            evidence,
            place=_place(),
            data_snapshot_version="hangzhou-research-candidate-v1",
            solver_node_id=1001,
        )


def test_prepare_cli_reports_one_blocked_revision_without_aborting(tmp_path: Path) -> None:
    database = tmp_path / "projection-prepare.db"
    engine = create_engine(f"sqlite:///{database}")
    create_schema(engine)
    with Session(engine) as session:
        repository = SqlAlchemyPlaceCatalogRepository(session)
        repository.add_place(_place())
        repository.add_source_record(_source())
        repository.add_revision(_revision())
        session.commit()

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "prepare_candidate_projections.py"),
            "--database",
            str(database),
            "--data-snapshot-version",
            "hangzhou-research-candidate-v1",
            "--revision-id",
            _revision().place_revision_id,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert '"status": "blocked"' in result.stdout
    assert '"MISSING_VERIFIED_ACCESS_POINT"' in result.stdout
    assert "candidate projections: prepared=0, skipped=0, blocked=1" in result.stdout


def test_prepare_cli_persists_candidate_projection_and_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "projection-prepare-success.db"
    engine = create_engine(f"sqlite:///{database}")
    create_schema(engine)
    with Session(engine) as session:
        repository = SqlAlchemyPlaceCatalogRepository(session)
        repository.add_place(_place())
        repository.add_source_record(_source())
        repository.add_revision(_revision())
        repository.add_geometry(_geometry())
        for access_point in _access_points():
            repository.add_access_point(access_point)
        repository.add_time_rule(_time_rule())
        session.commit()

    args = [
        sys.executable,
        str(ROOT / "scripts" / "prepare_candidate_projections.py"),
        "--database",
        str(database),
        "--data-snapshot-version",
        "hangzhou-research-candidate-v1",
        "--revision-id",
        _revision().place_revision_id,
    ]
    first = subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True)
    second = subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True)
    assert "candidate projections: prepared=1, skipped=0, blocked=0" in first.stdout
    assert "candidate projections: prepared=0, skipped=1, blocked=0" in second.stdout

    with Session(engine) as session:
        projection = session.get(SolverPlaceProjectionRow, "projection-place_revision_westlake_1")
    assert projection is not None
    assert projection.status == "candidate"
    assert projection.gate_reason_codes == []


def test_snapshot_node_allocator_skips_existing_ids(tmp_path: Path) -> None:
    database = tmp_path / "projection-node-allocation.db"
    engine = create_engine(f"sqlite:///{database}")
    create_schema(engine)
    with Session(engine) as session:
        session.add(
            SolverPlaceProjectionRow(
                projection_id="existing-projection",
                projection_version="solver-place-projection-v1",
                data_snapshot_version="snapshot-v1",
                place_id="place-existing",
                place_revision_id="revision-existing",
                solver_node_id=1000,
                place_kind="attraction",
                geometry_kind="point",
                arrival_access_point_id="arrival-existing",
                departure_access_point_id="departure-existing",
                duration_min=30,
                duration_recommended=60,
                duration_max=90,
                internal_travel_min=0,
                solver_payload={},
                projection_hash="0" * 64,
                status="candidate",
                gate_reason_codes=[],
                created_at="2026-08-31T00:00:00+00:00",
                published_at=None,
            )
        )
        session.commit()
        repository = SqlAlchemyPlaceCatalogRepository(session)
        assert repository.next_solver_node_id("snapshot-v1", minimum=1000) == 1001
        assert repository.next_solver_node_id("other-snapshot", minimum=1000) == 1000
