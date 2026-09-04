"""G7-R0.2-03 place catalog, publication gate and persistence tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from travel_agent.domain.place_catalog import (
    Place,
    PlaceAccessPoint,
    PlaceClosure,
    PlaceDateException,
    PlaceGeometry,
    PlaceRelation,
    PlaceRevision,
    PlaceSourceRecord,
    PlaceTimeRule,
    ProjectionPublicationContext,
    ProjectionPublicationError,
    SelectionExclusionGroup,
    SelectionExclusionMember,
    SolverPlaceProjection,
    canonical_projection_sha256,
    evaluate_projection_publication,
    publish_projection,
)
from travel_agent.infrastructure.database import SqlAlchemyUnitOfWork, create_schema

NOW = datetime(2026, 8, 29, 6, tzinfo=UTC)
REGISTRY_HASH = "a" * 64
DICTIONARY_HASH = "b" * 64


def _place(place_id: str = "place_westlake") -> Place:
    return Place(place_id, "hangzhou", "active", NOW, NOW)


def _source(place_id: str = "place_westlake") -> PlaceSourceRecord:
    return PlaceSourceRecord(
        "source_westlake_1",
        place_id,
        "hangzhou-westlake-admin-public-web",
        "hangzhou-m1-source-registry-v1",
        REGISTRY_HASH,
        "m1-place-collection-fields-v1",
        DICTIONARY_HASH,
        "https://westlake.hangzhou.gov.cn/example",
        "manual_reference",
        "staging",
        "conditional",
        NOW,
        "c" * 64,
        "active",
        NOW,
    )


def _revision(place_id: str = "place_westlake") -> PlaceRevision:
    return PlaceRevision(
        "place_revision_westlake_1",
        place_id,
        1,
        "human_verified",
        "西湖示例景点",
        ("示例别名",),
        "attraction",
        "landmark",
        "杭州市西湖区",
        "示例地址",
        "point",
        60,
        90,
        150,
        0,
        2,
        "outdoor",
        ("morning", "afternoon"),
        ("general",),
        "conditional",
        False,
        True,
        True,
        ("source_westlake_1",),
        NOW,
        NOW,
    )


def _geometry() -> PlaceGeometry:
    return PlaceGeometry(
        "geometry_westlake_1",
        "place_revision_westlake_1",
        "point",
        {"type": "Point", "coordinates": [120.15, 30.25]},
        "source_westlake_1",
        "human_verified",
        True,
        NOW,
        NOW,
    )


def _access_points(*, verified: bool = True) -> tuple[PlaceAccessPoint, ...]:
    status = "human_verified" if verified else "candidate"
    reviewed_at = NOW if verified else None
    return (
        PlaceAccessPoint(
            "access_westlake_arrival",
            "place_revision_westlake_1",
            "visitor_entrance",
            "游客入口",
            Decimal("30.2500000"),
            Decimal("120.1500000"),
            "source_westlake_1",
            status,
            True,
            NOW,
            reviewed_at,
            NOW,
        ),
        PlaceAccessPoint(
            "access_westlake_departure",
            "place_revision_westlake_1",
            "visitor_exit",
            "游客出口",
            Decimal("30.2510000"),
            Decimal("120.1510000"),
            "source_westlake_1",
            status,
            True,
            NOW,
            reviewed_at,
            NOW,
        ),
    )


def _time_rule(rule_id: str = "time_westlake_1") -> PlaceTimeRule:
    return PlaceTimeRule(
        rule_id,
        "place_revision_westlake_1",
        "opening_hours",
        (1, 2, 3, 4, 5, 6, 7),
        9 * 60,
        17 * 60,
        16 * 60 + 30,
        date(2026, 1, 1),
        None,
        "source_westlake_1",
        "human_verified",
        True,
        NOW,
        NOW,
    )


def _projection() -> SolverPlaceProjection:
    candidate = SolverPlaceProjection(
        "projection_westlake_1",
        "solver-place-projection-v1",
        "hangzhou-candidate-2026-08-29-v1",
        "place_westlake",
        "place_revision_westlake_1",
        101,
        "attraction",
        "point",
        "access_westlake_arrival",
        "access_westlake_departure",
        60,
        90,
        150,
        0,
        {
            "attraction_id": "place_westlake",
            "name": "西湖示例景点",
            "data_verified": True,
        },
        "0" * 64,
        "candidate",
        (),
        NOW,
    )
    return replace(candidate, projection_hash=canonical_projection_sha256(candidate))


def _context(
    *,
    access_points: tuple[PlaceAccessPoint, ...] | None = None,
    relations: tuple[PlaceRelation, ...] = (),
    projection: SolverPlaceProjection | None = None,
) -> ProjectionPublicationContext:
    return ProjectionPublicationContext(
        _place(),
        _revision(),
        (_source(),),
        (_geometry(),),
        access_points if access_points is not None else _access_points(),
        (_time_rule(),),
        relations,
        projection or _projection(),
    )


def test_conditional_source_record_is_staging_only() -> None:
    with pytest.raises(ValueError, match="staging only"):
        replace(_source(), target_stage="published")


def test_projection_hash_is_stable_and_ignores_workflow_status() -> None:
    projection = _projection()
    reordered = replace(
        projection,
        solver_payload={
            "data_verified": True,
            "name": "西湖示例景点",
            "attraction_id": "place_westlake",
        },
        gate_reason_codes=("OLD_REASON",),
    )

    assert canonical_projection_sha256(projection) == projection.projection_hash
    assert canonical_projection_sha256(reordered) == projection.projection_hash


def test_complete_human_verified_projection_passes_and_publishes_immutably() -> None:
    context = _context()

    assert evaluate_projection_publication(context) == ()

    revision, projection = publish_projection(context, published_at=NOW)

    assert context.revision.lifecycle_status == "human_verified"
    assert context.projection.status == "candidate"
    assert revision.lifecycle_status == "published"
    assert projection.status == "published"
    assert projection.projection_hash == context.projection.projection_hash


def test_gate_does_not_require_conflict_confirmation_when_no_conflict_exists() -> None:
    context = replace(
        _context(),
        revision=replace(_revision(), conflicts_resolved=False),
    )

    assert "SOURCE_CONFLICT_UNRESOLVED" not in evaluate_projection_publication(context)


def test_gate_rejects_an_actual_unresolved_source_conflict() -> None:
    conflicting_source = replace(
        _source(),
        source_record_id="source_westlake_2",
        content_sha256="d" * 64,
    )
    context = replace(
        _context(),
        revision=replace(_revision(), conflicts_resolved=False),
        source_records=(_source(), conflicting_source),
    )

    assert "SOURCE_CONFLICT_UNRESOLVED" in evaluate_projection_publication(context)


def test_gate_rejects_source_record_belonging_to_another_place() -> None:
    cross_place_source = _source("place_other")
    context = replace(_context(), source_records=(cross_place_source,))

    reasons = evaluate_projection_publication(context)

    assert "SOURCE_RECORD_PLACE_MISMATCH" in reasons
    # The source exists and is active; the failure is its Place ownership, not
    # an absent source record.
    assert "MISSING_SOURCE_RECORD" not in reasons


def test_gate_rejects_unverified_access_hash_drift_and_overlap() -> None:
    relation = PlaceRelation(
        "relation_overlap_1",
        "place_westlake",
        "place_child",
        "same_experience",
        "source_westlake_1",
        "human_verified",
        "pending",
        None,
        True,
        NOW,
        NOW,
    )
    drifted = replace(_projection(), solver_payload={"name": "changed"})
    reasons = evaluate_projection_publication(
        _context(
            access_points=_access_points(verified=False),
            relations=(relation,),
            projection=drifted,
        )
    )

    assert "ACCESS_POINT_NOT_HUMAN_VERIFIED" in reasons
    assert "OVERLAPPING_SELECTION_UNRESOLVED" in reasons
    assert "PROJECTION_HASH_MISMATCH" in reasons


def test_show_with_multiple_fixed_sessions_is_rejected() -> None:
    revision = replace(
        _revision(),
        place_kind="show",
        duration_min=30,
        duration_recommended=30,
        duration_max=30,
    )
    projection = replace(
        _projection(),
        place_kind="show",
        duration_min=30,
        duration_recommended=30,
        duration_max=30,
    )
    projection = replace(projection, projection_hash=canonical_projection_sha256(projection))
    sessions = tuple(
        replace(
            _time_rule(f"session_{start}"),
            rule_kind="fixed_session",
            start_minute=start,
            end_minute=start + 30,
            last_entry_minute=None,
        )
        for start in (18 * 60 + 30, 19 * 60 + 30)
    )
    context = replace(_context(projection=projection), revision=revision, time_rules=sessions)

    assert "FIXED_SESSION_AMBIGUOUS" in evaluate_projection_publication(context)


def test_show_with_only_opening_hours_requires_a_fixed_session() -> None:
    revision = replace(_revision(), place_kind="show")
    projection = replace(_projection(), place_kind="show")
    projection = replace(projection, projection_hash=canonical_projection_sha256(projection))
    context = replace(
        _context(projection=projection),
        revision=revision,
        time_rules=(replace(_time_rule("opening-hours"), rule_kind="opening_hours"),),
    )

    reasons = evaluate_projection_publication(context)

    assert "FIXED_SESSION_REQUIRED" in reasons
    assert "TIME_RULE_UNRESOLVED" not in reasons


def test_sqlalchemy_catalog_persists_and_only_gate_can_publish(tmp_path: Path) -> None:
    database = tmp_path / "catalog.db"
    engine = create_engine(f"sqlite:///{database}")
    create_schema(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    with SqlAlchemyUnitOfWork(factory) as uow:
        uow.place_catalog.add_place(_place())
        uow.place_catalog.add_source_record(_source())
        uow.place_catalog.add_revision(_revision())
        uow.place_catalog.add_geometry(_geometry())
        for point in _access_points():
            uow.place_catalog.add_access_point(point)
        uow.place_catalog.add_time_rule(_time_rule())
        uow.place_catalog.add_closure(
            PlaceClosure(
                "closure_westlake_monday",
                "place_revision_westlake_1",
                1,
                "source_westlake_1",
                "human_verified",
                True,
                NOW,
                NOW,
            )
        )
        uow.place_catalog.add_date_exception(
            PlaceDateException(
                "exception_westlake_2026_10_01",
                "place_revision_westlake_1",
                date(2026, 10, 1),
                "open_override",
                8 * 60,
                18 * 60,
                17 * 60 + 30,
                "source_westlake_1",
                "human_verified",
                True,
                NOW,
                NOW,
            )
        )
        uow.place_catalog.add_place(_place("place_child"))
        uow.place_catalog.add_relation(
            PlaceRelation(
                "relation_westlake_child",
                "place_westlake",
                "place_child",
                "contains",
                "source_westlake_1",
                "human_verified",
                "resolved",
                "父子地点边界已人工裁决。",
                True,
                NOW,
                NOW,
            )
        )
        uow.place_catalog.add_exclusion_group(
            SelectionExclusionGroup(
                "group_westlake_overlap",
                "hangzhou",
                "西湖重叠体验",
                "active",
                "human_verified",
                "同一游览体验不能重复选择。",
                NOW,
                NOW,
            )
        )
        uow.place_catalog.add_exclusion_member(
            SelectionExclusionMember("group_westlake_overlap", "place_westlake", NOW)
        )
        uow.place_catalog.add_projection(_projection())
        published = uow.place_catalog.publish_projection(
            "projection_westlake_1", published_at=NOW
        )
        uow.commit()

    assert published.status == "published"
    with SqlAlchemyUnitOfWork(factory) as uow:
        restored_place = uow.place_catalog.get_place("place_westlake")
        restored_revision = uow.place_catalog.get_revision("place_revision_westlake_1")
        restored_projection = uow.place_catalog.get_projection("projection_westlake_1")

    assert restored_place == _place()
    assert restored_revision is not None
    assert restored_revision.lifecycle_status == "published"
    assert restored_projection is not None
    assert restored_projection.status == "published"
    assert restored_projection.projection_hash == _projection().projection_hash


def test_sqlalchemy_publication_context_rejects_cross_place_source(tmp_path: Path) -> None:
    database = tmp_path / "cross-place-source.db"
    engine = create_engine(f"sqlite:///{database}")
    create_schema(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    with SqlAlchemyUnitOfWork(factory) as uow:
        uow.place_catalog.add_place(_place())
        uow.place_catalog.add_place(_place("place_other"))
        # Keep the source ID referenced by the revision, but attach the source
        # row itself to a different Place.  This is the corruption the
        # publication gate must surface explicitly.
        uow.place_catalog.add_source_record(_source("place_other"))
        uow.place_catalog.add_revision(_revision())
        uow.place_catalog.add_geometry(_geometry())
        for point in _access_points():
            uow.place_catalog.add_access_point(point)
        uow.place_catalog.add_time_rule(_time_rule())
        uow.place_catalog.add_projection(_projection())

        context = uow.place_catalog.load_publication_context("projection_westlake_1")
        assert context is not None
        assert context.source_records[0].place_id == "place_other"
        with pytest.raises(ProjectionPublicationError) as exc_info:
            uow.place_catalog.publish_projection(
                "projection_westlake_1", published_at=NOW
            )

    assert "SOURCE_RECORD_PLACE_MISMATCH" in exc_info.value.reason_codes


def test_repository_rejects_direct_published_inserts(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'catalog.db'}")
    create_schema(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    published_revision, published_projection = publish_projection(_context(), published_at=NOW)

    with SqlAlchemyUnitOfWork(factory) as uow:
        with pytest.raises(ValueError, match="publication gate"):
            uow.place_catalog.add_revision(published_revision)
        with pytest.raises(ValueError, match="publication gate"):
            uow.place_catalog.add_projection(published_projection)


def test_publishing_new_revision_retires_previous_solver_version(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'revision-retirement.db'}")
    create_schema(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    second_revision_id = "place_revision_westlake_2"
    second_projection_id = "projection_westlake_2"
    with SqlAlchemyUnitOfWork(factory) as uow:
        uow.place_catalog.add_place(_place())
        uow.place_catalog.add_source_record(_source())
        uow.place_catalog.add_revision(_revision())
        uow.place_catalog.add_geometry(_geometry())
        for point in _access_points():
            uow.place_catalog.add_access_point(point)
        uow.place_catalog.add_time_rule(_time_rule())
        uow.place_catalog.add_projection(_projection())
        uow.place_catalog.publish_projection("projection_westlake_1", published_at=NOW)

        second_revision = replace(
            _revision(),
            place_revision_id=second_revision_id,
            revision_number=2,
            lifecycle_status="human_verified",
        )
        uow.place_catalog.add_revision(second_revision)
        uow.place_catalog.add_geometry(
            replace(_geometry(), geometry_id="geometry_westlake_2", place_revision_id=second_revision_id)
        )
        for point in _access_points():
            uow.place_catalog.add_access_point(
                replace(
                    point,
                    access_point_id=point.access_point_id.replace("westlake", "westlake2"),
                    place_revision_id=second_revision_id,
                )
            )
        uow.place_catalog.add_time_rule(
            replace(_time_rule(), time_rule_id="time_westlake_2", place_revision_id=second_revision_id)
        )
        second_projection = replace(
            _projection(),
            projection_id=second_projection_id,
            data_snapshot_version="hangzhou-candidate-2026-08-29-v2",
            solver_node_id=102,
            place_revision_id=second_revision_id,
            arrival_access_point_id="access_westlake2_arrival",
            departure_access_point_id="access_westlake2_departure",
        )
        second_projection = replace(
            second_projection,
            projection_hash=canonical_projection_sha256(second_projection),
        )
        uow.place_catalog.add_projection(second_projection)
        uow.place_catalog.publish_projection(second_projection_id, published_at=NOW)
        uow.commit()

    with SqlAlchemyUnitOfWork(factory) as uow:
        old_revision = uow.place_catalog.get_revision("place_revision_westlake_1")
        old_projection = uow.place_catalog.get_projection("projection_westlake_1")
        current_revision = uow.place_catalog.get_revision(second_revision_id)
        current_projection = uow.place_catalog.get_projection(second_projection_id)

    assert old_revision is not None and old_revision.lifecycle_status == "retired"
    assert old_revision.solver_eligible is False
    assert old_projection is not None and old_projection.status == "retired"
    assert current_revision is not None and current_revision.lifecycle_status == "published"
    assert current_revision.solver_eligible is True
    assert current_projection is not None and current_projection.status == "published"


def test_o04_candidate_evidence_mutations_bump_revision_version_and_reset_eligibility(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'o04-write.db'}")
    create_schema(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    candidate = replace(
        _revision(),
        lifecycle_status="candidate",
        solver_eligible=True,
        conflicts_resolved=True,
        reviewed_at=None,
        revision_version=1,
    )
    with SqlAlchemyUnitOfWork(factory) as uow:
        uow.place_catalog.add_place(_place())
        uow.place_catalog.add_source_record(_source())
        uow.place_catalog.add_revision(candidate)
        updated = uow.place_catalog.create_access_point(
            _access_points()[0], expected_revision_version=1
        )
        assert updated.revision_version == 2
        assert updated.solver_eligible is False
        assert updated.conflicts_resolved is False
        with pytest.raises(ValueError, match="version conflict"):
            uow.place_catalog.create_access_point(
                _access_points()[1], expected_revision_version=1
            )
        uow.commit()

    with SqlAlchemyUnitOfWork(factory) as uow:
        restored = uow.place_catalog.get_revision(candidate.place_revision_id)
        assert restored is not None
        assert restored.revision_version == 2
        evidence = uow.place_catalog.load_revision_evidence(candidate.place_revision_id)
        assert evidence is not None
        assert len(evidence.access_points) == 1


def test_alembic_0006_builds_catalog_tables_without_touching_old_revisions(
    tmp_path: Path,
) -> None:
    database = tmp_path / "migrated.db"
    config = Config("alembic.ini")
    config.attributes["skip_dotenv"] = True
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")

    command.upgrade(config, "head")

    inspector = inspect(create_engine(f"sqlite:///{database}"))
    tables = set(inspector.get_table_names())
    assert {
        "places",
        "place_source_records",
        "place_revisions",
        "place_geometries",
        "place_access_points",
        "place_time_rules",
        "place_closures",
        "place_date_exceptions",
        "place_relations",
        "selection_exclusion_groups",
        "selection_exclusion_members",
        "solver_place_projections",
    } <= tables
    assert "trip_revisions" in tables
