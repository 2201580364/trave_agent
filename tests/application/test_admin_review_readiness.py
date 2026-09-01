from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

from travel_agent.application.admin.review import _review_readiness
from travel_agent.domain.place_catalog import (
    PlaceAccessPoint,
    PlaceClosure,
    PlaceDateException,
    PlaceGeometry,
    PlaceRelation,
    PlaceReviewTask,
    PlaceRevision,
    PlaceRevisionEvidence,
    PlaceSourceRecord,
    PlaceTimeRule,
)

NOW = datetime(2026, 9, 1, 8, tzinfo=UTC)
SOURCE_ID = "source-1"


def _source(*, status: str = "active") -> PlaceSourceRecord:
    return PlaceSourceRecord(
        SOURCE_ID,
        "place-1",
        "official-public-page",
        "registry-v1",
        "a" * 64,
        "field-dictionary-v1",
        "b" * 64,
        "https://example.com/place-1",
        "manual_reference",
        "staging",
        "conditional",
        NOW,
        "c" * 64,
        status,
        NOW,
    )


def _revision(**changes: object) -> PlaceRevision:
    base = PlaceRevision(
        "revision-1",
        "place-1",
        1,
        "candidate",
        "示例地点",
        (),
        "attraction",
        "landmark",
        "杭州市西湖区",
        "示例地址",
        "point",
        60,
        90,
        120,
        0,
        2,
        "outdoor",
        ("morning", "afternoon"),
        ("general",),
        "conditional",
        False,
        False,
        True,
        (SOURCE_ID,),
        NOW,
        review_flags=(),
        relation_review_status="no_relations",
    )
    return replace(base, **changes)


def _geometry(*, source_record_id: str = SOURCE_ID) -> PlaceGeometry:
    return PlaceGeometry(
        "geometry-1",
        "revision-1",
        "point",
        {"type": "Point", "coordinates": [120.15, 30.25]},
        source_record_id,
        "human_verified",
        True,
        NOW,
        NOW,
    )


def _access_point(*, source_record_id: str = SOURCE_ID) -> PlaceAccessPoint:
    return PlaceAccessPoint(
        "access-1",
        "revision-1",
        "visitor_entrance",
        "游客入口",
        Decimal("30.25"),
        Decimal("120.15"),
        source_record_id,
        "human_verified",
        True,
        NOW,
        NOW,
        NOW,
    )


def _time_rule(
    *,
    rule_kind: str = "opening_hours",
    review_status: str = "human_verified",
    source_record_id: str = SOURCE_ID,
) -> PlaceTimeRule:
    return PlaceTimeRule(
        "time-rule-1",
        "revision-1",
        rule_kind,
        (1, 2, 3, 4, 5, 6, 7),
        9 * 60,
        17 * 60,
        None,
        date(2026, 1, 1),
        None,
        source_record_id,
        review_status,
        True,
        NOW,
        NOW if review_status == "human_verified" else None,
    )


def _evidence(
    *,
    revision: PlaceRevision | None = None,
    sources: tuple[PlaceSourceRecord, ...] | None = None,
    geometries: tuple[PlaceGeometry, ...] | None = None,
    access_points: tuple[PlaceAccessPoint, ...] | None = None,
    time_rules: tuple[PlaceTimeRule, ...] | None = None,
    closures: tuple[PlaceClosure, ...] = (),
    date_exceptions: tuple[PlaceDateException, ...] = (),
    relations: tuple[PlaceRelation, ...] = (),
) -> PlaceRevisionEvidence:
    return PlaceRevisionEvidence(
        revision=revision or _revision(),
        source_records=(_source(),) if sources is None else sources,
        geometries=(_geometry(),) if geometries is None else geometries,
        access_points=(_access_point(),) if access_points is None else access_points,
        time_rules=(_time_rule(),) if time_rules is None else time_rules,
        closures=closures,
        date_exceptions=date_exceptions,
        projection=None,
        relations=relations,
    )


