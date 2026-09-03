"""Deterministic solver projection hashing and fail-closed publication gates."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from .entities import (
    Place,
    PlaceAccessPoint,
    PlaceGeometry,
    PlaceRelation,
    PlaceRevision,
    PlaceSourceRecord,
    PlaceTimeRule,
    SolverPlaceProjection,
)

SUPPORTED_GEOMETRIES = {
    "attraction": frozenset({"point"}),
    "scenic_area": frozenset({"area"}),
    "neighborhood": frozenset({"area"}),
    "walking_route": frozenset({"route"}),
    "market": frozenset({"point", "area"}),
    "show": frozenset({"point"}),
    "experience": frozenset({"point", "area"}),
}


class ProjectionPublicationError(ValueError):
    """A candidate projection failed one or more stable publication gates."""

    def __init__(self, reason_codes: tuple[str, ...]) -> None:
        self.reason_codes = reason_codes
        super().__init__("projection cannot be published: " + ", ".join(reason_codes))


@dataclass(frozen=True, slots=True)
class ProjectionPublicationContext:
    place: Place
    revision: PlaceRevision
    source_records: tuple[PlaceSourceRecord, ...]
    geometries: tuple[PlaceGeometry, ...]
    access_points: tuple[PlaceAccessPoint, ...]
    time_rules: tuple[PlaceTimeRule, ...]
    relations: tuple[PlaceRelation, ...]
    projection: SolverPlaceProjection


def canonical_projection_sha256(projection: SolverPlaceProjection) -> str:
    """Hash only immutable solver inputs, not workflow status or timestamps."""

    payload: dict[str, Any] = {
        "projection_version": projection.projection_version,
        "data_snapshot_version": projection.data_snapshot_version,
        "place_id": projection.place_id,
        "place_revision_id": projection.place_revision_id,
        "solver_node_id": projection.solver_node_id,
        "place_kind": projection.place_kind,
        "geometry_kind": projection.geometry_kind,
        "arrival_access_point_id": projection.arrival_access_point_id,
        "departure_access_point_id": projection.departure_access_point_id,
        "duration_min": projection.duration_min,
        "duration_recommended": projection.duration_recommended,
        "duration_max": projection.duration_max,
        "internal_travel_min": projection.internal_travel_min,
        "solver_payload": projection.solver_payload,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def has_source_content_conflict(
    source_records: tuple[PlaceSourceRecord, ...],
) -> bool:
    """Return whether one governed source has multiple distinct content versions."""

    fingerprints_by_source: dict[str, set[str]] = {}
    for record in source_records:
        fingerprints_by_source.setdefault(record.source_id, set()).add(
            record.content_sha256 or record.registry_sha256
        )
    return any(len(fingerprints) > 1 for fingerprints in fingerprints_by_source.values())


def evaluate_projection_publication(
    context: ProjectionPublicationContext,
) -> tuple[str, ...]:
    """Return stable, sorted reason codes; an empty tuple means publishable."""

    place = context.place
    revision = context.revision
    projection = context.projection
    reasons: set[str] = set()

    if place.status != "active":
        reasons.add("PLACE_NOT_ACTIVE")
    if revision.lifecycle_status not in {"human_verified", "published"}:
        reasons.add("REVISION_NOT_HUMAN_VERIFIED")
    if not revision.solver_eligible:
        reasons.add("PLACE_NOT_SOLVER_ELIGIBLE")
    if projection.status == "retired":
        reasons.add("PROJECTION_NOT_ACTIVE")
    if projection.place_id != place.place_id or revision.place_id != place.place_id:
        reasons.add("PROJECTION_PLACE_MISMATCH")
    if projection.place_revision_id != revision.place_revision_id:
        reasons.add("PROJECTION_REVISION_MISMATCH")
    if revision.place_kind != projection.place_kind:
        reasons.add("PROJECTION_PLACE_KIND_MISMATCH")
    if revision.geometry_kind != projection.geometry_kind:
        reasons.add("PROJECTION_GEOMETRY_KIND_MISMATCH")
    if revision.geometry_kind not in SUPPORTED_GEOMETRIES.get(revision.place_kind, frozenset()):
        reasons.add("UNSUPPORTED_PLACE_KIND")
    if (
        projection.duration_min,
        projection.duration_recommended,
        projection.duration_max,
        projection.internal_travel_min,
    ) != (
        revision.duration_min,
        revision.duration_recommended,
        revision.duration_max,
        revision.internal_travel_min,
    ):
        reasons.add("PROJECTION_DURATION_MISMATCH")

    # Source IDs are only globally unique, while the facts they support are
    # scoped to a Place.  Keep the global lookup separate from the usable
    # current-Place set so an existing source from another Place is reported
    # as a provenance mismatch instead of being treated as a valid source (or
    # silently disappearing as a missing one).
    source_records_by_id = {
        record.source_record_id: record for record in context.source_records
    }
    active_source_records = {
        record.source_record_id: record
        for record in context.source_records
        if record.status == "active"
    }
    source_record_ids = tuple(
        dict.fromkeys(
            (
                *revision.source_record_ids,
                *(geometry.source_record_id for geometry in context.geometries),
                *(point.source_record_id for point in context.access_points),
                *(rule.source_record_id for rule in context.time_rules),
                *(relation.source_record_id for relation in context.relations),
            )
        )
    )
    if any(
        source_record_id in source_records_by_id
        and source_records_by_id[source_record_id].place_id != place.place_id
        for source_record_id in source_record_ids
    ):
        reasons.add("SOURCE_RECORD_PLACE_MISMATCH")

    source_records = {
        source_record_id: record
        for source_record_id, record in active_source_records.items()
        if record.place_id == place.place_id
    }
    if not revision.source_record_ids or any(
        source_record_id not in active_source_records
        for source_record_id in revision.source_record_ids
    ):
        reasons.add("MISSING_SOURCE_RECORD")

    verified_geometries = [
        geometry
        for geometry in context.geometries
        if geometry.active
        and geometry.review_status == "human_verified"
        and geometry.geometry_kind == revision.geometry_kind
        and geometry.source_record_id in source_records
    ]
    if not verified_geometries:
        reasons.add("MISSING_VERIFIED_GEOMETRY")

    access_points = {
        point.access_point_id: point
        for point in context.access_points
        if point.active
    }
    arrival = access_points.get(projection.arrival_access_point_id)
    departure = access_points.get(projection.departure_access_point_id)
    if arrival is None:
        reasons.add("MISSING_ARRIVAL_ACCESS_POINT")
    if departure is None:
        reasons.add("MISSING_DEPARTURE_ACCESS_POINT")
    for point in (arrival, departure):
        if point is None:
            continue
        if point.place_revision_id != revision.place_revision_id:
            reasons.add("ACCESS_POINT_REVISION_MISMATCH")
        if (
            point.review_status != "human_verified"
            or point.reviewed_at is None
            or point.source_record_id not in source_records
        ):
            reasons.add("ACCESS_POINT_NOT_HUMAN_VERIFIED")

    verified_rules = [
        rule
        for rule in context.time_rules
        if rule.active
        and rule.review_status == "human_verified"
        and rule.source_record_id in source_records
    ]
    if not revision.is_always_open and not verified_rules:
        reasons.add("TIME_RULE_UNRESOLVED")
    fixed_sessions = [rule for rule in verified_rules if rule.rule_kind == "fixed_session"]
    if revision.place_kind == "show":
        if not fixed_sessions:
            # A show is scheduled around a concrete session, not a generic
            # opening-hours window. Keep this reason distinct so operators
            # can correct the rule kind instead of chasing a false missing
            # verification warning.
            reasons.add("FIXED_SESSION_REQUIRED")
        elif len(fixed_sessions) != 1:
            reasons.add("FIXED_SESSION_AMBIGUOUS")

    if has_source_content_conflict(context.source_records) and not revision.conflicts_resolved:
        reasons.add("SOURCE_CONFLICT_UNRESOLVED")
    if any(
        relation.active
        and relation.relation_type in {"overlaps", "same_experience"}
        and relation.resolution_status == "pending"
        for relation in context.relations
    ):
        reasons.add("OVERLAPPING_SELECTION_UNRESOLVED")
    if (
        revision.relation_review_status == "pending"
        and not any(relation.active for relation in context.relations)
    ):
        reasons.add("RELATION_REVIEW_REQUIRED")
    if canonical_projection_sha256(projection) != projection.projection_hash:
        reasons.add("PROJECTION_HASH_MISMATCH")

    return tuple(sorted(reasons))


def publish_projection(
    context: ProjectionPublicationContext,
    *,
    published_at: datetime,
) -> tuple[PlaceRevision, SolverPlaceProjection]:
    """Return immutable published objects only after all dependency gates pass."""

    if published_at.tzinfo is None:
        raise ValueError("projection published_at must be timezone-aware")
    reasons = evaluate_projection_publication(context)
    if reasons:
        raise ProjectionPublicationError(reasons)
    revision = replace(
        context.revision,
        lifecycle_status="published",
        published_at=published_at,
    )
    projection = replace(
        context.projection,
        status="published",
        gate_reason_codes=(),
        published_at=published_at,
    )
    return revision, projection
