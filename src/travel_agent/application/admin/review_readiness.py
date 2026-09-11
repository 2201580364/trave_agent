"""Pure OM1 review readiness evaluation (H3, transformation-plan S7-1)."""

from __future__ import annotations

from travel_agent.domain.place_catalog import (
    PlaceReviewTask,
    PlaceRevisionEvidence,
    has_source_content_conflict,
)
from travel_agent.domain.place_catalog.session_payload import valid_session_timing


def evaluate_review_readiness(
    evidence: PlaceRevisionEvidence,
    task: PlaceReviewTask | None,
) -> dict[str, object]:
    """Summarize the six editor/reviewer checks used by the OM1 workbench."""

    revision = evidence.revision
    active_source_ids = {
        source.source_record_id for source in evidence.source_records if source.status == "active"
    }
    active_dependency_sources = set(revision.source_record_ids) | {
        item.source_record_id
        for items in (
            evidence.geometries,
            evidence.access_points,
            evidence.time_rules,
            evidence.closures,
            evidence.date_exceptions,
            evidence.relations,
        )
        for item in items
        if item.active
    }
    inactive_only_sources = {
        item.source_record_id
        for items in (
            evidence.geometries,
            evidence.access_points,
            evidence.time_rules,
            evidence.closures,
            evidence.date_exceptions,
            evidence.relations,
        )
        for item in items
        if not item.active
    } - active_dependency_sources
    relevant_sources = tuple(
        item
        for item in evidence.source_records
        if item.source_record_id not in inactive_only_sources
    )
    source_collected = bool(revision.source_record_ids) and not (
        set(revision.source_record_ids) & set(evidence.missing_source_record_ids)
    )
    source_collected = source_collected and all(
        source_id in active_source_ids for source_id in revision.source_record_ids
    )
    source_collected = source_collected and (
        not has_source_content_conflict(relevant_sources) or revision.conflicts_resolved
    )

    blocking_fact_flags = {
        "NAME_REQUIRES_HUMAN_VERIFICATION",
        "CATEGORY_REQUIRES_HUMAN_VERIFICATION",
        "DURATION_NOT_COLLECTED",
    }
    basic_collected = revision.lifecycle_status in {"human_verified", "published"} or not any(
        flag in blocking_fact_flags for flag in revision.review_flags
    )

    active_geometries = tuple(item for item in evidence.geometries if item.active)
    geometry_sources_valid = all(
        item.source_record_id in active_source_ids for item in active_geometries
    )
    matching_geometries = tuple(
        item
        for item in active_geometries
        if item.geometry_kind == revision.geometry_kind
        and item.source_record_id in active_source_ids
    )
    provider_point_only = "PROVIDER_POINT_IS_NOT_PLACE_GEOMETRY" in revision.review_flags
    geometry_collected = (
        bool(matching_geometries) and geometry_sources_valid and not provider_point_only
    )
    verified_geometries = sum(
        item.review_status == "human_verified" and item.source_record_id in active_source_ids
        for item in active_geometries
    )
    geometry_verified = (
        geometry_collected
        and verified_geometries == len(active_geometries)
        and any(item.review_status == "human_verified" for item in matching_geometries)
    )

    active_access_points = tuple(item for item in evidence.access_points if item.active)
    access_sources_valid = all(
        item.source_record_id in active_source_ids for item in active_access_points
    )
    usable_access_points = tuple(
        item for item in active_access_points if item.source_record_id in active_source_ids
    )
    access_collected = bool(usable_access_points) and access_sources_valid
    verified_access_points = sum(
        item.review_status == "human_verified" and item.source_record_id in active_source_ids
        for item in active_access_points
    )
    access_verified = access_collected and verified_access_points == len(active_access_points)

    active_time_rules = tuple(item for item in evidence.time_rules if item.active)
    active_time_children = (
        *active_time_rules,
        *(item for item in evidence.closures if item.active),
        *(item for item in evidence.date_exceptions if item.active),
    )
    time_sources_valid = all(
        item.source_record_id in active_source_ids for item in active_time_children
    )
    usable_time_rules = tuple(
        item for item in active_time_rules if item.source_record_id in active_source_ids
    )
    fixed_sessions = tuple(item for item in usable_time_rules if item.rule_kind == "fixed_session")
    time_collected = (revision.is_always_open or bool(usable_time_rules)) and time_sources_valid
    if revision.place_kind == "show":
        time_collected = (
            time_collected
            and bool(fixed_sessions)
            and all(
                valid_session_timing(item.start_minute, item.end_minute, item.last_entry_minute)
                for item in (
                    *fixed_sessions,
                    *(
                        e
                        for e in evidence.date_exceptions
                        if e.active and e.exception_kind == "session_override"
                    ),
                )
            )
        )
    verified_time_children = sum(
        item.review_status == "human_verified" and item.source_record_id in active_source_ids
        for item in active_time_children
    )
    time_verified = time_collected and verified_time_children == len(active_time_children)
    if not revision.is_always_open:
        time_verified = time_verified and bool(active_time_rules)

    active_relations = tuple(item for item in evidence.relations if item.active)
    relation_sources_valid = all(
        item.source_record_id in active_source_ids for item in active_relations
    )
    relation_collected = (
        relation_sources_valid
        and all(item.resolution_status != "pending" for item in active_relations)
        if active_relations
        else revision.relation_review_status in {"no_relations", "not_required"}
    )
    verified_relations = sum(
        item.review_status == "human_verified" and item.source_record_id in active_source_ids
        for item in active_relations
    )
    relation_verified = relation_collected and verified_relations == len(active_relations)

    checks = (
        _readiness_check("basic", basic_collected, basic_collected, 1, int(basic_collected)),
        _readiness_check(
            "source",
            source_collected,
            source_collected,
            len(revision.source_record_ids),
            len(revision.source_record_ids) if source_collected else 0,
        ),
        _readiness_check(
            "geometry",
            geometry_collected,
            geometry_verified,
            len(active_geometries),
            verified_geometries,
        ),
        _readiness_check(
            "access_point",
            access_collected,
            access_verified,
            len(active_access_points),
            verified_access_points,
        ),
        _readiness_check(
            "time",
            time_collected,
            time_verified,
            len(active_time_children),
            verified_time_children,
        ),
        _readiness_check(
            "relation",
            relation_collected,
            relation_verified,
            len(active_relations) or 1,
            verified_relations if active_relations else int(relation_verified),
        ),
    )
    completed_checks = sum(bool(check["collected"]) for check in checks)
    verified_checks = sum(bool(check["verified"]) for check in checks)
    total_checks = len(checks)
    if revision.lifecycle_status != "candidate":
        status = revision.lifecycle_status
    elif task is not None and task.status == "changes_requested":
        status = "changes_requested"
    elif task is not None:
        status = "ready_for_approval" if verified_checks == total_checks else "under_review"
    elif completed_checks == total_checks:
        status = "ready_for_review"
    else:
        status = "needs_evidence"
    return {
        "status": status,
        "completed_checks": completed_checks,
        "verified_checks": verified_checks,
        "total_checks": total_checks,
        "missing_checks": tuple(str(check["key"]) for check in checks if not check["collected"]),
        "pending_review_checks": tuple(
            str(check["key"]) for check in checks if check["collected"] and not check["verified"]
        ),
        "task_status": task.status if task is not None else None,
        "checks": checks,
    }


def _readiness_check(
    key: str,
    collected: bool,
    verified: bool,
    total: int,
    verified_count: int,
) -> dict[str, object]:
    return {
        "key": key,
        "collected": collected,
        "verified": verified,
        "total": total,
        "verified_count": verified_count,
    }