def _task(status: str) -> PlaceReviewTask:
    return PlaceReviewTask("task-1", "revision-1", status, None, 1, "editor-1", NOW, NOW)


def _check(result: dict[str, object], key: str) -> dict[str, object]:
    return next(item for item in result["checks"] if item["key"] == key)  # type: ignore[index,union-attr]


def test_complete_evidence_without_task_is_ready_to_submit_not_ready_to_approve() -> None:
    result = _review_readiness(_evidence(), None)

    assert result["completed_checks"] == 6
    assert result["verified_checks"] == 6
    assert result["status"] == "ready_for_review"


def test_complete_evidence_in_review_is_ready_for_approval() -> None:
    result = _review_readiness(_evidence(), _task("in_review"))

    assert result["status"] == "ready_for_approval"


def test_changes_requested_takes_precedence_over_previously_verified_evidence() -> None:
    result = _review_readiness(_evidence(), _task("changes_requested"))

    assert result["status"] == "changes_requested"


def test_always_open_needs_no_time_rule_but_still_requires_time_exceptions_reviewed() -> None:
    always_open = _revision(is_always_open=True)
    without_rules = _review_readiness(
        _evidence(revision=always_open, time_rules=()),
        None,
    )
    assert _check(without_rules, "time")["verified"] is True

    pending_closure = PlaceClosure(
        "closure-1",
        "revision-1",
        1,
        SOURCE_ID,
        "candidate",
        True,
        NOW,
    )
    with_pending_closure = _review_readiness(
        _evidence(revision=always_open, time_rules=(), closures=(pending_closure,)),
        None,
    )
    assert _check(with_pending_closure, "time")["collected"] is True
    assert _check(with_pending_closure, "time")["verified"] is False
    assert "time" in with_pending_closure["pending_review_checks"]


def test_show_requires_exactly_one_fixed_session() -> None:
    show = _revision(place_kind="show")
    only_opening_hours = _review_readiness(_evidence(revision=show), None)
    assert _check(only_opening_hours, "time")["collected"] is False

    fixed_session = replace(_time_rule(), rule_kind="fixed_session")
    one_session = _review_readiness(
        _evidence(revision=show, time_rules=(fixed_session,)),
        None,
    )
    assert _check(one_session, "time")["verified"] is True

    second_session = replace(fixed_session, time_rule_id="time-rule-2")
    two_sessions = _review_readiness(
        _evidence(revision=show, time_rules=(fixed_session, second_session)),
        None,
    )
    assert _check(two_sessions, "time")["collected"] is False


def test_active_child_evidence_with_inactive_source_is_not_ready() -> None:
    missing_source_id = "source-missing"
    result = _review_readiness(
        _evidence(
            geometries=(_geometry(source_record_id=missing_source_id),),
            access_points=(_access_point(source_record_id=missing_source_id),),
            time_rules=(_time_rule(source_record_id=missing_source_id),),
        ),
        None,
    )

    assert result["status"] == "needs_evidence"
    assert {"geometry", "access_point", "time"}.issubset(result["missing_checks"])


def test_active_relation_must_be_resolved_and_human_verified() -> None:
    pending = PlaceRelation(
        "relation-1",
        "place-1",
        "place-2",
        "overlaps",
        SOURCE_ID,
        "candidate",
        "pending",
        None,
        True,
        NOW,
    )
    pending_result = _review_readiness(_evidence(relations=(pending,)), None)
    assert _check(pending_result, "relation")["collected"] is False

    resolved = replace(
        pending,
        resolution_status="resolved",
        decision_note="两个地点可分别选择",
    )
    resolved_result = _review_readiness(_evidence(relations=(resolved,)), None)
    assert _check(resolved_result, "relation")["collected"] is True
    assert _check(resolved_result, "relation")["verified"] is False

    verified = replace(resolved, review_status="human_verified", reviewed_at=NOW)
    verified_result = _review_readiness(_evidence(relations=(verified,)), None)
    assert _check(verified_result, "relation")["verified"] is True
