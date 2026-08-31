"""Prepare candidate solver projections from human-verified Place Revisions.

This is a data-pipeline step, not a publication shortcut.  It only creates
``candidate`` projections and records publication-gate reasons; publishing
still goes through the admin publication workflow and ``publish_projection``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from travel_agent.domain.place_catalog import (  # noqa: E402
    PlaceRevisionEvidence,
    ProjectionPublicationContext,
    SolverPlaceProjection,
    canonical_projection_sha256,
    evaluate_projection_publication,
)
from travel_agent.infrastructure.database.place_catalog import (  # noqa: E402
    SqlAlchemyPlaceCatalogRepository,
)

DEFAULT_DATABASE = ROOT / ".local/travel_agent.db"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--data-snapshot-version", required=True)
    parser.add_argument("--revision-id", action="append", required=True)
    parser.add_argument(
        "--solver-node-start",
        type=int,
        default=1000,
        help="lowest node id to consider; existing snapshot IDs are always skipped",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.solver_node_start <= 0:
        parser.error("solver node start must be positive")

    revision_ids = tuple(sorted(set(args.revision_id)))
    engine = create_engine(f"sqlite:///{args.database.resolve().as_posix()}")
    prepared = 0
    skipped = 0
    blocked = 0
    reserved_node_ids: set[int] = set()
    with Session(engine) as session:
        repository = SqlAlchemyPlaceCatalogRepository(session)
        for revision_id in revision_ids:
            revision = repository.get_revision(revision_id)
            if revision is None:
                print(json.dumps({"revision_id": revision_id, "status": "missing"}))
                skipped += 1
                continue
            if revision.lifecycle_status != "human_verified":
                print(
                    json.dumps(
                        {
                            "revision_id": revision_id,
                            "status": "blocked",
                            "reason_codes": ["REVISION_NOT_HUMAN_VERIFIED"],
                        }
                    )
                )
                blocked += 1
                continue
            existing = repository.get_projection_for_revision(revision_id)
            if existing is not None:
                print(
                    json.dumps(
                        {
                            "revision_id": revision_id,
                            "status": "skipped",
                            "projection_id": existing.projection_id,
                        }
                    )
                )
                skipped += 1
                continue
            evidence = repository.load_revision_evidence(revision_id)
            place = repository.get_place(revision.place_id)
            if evidence is None or place is None:
                print(
                    json.dumps(
                        {
                            "revision_id": revision_id,
                            "status": "blocked",
                            "reason_codes": ["REVISION_EVIDENCE_MISSING"],
                        }
                    )
                )
                blocked += 1
                continue
            try:
                solver_node_id = repository.next_solver_node_id(
                    args.data_snapshot_version, minimum=args.solver_node_start
                )
                while solver_node_id in reserved_node_ids:
                    solver_node_id += 1
                reserved_node_ids.add(solver_node_id)
                projection = build_candidate_projection(
                    revision,
                    evidence,
                    place=place,
                    data_snapshot_version=args.data_snapshot_version,
                    solver_node_id=solver_node_id,
                )
            except ValueError as exc:
                reserved_node_ids.discard(solver_node_id)
                reason_code = _build_error_code(str(exc))
                print(
                    json.dumps(
                        {
                            "revision_id": revision_id,
                            "status": "blocked",
                            "reason_codes": [reason_code],
                        },
                        ensure_ascii=False,
                    )
                )
                blocked += 1
                continue
            reasons = projection.gate_reason_codes
            if not args.dry_run:
                repository.add_projection(projection)
            prepared += 1
            blocked += bool(reasons)
            print(
                json.dumps(
                    {
                        "revision_id": revision_id,
                        "status": "prepared" if not reasons else "prepared_blocked",
                        "projection_id": projection.projection_id,
                        "reason_codes": list(reasons),
                        "dry_run": args.dry_run,
                    },
                    ensure_ascii=False,
                )
            )
        if not args.dry_run:
            session.commit()
    print(
        f"candidate projections: prepared={prepared}, skipped={skipped}, "
        f"blocked={blocked}, dry_run={args.dry_run}"
    )
    return 0


def build_candidate_projection(
    revision: Any,
    evidence: PlaceRevisionEvidence,
    *,
    place: Any,
    data_snapshot_version: str,
    solver_node_id: int,
) -> SolverPlaceProjection:
    """Build one deterministic candidate projection without publishing it."""

    if revision.lifecycle_status != "human_verified":
        raise ValueError("candidate projection requires a human_verified revision")
    if solver_node_id <= 0:
        raise ValueError("solver node id must be positive")
    access_points = [
        item
        for item in evidence.access_points
        if item.active and item.review_status == "human_verified"
    ]
    if not access_points:
        raise ValueError("candidate projection requires an active verified access point")
    arrival = min(
        access_points,
        key=lambda item: (_access_rank(item.access_point_kind, False), item.access_point_id),
    )
    departure = min(
        access_points,
        key=lambda item: (_access_rank(item.access_point_kind, True), item.access_point_id),
    )
    payload = _solver_payload(revision, evidence, data_verified=False)
    projection = SolverPlaceProjection(
        projection_id=f"projection-{revision.place_revision_id}",
        projection_version="solver-place-projection-v1",
        data_snapshot_version=data_snapshot_version,
        place_id=revision.place_id,
        place_revision_id=revision.place_revision_id,
        solver_node_id=solver_node_id,
        place_kind=revision.place_kind,
        geometry_kind=revision.geometry_kind,
        arrival_access_point_id=arrival.access_point_id,
        departure_access_point_id=departure.access_point_id,
        duration_min=revision.duration_min,
        duration_recommended=revision.duration_recommended,
        duration_max=revision.duration_max,
        internal_travel_min=revision.internal_travel_min,
        solver_payload=payload,
        projection_hash="0" * 64,
        status="candidate",
        gate_reason_codes=(),
        created_at=revision.created_at,
    )
    projection = replace(projection, projection_hash=canonical_projection_sha256(projection))
    context = ProjectionPublicationContext(
        place,
        revision,
        evidence.source_records,
        evidence.geometries,
        evidence.access_points,
        evidence.time_rules,
        evidence.relations,
        projection,
    )
    reasons = evaluate_projection_publication(context)
    if not reasons:
        projection = replace(
            projection,
            solver_payload=_solver_payload(revision, evidence, data_verified=True),
        )
        projection = replace(projection, projection_hash=canonical_projection_sha256(projection))
    return replace(projection, gate_reason_codes=reasons)


def _access_rank(kind: str, departure: bool) -> int:
    if departure:
        order = {
            "visitor_exit": 0,
            "route_end": 1,
            "visitor_entrance": 2,
            "route_start": 3,
        }
    else:
        order = {
            "visitor_entrance": 0,
            "route_start": 1,
            "performance_location": 2,
            "area_representative": 3,
        }
    return order.get(kind, 10)


def _solver_payload(
    revision: Any, evidence: PlaceRevisionEvidence, *, data_verified: bool
) -> dict[str, object]:
    return {
        "attraction_id": revision.place_id,
        "name": revision.canonical_name,
        "suggested_duration": revision.duration_recommended,
        "close_days": sorted({item.weekday for item in evidence.closures if item.active}),
        "is_always_open": revision.is_always_open,
        "is_indoor": revision.indoor_outdoor == "indoor",
        "energy_level": revision.energy_level,
        "data_verified": data_verified,
    }


def _build_error_code(message: str) -> str:
    if "verified access point" in message:
        return "MISSING_VERIFIED_ACCESS_POINT"
    if "human_verified" in message:
        return "REVISION_NOT_HUMAN_VERIFIED"
    if "solver node id" in message:
        return "INVALID_SOLVER_NODE_ID"
    return "PROJECTION_BUILD_INVALID"


if __name__ == "__main__":
    raise SystemExit(main())
