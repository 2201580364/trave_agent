"""Import the governed Hangzhou candidate catalog into staging Place Revisions.

The R0.2-04 catalog intentionally lacks verified duration, opening hours and
access points. Imported revisions therefore remain ``candidate`` and are never
solver eligible or published by this script.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from travel_agent.data_governance.candidate_catalog import validate_candidate_catalog  # noqa: E402
from travel_agent.domain.place_catalog import (  # noqa: E402
    Place,
    PlaceGeometry,
    PlaceRevision,
    PlaceSourceRecord,
)
from travel_agent.infrastructure.database.place_catalog import (  # noqa: E402
    PlaceRevisionRow,
    SqlAlchemyPlaceCatalogRepository,
)

DEFAULT_CATALOG = ROOT / "data/governance/hangzhou-candidate-catalog-v1.json"
DEFAULT_REGISTRY = ROOT / "data/governance/hangzhou-source-registry-v1.json"
DEFAULT_DICTIONARY = ROOT / "data/governance/place-collection-field-dictionary-v1.json"
DEFAULT_DATABASE = ROOT / ".local/travel_agent.db"
GAODE_SOURCE_URL = "https://lbs.amap.com/api/webservice/guide/api/search"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--dictionary", type=Path, default=DEFAULT_DICTIONARY)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument(
        "--candidate-id",
        action="append",
        dest="candidate_ids",
        help="import only this candidate ID; repeat for a controlled batch",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="import at most this many candidates after candidate-id filtering",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    catalog = _load(args.catalog)
    registry = _load(args.registry)
    dictionary = _load(args.dictionary)
    validate_candidate_catalog(catalog, registry, dictionary)

    selected = _select_candidates(
        catalog["candidates"], candidate_ids=args.candidate_ids, limit=args.limit
    )
    engine = create_engine(f"sqlite:///{args.database.resolve().as_posix()}")
    imported = 0
    updated = 0
    skipped = 0
    with Session(engine) as session:
        repository = SqlAlchemyPlaceCatalogRepository(session)
        for candidate in selected:
            revision_id = f"revision-{candidate['candidate_id']}"
            existing = session.get(PlaceRevisionRow, revision_id)
            if existing is not None:
                # Older imports created the 1/1/1 placeholder duration without
                # carrying the catalog review flags and inherited the legacy
                # ``not_required`` relation status.  Reconcile only pristine
                # imports so rerunning this command never overwrites facts that
                # an editor has already reviewed or changed.
                pristine_import = (
                    existing.lifecycle_status == "candidate"
                    and existing.revision_number == 1
                    and existing.revision_version == 1
                    and existing.reviewed_at is None
                    and existing.published_at is None
                    and not existing.solver_eligible
                    and (
                        existing.duration_min,
                        existing.duration_recommended,
                        existing.duration_max,
                    )
                    == (1, 1, 1)
                )
                changed = False
                if pristine_import and not existing.review_flags:
                    existing.review_flags = list(candidate["review_flags"])
                    changed = True
                if pristine_import and existing.relation_review_status == "not_required":
                    existing.relation_review_status = "pending"
                    changed = True
                if changed:
                    updated += 1
                else:
                    skipped += 1
                continue
            if not args.dry_run:
                _import_candidate(
                    session,
                    repository,
                    candidate,
                    catalog,
                    registry,
                    dictionary,
                )
            imported += 1
        if not args.dry_run:
            session.commit()
    print(
        "candidate revisions: "
        f"imported={imported}, updated={updated}, skipped={skipped}, dry_run={args.dry_run}"
    )
    return 0


def _select_candidates(
    candidates: list[dict[str, Any]],
    *,
    candidate_ids: list[str] | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    if limit is not None and limit < 1:
        raise ValueError("--limit must be positive")
    selected = candidates
    if candidate_ids:
        requested = set(candidate_ids)
        selected = [item for item in candidates if item.get("candidate_id") in requested]
        missing = requested - {str(item.get("candidate_id")) for item in selected}
        if missing:
            raise ValueError(f"unknown candidate IDs: {', '.join(sorted(missing))}")
    if limit is not None:
        selected = selected[:limit]
    if not selected:
        raise ValueError("candidate selection is empty")
    return selected


def _import_candidate(
    session: Session,
    repository: SqlAlchemyPlaceCatalogRepository,
    candidate: dict[str, Any],
    catalog: dict[str, Any],
    registry: dict[str, Any],
    dictionary: dict[str, Any],
) -> None:
    candidate_id = str(candidate["candidate_id"])
    place_id = f"place-{candidate_id}"
    source_record_id = f"source-{candidate_id}"
    revision_id = f"revision-{candidate_id}"
    geometry_id = f"geometry-{candidate_id}"
    provider = candidate["provider_candidate"]
    coverage = candidate["coverage"]
    observed_at = datetime.fromisoformat(provider["observed_at"])

    if repository.get_place(place_id) is None:
        now = observed_at
        repository.add_place(
            Place(
                place_id=place_id,
                city_id=str(catalog["city_id"]),
                status="active",
                created_at=now,
                updated_at=now,
            )
        )

    repository.add_source_record(
        PlaceSourceRecord(
            source_record_id=source_record_id,
            place_id=place_id,
            source_id=str(catalog["collection_policy"]["source_id"]),
            registry_id=str(catalog["source_registry"]["registry_id"]),
            registry_sha256=str(catalog["source_registry"]["registry_sha256"]),
            field_dictionary_id=str(catalog["field_dictionary"]["dictionary_id"]),
            field_dictionary_sha256=str(catalog["field_dictionary"]["dictionary_sha256"]),
            source_url=GAODE_SOURCE_URL,
            collection_mode=str(catalog["collection_policy"]["collection_mode"]),
            target_stage="staging",
            source_decision="approved",
            observed_at=observed_at,
            content_sha256=None,
            status="active",
            created_at=observed_at,
        )
    )
    repository.add_revision(
        PlaceRevision(
            place_revision_id=revision_id,
            place_id=place_id,
            revision_number=1,
            lifecycle_status="candidate",
            canonical_name=str(candidate["canonical_name_candidate"]),
            aliases=(),
            place_kind=str(candidate["place_kind_candidate"]),
            category=str(candidate["primary_category"]),
            admin_area=str(provider.get("admin_area") or "杭州市"),
            address=str(provider.get("address") or "候选地址待核验"),
            geometry_kind=str(candidate["geometry_kind_candidate"]),
            duration_min=1,
            duration_recommended=1,
            duration_max=1,
            internal_travel_min=0,
            energy_level=3,
            indoor_outdoor="mixed" if coverage["indoor_or_rain"] else "outdoor",
            suitable_periods=tuple(str(item) for item in coverage["suitable_periods"]),
            audience_tags=tuple(str(item) for item in coverage["audiences"]),
            rain_suitability="suitable" if coverage["indoor_or_rain"] else "conditional",
            is_always_open=False,
            solver_eligible=False,
            conflicts_resolved=False,
            source_record_ids=(source_record_id,),
            created_at=observed_at,
            review_flags=tuple(str(flag) for flag in candidate["review_flags"]),
            relation_review_status="pending",
        )
    )
    location = provider["location"]
    repository.add_geometry(
        PlaceGeometry(
            geometry_id=geometry_id,
            place_revision_id=revision_id,
            geometry_kind=str(candidate["geometry_kind_candidate"]),
            geometry={
                "kind": "provider_candidate_point",
                "lat": float(location["lat"]),
                "lng": float(location["lng"]),
            },
            source_record_id=source_record_id,
            review_status="candidate",
            active=True,
            created_at=observed_at,
            reviewed_at=None,
        )
    )
    session.flush()


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
