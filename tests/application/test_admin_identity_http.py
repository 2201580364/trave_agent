"""G7-R0.2-05-01 administrator identity, RBAC, and audit tests."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from travel_agent.application.admin import (
    AdminIdentityService,
    GovernedSourceCatalog,
    PlaceReviewWorkflowService,
)
from travel_agent.application.admin.service import verify_admin_password
from travel_agent.infrastructure.database import (
    AnonymousIdentityService,
    SqlAlchemyAdminUnitOfWork,
    SqlAlchemyUnitOfWork,
    create_schema,
)
from travel_agent.infrastructure.database.admin_identity import (
    AdminActorRow,
    AdminAuditEventRow,
    AdminRoleRow,
    AdminSessionRow,
)
from travel_agent.infrastructure.database.place_catalog import (
    PlaceAccessPointRow,
    PlaceClosureRow,
    PlaceDateExceptionRow,
    PlaceGeometryRow,
    PlaceRevisionRow,
    PlaceRelationRow,
    PlaceRow,
    PlaceSourceRecordRow,
    PlaceTimeRuleRow,
    SolverPlaceProjectionRow,
)
from travel_agent.infrastructure.database.place_review import PlaceReviewDecisionRow
from travel_agent.infrastructure.memory import (
    FixedDataSnapshotVersionProvider,
    InMemoryGenerationExecutor,
    SequenceIdGenerator,
)
from travel_agent.interfaces.http import HttpContainer, create_app
from travel_agent.interfaces.http.admin import safe_source_url

NOW = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
ROOT_LOGIN = "root.admin"
ROOT_PASSWORD = "Root-Admin-Password-2026!"
EDITOR_PASSWORD = "Editor-Password-2026!"


class FixedClock:
    def now(self) -> datetime:
        return NOW


class SequenceTokenGenerator:
    def __init__(self, prefix: str) -> None:
        self._prefix = prefix
        self._next = 1

    def new_token(self) -> str:
        value = f"{self._prefix}-{self._next}-non-public-credential"
        self._next += 1
        return value


@dataclass(slots=True)
class AdminTestContext:
    client: TestClient
    service: AdminIdentityService
    sessions: sessionmaker[Session]


@pytest.fixture
def admin_context(tmp_path: Path) -> Iterator[AdminTestContext]:
    engine = create_engine(f"sqlite:///{tmp_path / 'admin.db'}")
    create_schema(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    ids = SequenceIdGenerator()
    clock = FixedClock()
    service = AdminIdentityService(
        lambda: SqlAlchemyAdminUnitOfWork(sessions),
        clock,
        ids,
        SequenceTokenGenerator("admin-token"),
    )
    assert service.bootstrap_initial_admin(ROOT_LOGIN, ROOT_PASSWORD) is True

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(sessions)

    identity = AnonymousIdentityService(
        sessions,
        clock,
        ids,
        SequenceTokenGenerator("anonymous-token"),
    )
    container = HttpContainer(
        uow_factory,
        clock,
        ids,
        FixedDataSnapshotVersionProvider({}),
        InMemoryGenerationExecutor(),
        identity,
        admin_identity=service,
        review_workflow=PlaceReviewWorkflowService(
            lambda: SqlAlchemyAdminUnitOfWork(sessions),
            clock,
            ids,
            GovernedSourceCatalog.from_files(
                Path(__file__).resolve().parents[2]
                / "data/governance/hangzhou-source-registry-v1.json",
                Path(__file__).resolve().parents[2]
                / "data/governance/place-collection-field-dictionary-v1.json",
            ),
        ),
    )
    with TestClient(create_app(container)) as client:
        yield AdminTestContext(client, service, sessions)


def _login(client: TestClient, login: str, password: str) -> tuple[str, dict[str, str]]:
    response = client.post(
        "/api/v1/admin/sessions",
        headers={"X-Request-ID": f"req-login-{login}"},
        json={"login_name": login, "password": password},
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


def test_bootstrap_is_one_time_and_never_persists_plaintext_secret(
    admin_context: AdminTestContext,
) -> None:
    context = admin_context

    assert context.service.bootstrap_initial_admin("other.admin", ROOT_PASSWORD) is False
    with context.sessions() as session:
        actor = session.scalar(select(AdminActorRow))
        roles = tuple(session.scalars(select(AdminRoleRow).order_by(AdminRoleRow.role_key)))
        audits = tuple(session.scalars(select(AdminAuditEventRow)))

    assert actor is not None
    assert actor.login_name == ROOT_LOGIN
    assert actor.credential_digest.startswith("scrypt$")
    assert ROOT_PASSWORD not in actor.credential_digest
    assert [role.role_key for role in roles] == [
        "admin_security",
        "content_moderator",
        "data_editor",
        "data_publisher",
        "data_reviewer",
        "research_viewer",
    ]
    assert [event.action for event in audits] == ["ADMIN_ACTOR_BOOTSTRAPPED"]
    assert audits[0].after_digest is not None
    assert audits[0].reason_text is None
    assert (
        verify_admin_password(
            ROOT_PASSWORD,
            "scrypt$1073741824$8$1$" + ("00" * 16) + "$" + ("00" * 32),
        )
        is False
    )


def test_admin_session_is_independent_revocable_and_stores_only_token_digest(
    admin_context: AdminTestContext,
) -> None:
    context = admin_context
    rejected = context.client.post(
        "/api/v1/admin/sessions",
        headers={"X-Request-ID": "req-bad-login"},
        json={"login_name": ROOT_LOGIN, "password": "Wrong-Password-2026!"},
    )
    assert rejected.status_code == 401
    assert rejected.json()["error"]["code"] == "admin_authentication_required"

    token, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)
    me = context.client.get("/api/v1/admin/me", headers=headers)
    assert me.status_code == 200
    assert "admin_security" in me.json()["role_keys"]
    assert "admin:actor:roles:write" in me.json()["permissions"]

    with context.sessions() as session:
        stored = session.scalar(
            select(AdminSessionRow).order_by(AdminSessionRow.created_at.desc())
        )
    assert stored is not None
    assert stored.token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert token not in stored.token_hash
    assert stored.client_ip_hash is not None
    assert stored.user_agent_hash is not None

    anonymous = context.client.post(
        "/api/v1/anonymous-sessions", json={"device_installation_id": "device-admin-test"}
    ).json()["access_token"]
    ordinary_token = context.client.get(
        "/api/v1/admin/me",
        headers={"Authorization": f"Bearer {anonymous}"},
    )
    assert ordinary_token.status_code == 401
    assert ordinary_token.json()["error"]["code"] == "admin_authentication_required"

    assert (
        context.client.delete("/api/v1/admin/sessions/current", headers=headers).status_code
        == 204
    )
    assert context.client.get("/api/v1/admin/me", headers=headers).status_code == 401


def test_server_side_rbac_role_versioning_idempotency_and_session_invalidation(
    admin_context: AdminTestContext,
) -> None:
    context = admin_context
    _, root_headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)
    create_payload = {
        "operation_intent_id": "op-create-editor-1",
        "login_name": "place.editor",
        "initial_password": EDITOR_PASSWORD,
        "role_keys": ["data_editor"],
        "reason_code": "OM1_TEAM_PROVISIONING",
        "reason_text": "为地点候选录入建立最小权限账号",
    }
    created = context.client.post(
        "/api/v1/admin/admin-actors", headers=root_headers, json=create_payload
    )
    assert created.status_code == 201
    editor_id = created.json()["admin_actor_id"]
    assert created.json()["role_keys"] == ["data_editor"]
    assert created.json()["reused"] is False

    replay = context.client.post(
        "/api/v1/admin/admin-actors", headers=root_headers, json=create_payload
    )
    assert replay.status_code == 201
    assert replay.json()["admin_actor_id"] == editor_id
    assert replay.json()["reused"] is True
    conflicting_replay = context.client.post(
        "/api/v1/admin/admin-actors",
        headers=root_headers,
        json={**create_payload, "initial_password": "Changed-Password-2026!"},
    )
    assert conflicting_replay.status_code == 409
    assert conflicting_replay.json()["error"]["code"] == (
        "admin_operation_intent_conflict"
    )

    _, editor_headers = _login(context.client, "place.editor", EDITOR_PASSWORD)
    forbidden = context.client.get(
        "/api/v1/admin/admin-actors", headers=editor_headers
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "admin_permission_denied"

    role_payload = {
        "operation_intent_id": "op-editor-roles-1",
        "expected_version": 1,
        "role_keys": ["data_editor", "research_viewer"],
        "reason_code": "RESEARCH_READ_ACCESS_GRANTED",
        "reason_text": "允许编辑查看研究快照",
    }
    changed = context.client.put(
        f"/api/v1/admin/admin-actors/{editor_id}/roles",
        headers=root_headers,
        json=role_payload,
    )
    assert changed.status_code == 200
    assert changed.json()["version"] == 2
    assert changed.json()["session_version"] == 2
    assert changed.json()["reused"] is False
    assert context.client.get("/api/v1/admin/me", headers=editor_headers).status_code == 401

    repeated = context.client.put(
        f"/api/v1/admin/admin-actors/{editor_id}/roles",
        headers=root_headers,
        json=role_payload,
    )
    assert repeated.status_code == 200
    assert repeated.json()["reused"] is True
    conflict = context.client.put(
        f"/api/v1/admin/admin-actors/{editor_id}/roles",
        headers=root_headers,
        json={**role_payload, "role_keys": ["research_viewer"]},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "admin_operation_intent_conflict"


def test_last_security_role_is_protected_and_rejected_attempt_is_audited(
    admin_context: AdminTestContext,
) -> None:
    context = admin_context
    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)
    actor = context.client.get("/api/v1/admin/admin-actors", headers=headers).json()[
        "items"
    ][0]
    response = context.client.put(
        f"/api/v1/admin/admin-actors/{actor['admin_actor_id']}/roles",
        headers={**headers, "X-Request-ID": "req-remove-last-security"},
        json={
            "operation_intent_id": "op-remove-last-security",
            "expected_version": 1,
            "role_keys": ["data_editor"],
            "reason_code": "ROLE_SCOPE_REDUCED",
            "reason_text": "缩小管理员职责范围",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "admin_role_safety_violation"

    audit = context.client.get(
        "/api/v1/admin/audit-events",
        headers=headers,
        params={"result": "rejected", "action": "ADMIN_ACTOR_ROLES_CHANGE"},
    )
    assert audit.status_code == 200
    event = audit.json()["items"][0]
    assert event["actor_login_name"] == ROOT_LOGIN
    assert event["operation_intent_id"] == "op-remove-last-security"
    assert event["request_id"] == "req-remove-last-security"
    assert event["error_code"] == "admin_role_safety_violation"
    assert event["before_digest"] is not None
    assert event["after_digest"] is None
    assert context.client.patch(
        f"/api/v1/admin/audit-events/{event['audit_event_id']}", headers=headers
    ).status_code == 404


def test_reason_text_rejects_likely_credentials(
    admin_context: AdminTestContext,
) -> None:
    context = admin_context
    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)
    response = context.client.post(
        "/api/v1/admin/admin-actors",
        headers=headers,
        json={
            "operation_intent_id": "op-sensitive-reason",
            "login_name": "unsafe.editor",
            "initial_password": EDITOR_PASSWORD,
            "role_keys": ["data_editor"],
            "reason_code": "OM1_TEAM_PROVISIONING",
            "reason_text": "临时 password 是某个值",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "domain_validation_failed"
    assert EDITOR_PASSWORD not in response.text


def test_alembic_head_adds_admin_tables_and_seeds_role_catalog(tmp_path: Path) -> None:
    database = tmp_path / "admin-migrated.db"
    config = Config("alembic.ini")
    config.attributes["skip_dotenv"] = True
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database}")
    with engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        roles = connection.execute(
            text("SELECT role_key FROM admin_roles ORDER BY role_key")
        ).scalars()
        table_names = {
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        }

    assert revision == "0013_backfill_solver_eligibility"
    assert set(roles) == {
        "admin_security",
        "content_moderator",
        "data_editor",
        "data_publisher",
        "data_reviewer",
        "research_viewer",
    }
    assert {
        "admin_actors",
        "admin_roles",
        "admin_actor_roles",
        "admin_sessions",
        "admin_audit_events",
    }.issubset(table_names)

    command.downgrade(config, "0006_place_catalog")
    with engine.connect() as connection:
        downgraded_revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        downgraded_tables = {
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        }
    assert downgraded_revision == "0006_place_catalog"
    assert "admin_actors" not in downgraded_tables
    assert "places" in downgraded_tables


def _seed_candidate_revision(context: AdminTestContext, revision_id: str = "revision-1") -> None:
    with context.sessions() as session:
        session.add(
            PlaceRow(
                place_id="place-1",
                city_id="hangzhou",
                status="active",
                merged_into_place_id=None,
                created_at=NOW.isoformat(),
                updated_at=NOW.isoformat(),
            )
        )
        session.add(
            PlaceRevisionRow(
                place_revision_id=revision_id,
                place_id="place-1",
                revision_number=1,
                lifecycle_status="candidate",
                canonical_name="Candidate Place",
                aliases=[],
                place_kind="attraction",
                category="museum",
                admin_area="West Lake",
                address=None,
                geometry_kind="point",
                duration_min=30,
                duration_recommended=60,
                duration_max=90,
                internal_travel_min=0,
                energy_level=2,
                indoor_outdoor="indoor",
                suitable_periods=["morning"],
                audience_tags=[],
                rain_suitability="suitable",
                is_always_open=False,
                solver_eligible=False,
                conflicts_resolved=True,
                source_record_ids=[],
                created_at=NOW.isoformat(),
                reviewed_at=None,
                published_at=None,
            )
        )
        session.commit()


def _seed_human_verified_revision_with_evidence(
    context: AdminTestContext, revision_id: str = "revision-projection"
) -> None:
    """Seed the smallest fully verified catalog graph for projection API tests."""
    with context.sessions() as session:
        session.add(PlaceRow(
            place_id="place-projection", city_id="hangzhou", status="active",
            merged_into_place_id=None, created_at=NOW.isoformat(), updated_at=NOW.isoformat(),
        ))
        session.add(PlaceSourceRecordRow(
            source_record_id="source-projection", place_id="place-projection",
            source_id="test-registry", registry_id="v1", registry_sha256="a" * 64,
            field_dictionary_id="fields-v1", field_dictionary_sha256="b" * 64,
            source_url="https://example.test/place", collection_mode="manual_reference",
            target_stage="published", source_decision="approved", observed_at=NOW.isoformat(),
            content_sha256="c" * 64, status="active", created_at=NOW.isoformat(),
        ))
        session.add(PlaceRevisionRow(
            place_revision_id=revision_id, place_id="place-projection", revision_number=1,
            lifecycle_status="human_verified", canonical_name="Verified Place", aliases=[],
            place_kind="attraction", category="museum", admin_area="West Lake", address="杭州",
            geometry_kind="point", duration_min=30, duration_recommended=60, duration_max=90,
            internal_travel_min=0, energy_level=2, indoor_outdoor="indoor",
            suitable_periods=["morning", "afternoon"], audience_tags=[], rain_suitability="suitable",
            is_always_open=False, solver_eligible=True, conflicts_resolved=True,
            source_record_ids=["source-projection"], created_at=NOW.isoformat(),
            reviewed_at=NOW.isoformat(), published_at=None,
        ))
        session.add(PlaceGeometryRow(
            geometry_id="geometry-projection", place_revision_id=revision_id, geometry_kind="point",
            geometry={"type": "Point", "coordinates": [120.15, 30.25]},
            source_record_id="source-projection", review_status="human_verified", active=True,
            created_at=NOW.isoformat(), reviewed_at=NOW.isoformat(),
        ))
        session.add(PlaceAccessPointRow(
            access_point_id="access-projection", place_revision_id=revision_id,
            access_point_kind="visitor_entrance", name="主入口", lat=30.25, lng=120.15,
            source_record_id="source-projection", review_status="human_verified", active=True,
            fetched_at=NOW.isoformat(), reviewed_at=NOW.isoformat(), created_at=NOW.isoformat(),
        ))
        session.add(PlaceTimeRuleRow(
            time_rule_id="time-projection", place_revision_id=revision_id, rule_kind="opening_hours",
            weekdays=[1, 2, 3, 4, 5, 6, 7], start_minute=540, end_minute=1020,
            last_entry_minute=990, valid_from=date(2026, 1, 1), valid_to=None,
            source_record_id="source-projection", review_status="human_verified", active=True,
            created_at=NOW.isoformat(), reviewed_at=NOW.isoformat(),
        ))
        session.commit()


def test_time_preview_resolves_exceptions_closures_cross_midnight_and_sessions(
    admin_context: AdminTestContext,
) -> None:
    context = admin_context
    _seed_candidate_revision(context, "revision-time-preview")
    with context.sessions() as session:
        revision = session.get(PlaceRevisionRow, "revision-time-preview")
        assert revision is not None
        revision.source_record_ids = []
        session.add(
            PlaceTimeRuleRow(
                time_rule_id="preview-opening",
                place_revision_id=revision.place_revision_id,
                rule_kind="opening_hours",
                weekdays=[1, 2, 3, 4, 5, 6, 7],
                start_minute=9 * 60,
                end_minute=17 * 60,
                last_entry_minute=16 * 60,
                valid_from=None,
                valid_to=None,
                source_record_id="missing-source",
                review_status="human_verified",
                active=True,
                created_at=NOW.isoformat(),
                reviewed_at=NOW.isoformat(),
            )
        )
        session.add(
            PlaceTimeRuleRow(
                time_rule_id="preview-fixed-1",
                place_revision_id=revision.place_revision_id,
                rule_kind="fixed_session",
                weekdays=[2],
                start_minute=23 * 60 + 30,
                end_minute=25 * 60 + 30,
                last_entry_minute=24 * 60 + 30,
                valid_from=None,
                valid_to=None,
                source_record_id="missing-source",
                review_status="human_verified",
                active=True,
                created_at=NOW.isoformat(),
                reviewed_at=NOW.isoformat(),
            )
        )
        session.add(
            PlaceTimeRuleRow(
                time_rule_id="preview-fixed-2",
                place_revision_id=revision.place_revision_id,
                rule_kind="fixed_session",
                weekdays=[2],
                start_minute=26 * 60,
                end_minute=27 * 60,
                last_entry_minute=None,
                valid_from=None,
                valid_to=None,
                source_record_id="missing-source",
                review_status="human_verified",
                active=True,
                created_at=NOW.isoformat(),
                reviewed_at=NOW.isoformat(),
            )
        )
        session.add(
            PlaceClosureRow(
                closure_id="preview-monday-closure",
                place_revision_id=revision.place_revision_id,
                weekday=1,
                source_record_id="missing-source",
                review_status="human_verified",
                active=True,
                created_at=NOW.isoformat(),
                reviewed_at=NOW.isoformat(),
            )
        )
        session.add(
            PlaceDateExceptionRow(
                date_exception_id="preview-open-override",
                place_revision_id=revision.place_revision_id,
                service_date=date(2026, 9, 7),
                exception_kind="open_override",
                start_minute=10 * 60,
                end_minute=18 * 60,
                last_entry_minute=17 * 60,
                source_record_id="missing-source",
                review_status="human_verified",
                active=True,
                created_at=NOW.isoformat(),
                reviewed_at=NOW.isoformat(),
            )
        )
        session.commit()

    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)

    override = context.client.get(
        "/api/v1/admin/place-revisions/revision-time-preview/time-preview",
        params={"service_date": "2026-09-07"},
        headers=headers,
    )
    assert override.status_code == 200
    assert override.json()["open"] is True
    assert override.json()["windows"] == [
        {"start_minute": 600, "end_minute": 1080, "last_entry_minute": 1020}
    ]
    assert override.json()["applied_exception_ids"] == ["preview-open-override"]
    assert override.json()["rule_ids"] == []
    assert override.json()["reason_codes"] == ["PLACE_DATE_EXCEPTION_APPLIED"]

    closed = context.client.get(
        "/api/v1/admin/place-revisions/revision-time-preview/time-preview",
        params={"service_date": "2026-09-14"},
        headers=headers,
    )
    assert closed.status_code == 200
    assert closed.json()["open"] is False
    assert closed.json()["reason_codes"] == ["PLACE_WEEKLY_CLOSED"]

    sessions = context.client.get(
        "/api/v1/admin/place-revisions/revision-time-preview/time-preview",
        params={"service_date": "2026-09-08"},
        headers=headers,
    )
    assert sessions.status_code == 200
    assert sessions.json()["open"] is True
    assert sessions.json()["reason_codes"] == [
        "CROSS_MIDNIGHT_WINDOW",
        "FIXED_SESSION_AMBIGUOUS",
    ]
    assert [item["time_rule_id"] for item in sessions.json()["fixed_sessions"]] == [
        "preview-fixed-1",
        "preview-fixed-2",
    ]

    unmatched = context.client.get(
        "/api/v1/admin/place-revisions/revision-time-preview/time-preview",
        params={"service_date": "2026-09-13"},
        headers=headers,
    )
    assert unmatched.status_code == 200
    assert unmatched.json()["open"] is True
    assert unmatched.json()["windows"][0]["start_minute"] == 540

    unauthenticated = context.client.get(
        "/api/v1/admin/place-revisions/revision-time-preview/time-preview",
        params={"service_date": "2026-09-07"},
    )
    assert unauthenticated.status_code == 401


def test_holiday_calendar_catalog_is_available_to_authenticated_admin(
    admin_context: AdminTestContext,
) -> None:
    _, headers = _login(admin_context.client, ROOT_LOGIN, ROOT_PASSWORD)
    response = admin_context.client.get("/api/v1/admin/holiday-calendars", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert {item["calendar_id"] for item in items} >= {
        "cn-mainland-2025",
        "cn-mainland-2026",
    }
    assert all(item["display_name"].startswith("中国大陆法定节假日历") for item in items)


def test_holiday_exception_generation_is_audited_and_materializes_only_conflicts(
    admin_context: AdminTestContext,
) -> None:
    context = admin_context
    _seed_candidate_revision(context, "revision-holiday-generation")
    with context.sessions() as session:
        revision = session.get(PlaceRevisionRow, "revision-holiday-generation")
        assert revision is not None
        revision.source_record_ids = ["source-holiday-generation"]
        session.add(PlaceSourceRecordRow(
            source_record_id="source-holiday-generation", place_id=revision.place_id,
            source_id="test-registry", registry_id="v1", registry_sha256="a" * 64,
            field_dictionary_id="fields-v1", field_dictionary_sha256="b" * 64,
            source_url="https://example.test/museum-holiday-policy",
            collection_mode="manual_reference", target_stage="staging",
            source_decision="approved", observed_at=NOW.isoformat(),
            content_sha256="c" * 64, status="active", created_at=NOW.isoformat(),
        ))
        session.add(PlaceClosureRow(
            closure_id="closure-holiday-monday",
            place_revision_id=revision.place_revision_id,
            weekday=1,
            source_record_id="source-holiday-generation",
            review_status="candidate",
            active=True,
            created_at=NOW.isoformat(),
            reviewed_at=None,
        ))
        session.commit()

    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)
    response = context.client.post(
        "/api/v1/admin/place-revisions/revision-holiday-generation/holiday-exceptions",
        headers=headers,
        json={
            "expected_revision_version": 1,
            "calendar_id": "cn-mainland-2026",
            "source_record_id": "source-holiday-generation",
            "open_start_minute": 540,
            "open_end_minute": 1020,
            "open_last_entry_minute": 990,
            "shift_closure": True,
            "operation_intent_id": "holiday-generation-http-1",
            "reason_code": "HOLIDAY_POLICY_MATERIALIZED",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["revision_version"] == 10
    with context.sessions() as session:
        rows = tuple(session.scalars(
            select(PlaceDateExceptionRow)
            .where(PlaceDateExceptionRow.place_revision_id == "revision-holiday-generation")
            .order_by(PlaceDateExceptionRow.service_date)
        ))
        audit = session.scalar(
            select(AdminAuditEventRow).where(
                AdminAuditEventRow.action == "PLACE_HOLIDAY_EXCEPTIONS_GENERATED"
            )
        )
    assert len(rows) == 9
    assert {row.service_date for row in rows if row.exception_kind == "open_override"} == {
        date(2026, 2, 16), date(2026, 2, 23), date(2026, 4, 6),
        date(2026, 5, 4), date(2026, 10, 5),
    }
    assert {row.service_date for row in rows if row.exception_kind == "closed"} == {
        date(2026, 2, 24), date(2026, 4, 7), date(2026, 5, 6), date(2026, 10, 8),
    }
    assert audit is not None
    assert audit.target_type == "place_date_exception"

def test_projection_preparation_api_is_verified_idempotent_and_does_not_publish(
    admin_context: AdminTestContext,
) -> None:
    context = admin_context
    _seed_human_verified_revision_with_evidence(context)
    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)
    payload = {
        "data_snapshot_version": "hangzhou-research-candidate-v1",
        "operation_intent_id": "projection-prepare-http-1",
        "reason_code": "PROJECTION_PREPARED",
    }
    response = context.client.post(
        "/api/v1/admin/place-revisions/revision-projection/projection-preparations",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "candidate"
    assert body["gate_reason_codes"] == []
    assert body["projection_hash"]
    with context.sessions() as session:
        prepared = session.get(SolverPlaceProjectionRow, body["projection_id"])
    assert prepared is not None
    assert prepared.status == "candidate"
    assert prepared.solver_node_id == 1

    replay = context.client.post(
        "/api/v1/admin/place-revisions/revision-projection/projection-preparations",
        headers=headers,
        json=payload,
    )
    assert replay.status_code == 200
    assert replay.json()["projection_id"] == body["projection_id"]

    with context.sessions() as session:
        projection = session.get(SolverPlaceProjectionRow, body["projection_id"])
    assert projection is not None
    assert projection.status == "candidate"


def test_projection_preparation_api_enforces_permission_and_revision_state(
    admin_context: AdminTestContext,
) -> None:
    context = admin_context
    _seed_human_verified_revision_with_evidence(context, "revision-projection-auth")
    _, root_headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)
    created = context.client.post(
        "/api/v1/admin/admin-actors",
        headers=root_headers,
        json={
            "operation_intent_id": "projection-editor-create",
            "login_name": "projection.editor",
            "initial_password": EDITOR_PASSWORD,
            "role_keys": ["data_editor"],
            "reason_code": "TEST_ACCOUNT",
        },
    )
    assert created.status_code == 201
    _, editor_headers = _login(context.client, "projection.editor", EDITOR_PASSWORD)
    denied = context.client.post(
        "/api/v1/admin/place-revisions/revision-projection-auth/projection-preparations",
        headers=editor_headers,
        json={"data_snapshot_version": "snapshot", "operation_intent_id": "denied", "reason_code": "TEST"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "admin_permission_denied"

    _seed_candidate_revision(context, "revision-projection-candidate")
    blocked = context.client.post(
        "/api/v1/admin/place-revisions/revision-projection-candidate/projection-preparations",
        headers=root_headers,
        json={"data_snapshot_version": "snapshot", "operation_intent_id": "candidate", "reason_code": "TEST"},
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "review_revision_not_approvable"


def test_publication_batch_preview_and_failed_execution_are_auditable(
    admin_context: AdminTestContext,
) -> None:
    _seed_candidate_revision(admin_context, "revision-batch-blocked")
    _, headers = _login(admin_context.client, ROOT_LOGIN, ROOT_PASSWORD)
    preview = admin_context.client.post(
        "/api/v1/admin/publication-batches/previews",
        headers=headers,
        json={
            "city_id": "hangzhou",
            "place_revision_ids": ["revision-batch-blocked"],
            "operation_intent_id": "batch-preview-blocked-1",
            "reason_code": "PUBLICATION_BATCH_PREVIEW",
        },
    )
    assert preview.status_code == 201
    body = preview.json()
    assert body["status"] == "preview"
    assert body["items"][0]["status"] == "blocked"
    assert body["items"][0]["reason_codes"] == ["PROJECTION_NOT_FOUND"]
    batch_id = body["batch_id"]

    execution = admin_context.client.post(
        f"/api/v1/admin/publication-batches/{batch_id}/execute",
        headers=headers,
        json={
            "operation_intent_id": "batch-execute-blocked-1",
            "reason_code": "PUBLICATION_BATCH_EXECUTE",
        },
    )
    assert execution.status_code == 200
    assert execution.json()["snapshot"] is None
    assert execution.json()["batch"]["status"] == "failed"

    replay = admin_context.client.post(
        f"/api/v1/admin/publication-batches/{batch_id}/execute",
        headers=headers,
        json={
            "operation_intent_id": "batch-execute-blocked-1",
            "reason_code": "PUBLICATION_BATCH_EXECUTE",
        },
    )
    assert replay.status_code == 200
    assert replay.json()["reused"] is True


def test_place_review_submit_approve_and_audit_are_one_workflow(
    admin_context: AdminTestContext,
) -> None:
    context = admin_context
    _seed_candidate_revision(context)
    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)

    submit_payload = {
        "operation_intent_id": "review-submit-1",
        "reason_code": "OM1_CANDIDATE_READY",
        "reason_text": "字段已完成初审",
    }
    submitted = context.client.post(
        "/api/v1/admin/place-revisions/revision-1/review-tasks",
        headers={**headers, "X-Request-ID": "req-review-submit"},
        json=submit_payload,
    )
    assert submitted.status_code == 201
    task = submitted.json()
    assert task["status"] == "ready_for_review"
    assert task["version"] == 1

    loaded = context.client.get(
        f"/api/v1/admin/review-tasks/{task['review_task_id']}", headers=headers
    )
    assert loaded.status_code == 200
    assert loaded.json()["place_revision_id"] == "revision-1"
    assert loaded.json()["status"] == "ready_for_review"

    replay = context.client.post(
        "/api/v1/admin/place-revisions/revision-1/review-tasks",
        headers=headers,
        json=submit_payload,
    )
    assert replay.status_code == 201
    assert replay.json()["review_task_id"] == task["review_task_id"]

    decided = context.client.post(
        f"/api/v1/admin/review-tasks/{task['review_task_id']}/decisions",
        headers={**headers, "X-Request-ID": "req-review-approve"},
        json={
            "operation_intent_id": "review-approve-1",
            "expected_version": 1,
            "decision_kind": "approve",
            "reason_code": "OM1_FACTS_VERIFIED",
            "reason_text": "人工核验通过",
        },
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"
    assert decided.json()["version"] == 2

    approve_replay = context.client.post(
        f"/api/v1/admin/review-tasks/{task['review_task_id']}/decisions",
        headers=headers,
        json={
            "operation_intent_id": "review-approve-1",
            "expected_version": 1,
            "decision_kind": "approve",
            "reason_code": "OM1_FACTS_VERIFIED",
            "reason_text": "人工核验通过",
        },
    )
    assert approve_replay.status_code == 200
    assert approve_replay.json()["status"] == "approved"

    intent_conflict = context.client.post(
        f"/api/v1/admin/review-tasks/{task['review_task_id']}/decisions",
        headers=headers,
        json={
            "operation_intent_id": "review-approve-1",
            "expected_version": 1,
            "decision_kind": "request_changes",
            "reason_code": "OM1_FACTS_VERIFIED",
        },
    )
    assert intent_conflict.status_code == 409
    assert intent_conflict.json()["error"]["code"] == "admin_operation_intent_conflict"

    with context.sessions() as session:
        revision = session.get(PlaceRevisionRow, "revision-1")
        decisions = tuple(session.scalars(select(PlaceReviewDecisionRow)))
        events = tuple(
            session.scalars(
                select(AdminAuditEventRow).where(
                    AdminAuditEventRow.action.in_(
                        ("PLACE_REVIEW_SUBMITTED", "PLACE_REVIEW_DECIDED")
                    )
                )
            )
        )
    assert revision is not None
    assert revision.lifecycle_status == "human_verified"
    assert len(decisions) == 1
    assert decisions[0].decision_kind == "approve"
    assert {event.action for event in events} == {
        "PLACE_REVIEW_SUBMITTED",
        "PLACE_REVIEW_DECIDED",
    }

    history = context.client.get(
        f"/api/v1/admin/review-tasks/{task['review_task_id']}/decisions",
        headers=headers,
    )
    assert history.status_code == 200
    assert history.json()["items"][0]["actor_role"] == "data_reviewer"


def test_candidate_list_and_revision_detail_are_permission_scoped(
    admin_context: AdminTestContext,
) -> None:
    context = admin_context
    _seed_candidate_revision(context, "revision-candidates")
    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)

    candidates = context.client.get("/api/v1/admin/candidates", headers=headers)
    assert candidates.status_code == 200
    assert candidates.json()["items"][0]["place_revision_id"] == "revision-candidates"
    assert candidates.json()["items"][0]["lifecycle_status"] == "candidate"
    readiness = candidates.json()["items"][0]["review_readiness"]
    assert readiness["status"] == "needs_evidence"
    assert readiness["completed_checks"] == 2
    assert readiness["total_checks"] == 6
    assert readiness["missing_checks"] == [
        "source",
        "geometry",
        "access_point",
        "time",
    ]
    assert candidates.json()["limit"] == 50
    assert candidates.json()["offset"] == 0
    assert candidates.json()["total"] == 1

    empty_page = context.client.get(
        "/api/v1/admin/candidates?limit=1&offset=1", headers=headers
    )
    assert empty_page.status_code == 200
    assert empty_page.json()["items"] == []
    assert empty_page.json()["total"] == 1

    detail = context.client.get(
        "/api/v1/admin/place-revisions/revision-candidates", headers=headers
    )
    assert detail.status_code == 200
    assert detail.json()["canonical_name"] == "Candidate Place"

    missing = context.client.get(
        "/api/v1/admin/place-revisions/missing", headers=headers
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "resource_not_found"


def test_place_source_records_are_governed_versioned_audited_and_reference_safe(
    admin_context: AdminTestContext,
) -> None:
    context = admin_context
    _seed_candidate_revision(context, "revision-source-maintenance")
    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)

    channels = context.client.get("/api/v1/admin/source-channels", headers=headers)
    assert channels.status_code == 200
    channel_ids = {item["source_id"] for item in channels.json()["items"]}
    assert "hangzhou-westlake-admin-public-web" in channel_ids
    assert "gaode-web-service" in channel_ids
    assert "qweather-developer-service" not in channel_ids

    payload = {
        "expected_revision_version": 1,
        "source_id": "hangzhou-westlake-admin-public-web",
        "source_url": "https://westlake.hangzhou.gov.cn/art/2026/8/29/example.html",
        "collection_mode": "manual_reference",
        "observed_at": NOW.isoformat(),
        "content_sha256": "C" * 64,
        "operation_intent_id": "source-create-1",
        "reason_code": "PLACE_SOURCE_RECORD_ADDED",
        "reason_text": "支持地点开放时间与位置核验",
    }
    created = context.client.post(
        "/api/v1/admin/place-revisions/revision-source-maintenance/source-records",
        headers=headers,
        json=payload,
    )
    assert created.status_code == 201
    assert created.json()["revision_version"] == 2
    assert created.json()["conflicts_resolved"] is False
    assert created.json()["solver_eligible"] is False
    source_record_id = created.json()["source_record_ids"][0]

    replay = context.client.post(
        "/api/v1/admin/place-revisions/revision-source-maintenance/source-records",
        headers=headers,
        json=payload,
    )
    assert replay.status_code == 201
    assert replay.json()["source_record_ids"] == [source_record_id]

    evidence = context.client.get(
        "/api/v1/admin/place-revisions/revision-source-maintenance/evidence",
        headers=headers,
    ).json()
    source = evidence["sources"][0]
    assert source["attached_to_revision"] is True
    assert source["content_sha256"] == "c" * 64
    with context.sessions() as session:
        row = session.get(PlaceSourceRecordRow, source_record_id)
        assert row is not None
        assert row.registry_id == "hangzhou-m1-source-registry-v1"
        assert len(row.registry_sha256) == 64
        assert row.field_dictionary_id == "m1-place-collection-fields-v1"
        assert len(row.field_dictionary_sha256) == 64
        assert row.target_stage == "staging"
        assert row.source_decision == "conditional"

    invalid = context.client.post(
        "/api/v1/admin/place-revisions/revision-source-maintenance/source-records",
        headers=headers,
        json={
            **payload,
            "expected_revision_version": 2,
            "source_id": "gaode-web-service",
            "source_url": "https://restapi.amap.com/v3/place/text?key=must-not-leak",
            "collection_mode": "api",
            "operation_intent_id": "source-create-sensitive",
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "source_record_validation_failed"
    assert "must-not-leak" not in invalid.text

    geometry = context.client.post(
        "/api/v1/admin/place-revisions/revision-source-maintenance/geometries",
        headers=headers,
        json={
            "expected_revision_version": 2,
            "geometry_kind": "point",
            "geometry": {"type": "Point", "coordinates": [120.15, 30.25]},
            "source_record_id": source_record_id,
            "operation_intent_id": "source-geometry-create",
            "reason_code": "EVIDENCE_CREATED",
        },
    )
    assert geometry.status_code == 200
    blocked = context.client.request(
        "DELETE",
        f"/api/v1/admin/place-revisions/revision-source-maintenance/source-records/{source_record_id}",
        headers=headers,
        json={
            "expected_revision_version": 3,
            "operation_intent_id": "source-detach-blocked",
            "reason_code": "PLACE_SOURCE_RECORD_REMOVED",
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "source_record_in_use"
    assert blocked.json()["error"]["details"]["references"] == ["地点几何"]

    geometry_id = context.client.get(
        "/api/v1/admin/place-revisions/revision-source-maintenance/evidence",
        headers=headers,
    ).json()["geometries"][0]["geometry_id"]
    retired = context.client.request(
        "DELETE",
        f"/api/v1/admin/place-revisions/revision-source-maintenance/geometries/{geometry_id}",
        headers=headers,
        json={
            "expected_revision_version": 3,
            "operation_intent_id": "source-geometry-retire",
            "reason_code": "EVIDENCE_RETIRED",
        },
    )
    assert retired.status_code == 200
    detached = context.client.request(
        "DELETE",
        f"/api/v1/admin/place-revisions/revision-source-maintenance/source-records/{source_record_id}",
        headers=headers,
        json={
            "expected_revision_version": 4,
            "operation_intent_id": "source-detach-1",
            "reason_code": "PLACE_SOURCE_RECORD_REMOVED",
        },
    )
    assert detached.status_code == 200
    assert detached.json()["revision_version"] == 5
    assert detached.json()["source_record_ids"] == []
    with context.sessions() as session:
        assert session.get(PlaceSourceRecordRow, source_record_id) is not None
        actions = tuple(
            session.scalars(
                select(AdminAuditEventRow.action).where(
                    AdminAuditEventRow.action.in_(
                        ("PLACE_SOURCE_RECORD_CREATED", "PLACE_SOURCE_RECORD_DETACHED")
                    )
                )
            )
        )
    assert actions == ("PLACE_SOURCE_RECORD_CREATED", "PLACE_SOURCE_RECORD_DETACHED")


def test_admin_place_and_audit_searches_filter_before_pagination(
    admin_context: AdminTestContext,
) -> None:
    context = admin_context
    _seed_candidate_revision(context, "revision-search")
    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)

    created_actor = context.client.post(
        "/api/v1/admin/admin-actors",
        headers=headers,
        json={
            "operation_intent_id": "op-create-search-editor",
            "login_name": "search.editor",
            "initial_password": EDITOR_PASSWORD,
            "role_keys": ["data_editor"],
            "reason_code": "OM1_TEAM_PROVISIONING",
        },
    )
    assert created_actor.status_code == 201

    actor_by_keyword = context.client.get(
        "/api/v1/admin/admin-actors",
        headers=headers,
        params={"keyword": "search.editor", "limit": 1, "offset": 0},
    )
    assert actor_by_keyword.status_code == 200
    assert actor_by_keyword.json()["total"] == 1
    assert [item["login_name"] for item in actor_by_keyword.json()["items"]] == [
        "search.editor"
    ]

    actor_by_role = context.client.get(
        "/api/v1/admin/admin-actors",
        headers=headers,
        params={"actor_status": "active", "role_key": "admin_security"},
    )
    assert actor_by_role.status_code == 200
    assert actor_by_role.json()["total"] == 1
    assert actor_by_role.json()["items"][0]["login_name"] == ROOT_LOGIN

    for query in (
        {"keyword": "Candidate"},
        {"admin_area": "West Lake"},
        {"place_kind": "attraction"},
    ):
        candidates = context.client.get(
            "/api/v1/admin/candidates", headers=headers, params=query
        )
        assert candidates.status_code == 200
        assert candidates.json()["total"] == 1
        assert candidates.json()["items"][0]["place_revision_id"] == "revision-search"

    no_candidates = context.client.get(
        "/api/v1/admin/candidates",
        headers=headers,
        params={"keyword": "not-a-real-place", "limit": 1, "offset": 0},
    )
    assert no_candidates.status_code == 200
    assert no_candidates.json()["items"] == []
    assert no_candidates.json()["total"] == 0

    submitted = context.client.post(
        "/api/v1/admin/place-revisions/revision-search/review-tasks",
        headers=headers,
        json={
            "operation_intent_id": "review-submit-search",
            "reason_code": "READY_FOR_REVIEW",
        },
    )
    assert submitted.status_code == 201

    review_queue = context.client.get(
        "/api/v1/admin/review-tasks",
        headers=headers,
        params={
            "review_status": "ready_for_review",
            "keyword": "Candidate",
            "admin_area": "West Lake",
            "place_kind": "attraction",
            "limit": 1,
            "offset": 0,
        },
    )
    assert review_queue.status_code == 200
    assert review_queue.json()["total"] == 1
    review_item = review_queue.json()["items"][0]
    assert review_item["place_revision_id"] == "revision-search"
    assert review_item["canonical_name"] == "Candidate Place"
    assert review_item["admin_area"] == "West Lake"
    assert review_item["place_kind"] == "attraction"
    assert review_item["category"] == "museum"
    assert review_item["revision_number"] == 1

    empty_review_page = context.client.get(
        "/api/v1/admin/review-tasks",
        headers=headers,
        params={"keyword": "Candidate", "limit": 1, "offset": 1},
    )
    assert empty_review_page.status_code == 200
    assert empty_review_page.json()["items"] == []
    assert empty_review_page.json()["total"] == 1

    audit_results = context.client.get(
        "/api/v1/admin/audit-events",
        headers=headers,
        params={"keyword": "ADMIN_ACTOR_CREATE", "limit": 1, "offset": 0},
    )
    assert audit_results.status_code == 200
    assert audit_results.json()["total"] == 1
    assert audit_results.json()["items"][0]["action"] == "ADMIN_ACTOR_CREATE"
    assert audit_results.json()["items"][0]["actor_login_name"] == ROOT_LOGIN

    audit_by_login = context.client.get(
        "/api/v1/admin/audit-events",
        headers=headers,
        params={
            "actor_login_name": "root.ad",
            "action": "ADMIN_ACTOR_CREATE",
            "limit": 1,
            "offset": 0,
        },
    )
    assert audit_by_login.status_code == 200
    assert audit_by_login.json()["total"] == 1
    assert audit_by_login.json()["items"][0]["actor_login_name"] == ROOT_LOGIN

    audit_by_login_keyword = context.client.get(
        "/api/v1/admin/audit-events",
        headers=headers,
        params={"keyword": ROOT_LOGIN, "limit": 1, "offset": 0},
    )
    assert audit_by_login_keyword.status_code == 200
    assert audit_by_login_keyword.json()["total"] >= 1
    assert audit_by_login_keyword.json()["items"][0]["actor_login_name"] == ROOT_LOGIN

    missing_actor_audits = context.client.get(
        "/api/v1/admin/audit-events",
        headers=headers,
        params={"actor_login_name": "missing.admin", "limit": 1, "offset": 0},
    )
    assert missing_actor_audits.status_code == 200
    assert missing_actor_audits.json()["items"] == []
    assert missing_actor_audits.json()["total"] == 0


def test_reviewer_can_decide_each_active_evidence_with_idempotency_and_audit(
    admin_context: AdminTestContext,
) -> None:
    context = admin_context
    _seed_candidate_revision(context, "revision-review-evidence")
    with context.sessions() as session:
        session.add(
            PlaceGeometryRow(
                geometry_id="geometry-review",
                place_revision_id="revision-review-evidence",
                geometry_kind="point",
                geometry={"type": "Point", "coordinates": [120.15, 30.25]},
                source_record_id="source-review",
                review_status="candidate",
                active=True,
                created_at=NOW.isoformat(),
                reviewed_at=None,
            )
        )
        session.add(
            PlaceRow(
                place_id="place-2",
                city_id="hangzhou",
                status="active",
                merged_into_place_id=None,
                created_at=NOW.isoformat(),
                updated_at=NOW.isoformat(),
            )
        )
        session.add(
            PlaceRelationRow(
                relation_id="relation-review",
                from_place_id="place-1",
                to_place_id="place-2",
                relation_type="overlaps",
                source_record_id="source-review",
                review_status="candidate",
                resolution_status="resolved",
                decision_note="测试关系已裁决",
                active=True,
                created_at=NOW.isoformat(),
                reviewed_at=None,
            )
        )
        session.commit()

    _, root_headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)
    payload = {
        "operation_intent_id": "review-geometry-1",
        "review_status": "human_verified",
        "reason_code": "EVIDENCE_APPROVED",
    }
    path = (
        "/api/v1/admin/place-revisions/revision-review-evidence/"
        "evidence/geometry/geometry-review/review"
    )
    before_submit = context.client.post(path, headers=root_headers, json=payload)
    assert before_submit.status_code == 404
    assert before_submit.json()["error"]["code"] == "review_task_not_found"
    submitted = context.client.post(
        "/api/v1/admin/place-revisions/revision-review-evidence/review-tasks",
        headers=root_headers,
        json={
            "operation_intent_id": "submit-review-evidence",
            "reason_code": "READY_FOR_REVIEW",
        },
    )
    assert submitted.status_code == 201
    premature_revision_approval = context.client.post(
        f"/api/v1/admin/review-tasks/{submitted.json()['review_task_id']}/decisions",
        headers=root_headers,
        json={
            "operation_intent_id": "premature-approve-review-evidence",
            "expected_version": 1,
            "decision_kind": "approve",
            "reason_code": "FACTS_VERIFIED",
        },
    )
    assert premature_revision_approval.status_code == 409
    assert premature_revision_approval.json()["error"]["code"] == (
        "review_revision_not_approvable"
    )
    approved = context.client.post(path, headers=root_headers, json=payload)
    assert approved.status_code == 200
    relation_payload = {
        "operation_intent_id": "review-relation-1",
        "review_status": "human_verified",
        "reason_code": "EVIDENCE_APPROVED",
    }
    relation_path = (
        "/api/v1/admin/place-revisions/revision-review-evidence/"
        "evidence/relation/relation-review/review"
    )
    relation_approved = context.client.post(
        relation_path, headers=root_headers, json=relation_payload
    )
    assert relation_approved.status_code == 200
    replay = context.client.post(path, headers=root_headers, json=payload)
    assert replay.status_code == 200
    conflict = context.client.post(
        path,
        headers=root_headers,
        json={**payload, "review_status": "rejected"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "admin_operation_intent_conflict"

    invalid_kind = context.client.post(
        path.replace("/geometry/", "/unknown/"),
        headers=root_headers,
        json=payload,
    )
    assert invalid_kind.status_code == 422

    with context.sessions() as session:
        geometry = session.get(PlaceGeometryRow, "geometry-review")
        audits = tuple(
            session.scalars(
                select(AdminAuditEventRow).where(
                    AdminAuditEventRow.operation_intent_id == "review-geometry-1"
                )
            )
        )
    assert geometry is not None
    assert geometry.review_status == "human_verified"
    assert datetime.fromisoformat(geometry.reviewed_at) == NOW
    assert len(audits) == 1
    assert audits[0].action == "PLACE_EVIDENCE_REVIEWED"
    assert audits[0].before_digest != audits[0].after_digest

    revision_approved = context.client.post(
        f"/api/v1/admin/review-tasks/{submitted.json()['review_task_id']}/decisions",
        headers=root_headers,
        json={
            "operation_intent_id": "approve-review-evidence-revision",
            "expected_version": 1,
            "decision_kind": "approve",
            "reason_code": "FACTS_VERIFIED",
        },
    )
    assert revision_approved.status_code == 200
    with context.sessions() as session:
        revision = session.get(PlaceRevisionRow, "revision-review-evidence")
    assert revision is not None
    assert revision.lifecycle_status == "human_verified"

    editor_payload = {
        "operation_intent_id": "create-evidence-editor",
        "login_name": "evidence.editor",
        "initial_password": EDITOR_PASSWORD,
        "role_keys": ["data_editor"],
        "reason_code": "OM1_TEAM_PROVISIONING",
    }
    assert context.client.post(
        "/api/v1/admin/admin-actors",
        headers=root_headers,
        json=editor_payload,
    ).status_code == 201
    _, editor_headers = _login(context.client, "evidence.editor", EDITOR_PASSWORD)
    forbidden = context.client.post(
        path,
        headers=editor_headers,
        json={**payload, "operation_intent_id": "editor-review-attempt"},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "admin_permission_denied"


def test_time_evidence_crud_review_and_revision_gate_form_one_versioned_workflow(
    admin_context: AdminTestContext,
) -> None:
    context = admin_context
    revision_id = "revision-time-crud"
    _seed_candidate_revision(context, revision_id)
    with context.sessions() as session:
        session.add(
            PlaceSourceRecordRow(
                source_record_id="source-time-crud",
                place_id="place-1",
                source_id="official-opening-hours",
                registry_id="registry-v1",
                registry_sha256="a" * 64,
                field_dictionary_id="dictionary-v1",
                field_dictionary_sha256="b" * 64,
                source_url="https://example.test/opening-hours",
                collection_mode="manual_reference",
                target_stage="staging",
                source_decision="approved",
                observed_at=NOW.isoformat(),
                content_sha256="c" * 64,
                status="active",
                created_at=NOW.isoformat(),
            )
        )
        session.commit()

    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)
    common = {
        "source_record_id": "source-time-crud",
        "reason_code": "TIME_EVIDENCE_EDITED",
    }
    time_rule = {
        **common,
        "expected_revision_version": 1,
        "rule_kind": "fixed_session",
        "weekdays": [5, 6],
        "start_minute": 1410,
        "end_minute": 1470,
        "last_entry_minute": 1400,
        "valid_from": "2026-09-01",
        "valid_to": "2026-12-31",
        "operation_intent_id": "create-time-rule",
    }
    created_rule = context.client.post(
        f"/api/v1/admin/place-revisions/{revision_id}/time-rules",
        headers=headers,
        json=time_rule,
    )
    assert created_rule.status_code == 200
    assert created_rule.json()["revision_version"] == 2
    assert created_rule.json()["solver_eligible"] is False

    replay = context.client.post(
        f"/api/v1/admin/place-revisions/{revision_id}/time-rules",
        headers=headers,
        json=time_rule,
    )
    assert replay.status_code == 200
    assert replay.json()["revision_version"] == 2

    evidence = context.client.get(
        f"/api/v1/admin/place-revisions/{revision_id}/evidence",
        headers=headers,
    ).json()
    time_rule_id = evidence["time_rules"][0]["time_rule_id"]
    updated_rule = context.client.patch(
        f"/api/v1/admin/place-revisions/{revision_id}/time-rules/{time_rule_id}",
        headers=headers,
        json={
            **time_rule,
            "expected_revision_version": 2,
            "end_minute": 1500,
            "operation_intent_id": "update-time-rule",
        },
    )
    assert updated_rule.status_code == 200
    assert updated_rule.json()["revision_version"] == 3

    created_closure = context.client.post(
        f"/api/v1/admin/place-revisions/{revision_id}/closures",
        headers=headers,
        json={
            **common,
            "expected_revision_version": 3,
            "weekday": 1,
            "operation_intent_id": "create-closure",
        },
    )
    assert created_closure.status_code == 200
    assert created_closure.json()["revision_version"] == 4
    evidence = context.client.get(
        f"/api/v1/admin/place-revisions/{revision_id}/evidence",
        headers=headers,
    ).json()
    closure_id = evidence["closures"][0]["closure_id"]
    updated_closure = context.client.patch(
        f"/api/v1/admin/place-revisions/{revision_id}/closures/{closure_id}",
        headers=headers,
        json={
            **common,
            "expected_revision_version": 4,
            "weekday": 2,
            "operation_intent_id": "update-closure",
        },
    )
    assert updated_closure.status_code == 200
    assert updated_closure.json()["revision_version"] == 5

    exception_payload = {
        **common,
        "expected_revision_version": 5,
        "service_date": "2026-10-01",
        "exception_kind": "session_override",
        "start_minute": 1500,
        "end_minute": 1560,
        "last_entry_minute": 1490,
        "operation_intent_id": "create-date-exception",
    }
    created_exception = context.client.post(
        f"/api/v1/admin/place-revisions/{revision_id}/date-exceptions",
        headers=headers,
        json=exception_payload,
    )
    assert created_exception.status_code == 200
    assert created_exception.json()["revision_version"] == 6
    evidence = context.client.get(
        f"/api/v1/admin/place-revisions/{revision_id}/evidence",
        headers=headers,
    ).json()
    date_exception_id = evidence["date_exceptions"][0]["date_exception_id"]
    updated_exception = context.client.patch(
        f"/api/v1/admin/place-revisions/{revision_id}/date-exceptions/{date_exception_id}",
        headers=headers,
        json={
            **exception_payload,
            "expected_revision_version": 6,
            "end_minute": 1590,
            "operation_intent_id": "update-date-exception",
        },
    )
    assert updated_exception.status_code == 200
    assert updated_exception.json()["revision_version"] == 7

    for version, kind, evidence_id in (
        (7, "time-rules", time_rule_id),
        (9, "closures", closure_id),
        (11, "date-exceptions", date_exception_id),
    ):
        retired = context.client.request(
            "DELETE",
            f"/api/v1/admin/place-revisions/{revision_id}/{kind}/{evidence_id}",
            headers=headers,
            json={
                "expected_revision_version": version,
                "operation_intent_id": f"retire-{kind}",
                "reason_code": "TIME_EVIDENCE_RETIRED",
            },
        )
        assert retired.status_code == 200
        assert retired.json()["revision_version"] == version + 1
        current = context.client.get(
            f"/api/v1/admin/place-revisions/{revision_id}/evidence",
            headers=headers,
        ).json()
        key = {
            "time-rules": "time_rules",
            "closures": "closures",
            "date-exceptions": "date_exceptions",
        }[kind]
        retired_item = next(
            item for item in current[key] if evidence_id in item.values()
        )
        assert retired_item["active"] is False

        if kind == "time-rules":
            restore_payload = {
                **time_rule,
                "expected_revision_version": version + 1,
                "end_minute": 1500,
                "operation_intent_id": "restore-time-rule",
            }
        elif kind == "closures":
            restore_payload = {
                **common,
                "expected_revision_version": version + 1,
                "weekday": 2,
                "operation_intent_id": "restore-closure",
            }
        else:
            restore_payload = {
                **exception_payload,
                "expected_revision_version": version + 1,
                "end_minute": 1590,
                "operation_intent_id": "restore-date-exception",
            }
        restored = context.client.patch(
            f"/api/v1/admin/place-revisions/{revision_id}/{kind}/{evidence_id}",
            headers=headers,
            json=restore_payload,
        )
        assert restored.status_code == 200
        assert restored.json()["revision_version"] == version + 2

    submitted = context.client.post(
        f"/api/v1/admin/place-revisions/{revision_id}/review-tasks",
        headers=headers,
        json={
            "operation_intent_id": "submit-time-evidence",
            "reason_code": "READY_FOR_REVIEW",
        },
    )
    assert submitted.status_code == 201
    task_id = submitted.json()["review_task_id"]
    premature = context.client.post(
        f"/api/v1/admin/review-tasks/{task_id}/decisions",
        headers=headers,
        json={
            "operation_intent_id": "premature-time-approval",
            "expected_version": 1,
            "decision_kind": "approve",
            "reason_code": "FACTS_VERIFIED",
        },
    )
    assert premature.status_code == 409
    assert premature.json()["error"]["code"] == "review_revision_not_approvable"

    for kind, evidence_id in (
        ("time_rule", time_rule_id),
        ("closure", closure_id),
        ("date_exception", date_exception_id),
    ):
        reviewed = context.client.post(
            f"/api/v1/admin/place-revisions/{revision_id}/evidence/{kind}/{evidence_id}/review",
            headers=headers,
            json={
                "operation_intent_id": f"review-{kind}",
                "review_status": "human_verified",
                "reason_code": "EVIDENCE_APPROVED",
            },
        )
        assert reviewed.status_code == 200

    approved = context.client.post(
        f"/api/v1/admin/review-tasks/{task_id}/decisions",
        headers=headers,
        json={
            "operation_intent_id": "approve-time-revision",
            "expected_version": 1,
            "decision_kind": "approve",
            "reason_code": "FACTS_VERIFIED",
        },
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    final_evidence = context.client.get(
        f"/api/v1/admin/place-revisions/{revision_id}/evidence",
        headers=headers,
    ).json()
    assert final_evidence["time_rules"][0]["end_minute"] == 1500
    assert final_evidence["closures"][0]["weekday"] == 2
    assert final_evidence["date_exceptions"][0]["end_minute"] == 1590
    assert all(
        item["review_status"] == "human_verified"
        for item in (
            *final_evidence["time_rules"],
            *final_evidence["closures"],
            *final_evidence["date_exceptions"],
        )
    )

    with context.sessions() as session:
        actions = set(
            session.scalars(
                select(AdminAuditEventRow.action).where(
                    AdminAuditEventRow.target_type.in_(
                        ("place_time_rule", "place_closure", "place_date_exception")
                    )
                )
            )
        )
    assert {
        "PLACE_TIME_RULE_CREATED",
        "PLACE_TIME_RULE_UPDATED",
        "PLACE_TIME_RULE_RETIRED",
        "PLACE_CLOSURE_CREATED",
        "PLACE_CLOSURE_UPDATED",
        "PLACE_CLOSURE_RETIRED",
        "PLACE_DATE_EXCEPTION_CREATED",
        "PLACE_DATE_EXCEPTION_UPDATED",
        "PLACE_DATE_EXCEPTION_RETIRED",
        "PLACE_EVIDENCE_REVIEWED",
    } <= actions


def test_revision_evidence_is_revision_scoped_and_exposes_projection_endpoints(
    admin_context: AdminTestContext,
) -> None:
    context = admin_context
    _seed_candidate_revision(context, "revision-evidence")
    with context.sessions() as session:
        revision = session.get(PlaceRevisionRow, "revision-evidence")
        assert revision is not None
        revision.source_record_ids = [
            "source-evidence",
            "source-sensitive",
            "missing-source",
            "source-other-place",
        ]
        session.add(
            PlaceSourceRecordRow(
                source_record_id="source-evidence",
                place_id="place-1",
                source_id="manual-reference",
                registry_id="registry-v1",
                registry_sha256="a" * 64,
                field_dictionary_id="dictionary-v1",
                field_dictionary_sha256="b" * 64,
                source_url="https://example.test/evidence",
                collection_mode="manual_reference",
                target_stage="staging",
                source_decision="conditional",
                observed_at=NOW.isoformat(),
                content_sha256="c" * 64,
                status="active",
                created_at=NOW.isoformat(),
            )
        )
        session.add(
            PlaceSourceRecordRow(
                source_record_id="source-sensitive",
                place_id="place-1",
                source_id="manual-reference-sensitive",
                registry_id="registry-v1",
                registry_sha256="a" * 64,
                field_dictionary_id="dictionary-v1",
                field_dictionary_sha256="b" * 64,
                source_url=(
                    "https://example.test/evidence?x-api-key=private-value"
                    "&client_secret=private-secret&keep=1#fragment-token"
                ),
                collection_mode="manual_reference",
                target_stage="staging",
                source_decision="conditional",
                observed_at=NOW.isoformat(),
                content_sha256="e" * 64,
                status="active",
                created_at=NOW.isoformat(),
            )
        )
        session.add(
            PlaceRow(
                place_id="place-2",
                city_id="hangzhou",
                status="active",
                merged_into_place_id=None,
                created_at=NOW.isoformat(),
                updated_at=NOW.isoformat(),
            )
        )
        session.add(
            PlaceSourceRecordRow(
                source_record_id="source-other-place",
                place_id="place-2",
                source_id="other-place-source",
                registry_id="registry-v1",
                registry_sha256="a" * 64,
                field_dictionary_id="dictionary-v1",
                field_dictionary_sha256="b" * 64,
                source_url="https://other.example/leaked-source",
                collection_mode="manual_reference",
                target_stage="staging",
                source_decision="conditional",
                observed_at=NOW.isoformat(),
                content_sha256="f" * 64,
                status="active",
                created_at=NOW.isoformat(),
            )
        )
        session.add(
            PlaceGeometryRow(
                geometry_id="geometry-evidence",
                place_revision_id="revision-evidence",
                geometry_kind="point",
                geometry={"type": "Point", "coordinates": [120.15, 30.25]},
                source_record_id="source-evidence",
                review_status="candidate",
                active=True,
                created_at=NOW.isoformat(),
                reviewed_at=None,
            )
        )
        session.add(
            PlaceGeometryRow(
                geometry_id="geometry-cross-place",
                place_revision_id="revision-evidence",
                geometry_kind="point",
                geometry={"type": "Point", "coordinates": [120.16, 30.26]},
                source_record_id="source-other-place",
                review_status="human_verified",
                active=True,
                created_at=NOW.isoformat(),
                reviewed_at=NOW.isoformat(),
            )
        )
        session.add(
            PlaceAccessPointRow(
                access_point_id="access-evidence",
                place_revision_id="revision-evidence",
                access_point_kind="visitor_entrance",
                name="主入口",
                lat=30.25,
                lng=120.15,
                source_record_id="source-evidence",
                review_status="candidate",
                active=True,
                fetched_at=NOW.isoformat(),
                reviewed_at=None,
                created_at=NOW.isoformat(),
            )
        )
        session.add(
            PlaceTimeRuleRow(
                time_rule_id="time-rule-evidence",
                place_revision_id="revision-evidence",
                rule_kind="opening_hours",
                weekdays=[1, 2, 3, 4, 5, 6, 7],
                start_minute=9 * 60,
                end_minute=17 * 60 + 30,
                last_entry_minute=16 * 60 + 30,
                valid_from=date(2026, 1, 1),
                valid_to=date(2026, 12, 31),
                source_record_id="source-evidence",
                review_status="candidate",
                active=True,
                created_at=NOW.isoformat(),
                reviewed_at=None,
            )
        )
        session.add(
            PlaceClosureRow(
                closure_id="closure-evidence",
                place_revision_id="revision-evidence",
                weekday=1,
                source_record_id="source-evidence",
                review_status="candidate",
                active=True,
                created_at=NOW.isoformat(),
                reviewed_at=None,
            )
        )
        session.add(
            PlaceDateExceptionRow(
                date_exception_id="date-exception-evidence",
                place_revision_id="revision-evidence",
                service_date=date(2026, 10, 1),
                exception_kind="open_override",
                start_minute=8 * 60,
                end_minute=18 * 60,
                last_entry_minute=17 * 60,
                source_record_id="source-evidence",
                review_status="candidate",
                active=True,
                created_at=NOW.isoformat(),
                reviewed_at=None,
            )
        )
        session.add(
            PlaceAccessPointRow(
                access_point_id="access-cross-place",
                place_revision_id="revision-evidence",
                access_point_kind="visitor_exit",
                name="错绑出口",
                lat=30.26,
                lng=120.16,
                source_record_id="source-other-place",
                review_status="human_verified",
                active=True,
                fetched_at=NOW.isoformat(),
                reviewed_at=NOW.isoformat(),
                created_at=NOW.isoformat(),
            )
        )
        session.add(
            SolverPlaceProjectionRow(
                projection_id="projection-evidence",
                projection_version="projection-v1",
                data_snapshot_version="snapshot-evidence",
                place_id="place-1",
                place_revision_id="revision-evidence",
                solver_node_id=42,
                place_kind="attraction",
                geometry_kind="point",
                arrival_access_point_id="access-evidence",
                departure_access_point_id="access-evidence",
                duration_min=30,
                duration_recommended=60,
                duration_max=90,
                internal_travel_min=5,
                solver_payload={"source": "test"},
                projection_hash="d" * 64,
                status="candidate",
                gate_reason_codes=[],
                created_at=NOW.isoformat(),
                published_at=None,
            )
        )
        session.add(
            SolverPlaceProjectionRow(
                projection_id="projection-evidence-z",
                projection_version="projection-v1",
                data_snapshot_version="snapshot-evidence-2",
                place_id="place-1",
                place_revision_id="revision-evidence",
                solver_node_id=43,
                place_kind="attraction",
                geometry_kind="point",
                arrival_access_point_id="access-evidence",
                departure_access_point_id="access-evidence",
                duration_min=30,
                duration_recommended=60,
                duration_max=90,
                internal_travel_min=5,
                solver_payload={"source": "test-tie"},
                projection_hash="1" * 64,
                status="candidate",
                gate_reason_codes=[],
                created_at=NOW.isoformat(),
                published_at=None,
            )
        )
        session.commit()

    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)
    response = context.client.get(
        "/api/v1/admin/place-revisions/revision-evidence/evidence",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["revision"]["place_revision_id"] == "revision-evidence"
    assert body["sources"][0]["source_record_id"] == "source-evidence"
    valid_geometry = next(
        item for item in body["geometries"] if item["geometry_id"] == "geometry-evidence"
    )
    assert valid_geometry["geometry"] == {
        "type": "Point",
        "coordinates": [120.15, 30.25],
    }
    assert valid_geometry["source_record_valid"] is True
    cross_geometry = next(
        item for item in body["geometries"] if item["geometry_id"] == "geometry-cross-place"
    )
    assert cross_geometry["source_record_valid"] is False
    valid_access_point = next(
        item for item in body["access_points"] if item["access_point_id"] == "access-evidence"
    )
    assert valid_access_point["lat"] == pytest.approx(30.25)
    assert valid_access_point["source_record_valid"] is True
    assert body["time_rules"][0]["time_rule_id"] == "time-rule-evidence"
    assert body["time_rules"][0]["source_record_valid"] is True
    assert body["closures"][0]["weekday"] == 1
    assert body["closures"][0]["source_record_valid"] is True
    assert body["date_exceptions"][0]["service_date"] == "2026-10-01"
    assert body["date_exceptions"][0]["source_record_valid"] is True
    cross_access_point = next(
        item for item in body["access_points"] if item["access_point_id"] == "access-cross-place"
    )
    assert cross_access_point["source_record_valid"] is False
    assert body["projection"]["arrival_access_point_id"] == "access-evidence"
    assert body["projection"]["departure_access_point_id"] == "access-evidence"
    assert body["projection"]["projection_id"] == "projection-evidence-z"
    assert body["sources"][1]["source_record_id"] == "source-sensitive"
    assert body["sources"][1]["source_url_redacted"] is True
    assert "private-value" not in response.text
    assert "fragment-token" not in response.text
    assert "other.example" not in response.text
    assert body["missing_source_record_ids"] == [
        "missing-source",
        "source-other-place",
    ]

    unauthenticated = context.client.get(
        "/api/v1/admin/place-revisions/revision-evidence/evidence"
    )
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["code"] == "admin_authentication_required"

    missing = context.client.get(
        "/api/v1/admin/place-revisions/missing/evidence",
        headers=headers,
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "resource_not_found"


def test_safe_source_url_redacts_credential_variants_and_preserves_ipv6() -> None:
    redacted = safe_source_url(
        "https://[::1]:8080/path?X-API-Key=private-key"
        "&client_secret=private-secret&access-token=private-token&keep=1#fragment"
    )

    assert "private-key" not in redacted
    assert "private-secret" not in redacted
    assert "private-token" not in redacted
    assert "fragment" not in redacted
    assert redacted.startswith("https://[::1]:8080/path?")
    parsed = urlsplit(redacted)
    assert parsed.hostname == "::1"
    assert parsed.port == 8080
    assert parse_qsl(parsed.query, keep_blank_values=True)[-1] == ("keep", "1")

    assert safe_source_url("https://example.test:invalid/path") == "[invalid source URL]"
    assert safe_source_url("https://[::1/path") == "[invalid source URL]"


def test_revision_editing_creates_new_candidate_and_keeps_base_immutable(
    admin_context: AdminTestContext,
) -> None:
    context = admin_context
    _seed_candidate_revision(context, "revision-base")
    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)

    created = context.client.post(
        "/api/v1/admin/places/place-1/revisions",
        headers=headers,
        json={
            "base_revision_id": "revision-base",
            "operation_intent_id": "create-revision-1",
            "reason_code": "PLACE_FACTS_REFRESH",
        },
    )
    assert created.status_code == 201
    assert created.json()["revision_number"] == 2
    assert created.json()["lifecycle_status"] == "candidate"
    assert created.json()["solver_eligible"] is False
    new_revision_id = created.json()["place_revision_id"]

    created_replay = context.client.post(
        "/api/v1/admin/places/place-1/revisions",
        headers=headers,
        json={
            "base_revision_id": "revision-base",
            "operation_intent_id": "create-revision-1",
            "reason_code": "PLACE_FACTS_REFRESH",
        },
    )
    assert created_replay.status_code == 201
    assert created_replay.json()["place_revision_id"] == new_revision_id

    updated = context.client.patch(
        f"/api/v1/admin/place-revisions/{new_revision_id}",
        headers=headers,
        json={
            "expected_revision_number": 2,
            "operation_intent_id": "update-revision-1",
            "reason_code": "PLACE_FACTS_EDITED",
            "canonical_name": "Updated Candidate Place",
            "duration_recommended": 90,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["canonical_name"] == "Updated Candidate Place"
    assert updated.json()["duration_recommended"] == 90

    updated_replay = context.client.patch(
        f"/api/v1/admin/place-revisions/{new_revision_id}",
        headers=headers,
        json={
            "expected_revision_number": 2,
            "operation_intent_id": "update-revision-1",
            "reason_code": "PLACE_FACTS_EDITED",
            "canonical_name": "Updated Candidate Place",
            "duration_recommended": 90,
        },
    )
    assert updated_replay.status_code == 200
    assert updated_replay.json()["canonical_name"] == "Updated Candidate Place"

    update_intent_conflict = context.client.patch(
        f"/api/v1/admin/place-revisions/{new_revision_id}",
        headers=headers,
        json={
            "expected_revision_number": 2,
            "operation_intent_id": "update-revision-1",
            "reason_code": "PLACE_FACTS_EDITED",
            "canonical_name": "Different Place",
        },
    )
    assert update_intent_conflict.status_code == 409
    assert update_intent_conflict.json()["error"]["code"] == "admin_operation_intent_conflict"

    base = context.client.get(
        "/api/v1/admin/place-revisions/revision-base", headers=headers
    )
    assert base.status_code == 200
    assert base.json()["canonical_name"] == "Candidate Place"

    task = context.client.post(
        "/api/v1/admin/place-revisions/revision-base/review-tasks",
        headers=headers,
        json={
            "operation_intent_id": "submit-revision-base",
            "reason_code": "READY_FOR_REVIEW",
        },
    )
    assert task.status_code == 201
    decision = context.client.post(
        f"/api/v1/admin/review-tasks/{task.json()['review_task_id']}/decisions",
        headers=headers,
        json={
            "operation_intent_id": "approve-revision-base",
            "expected_version": 1,
            "decision_kind": "approve",
            "reason_code": "FACTS_VERIFIED",
        },
    )
    assert decision.status_code == 200

    immutable = context.client.patch(
        "/api/v1/admin/place-revisions/revision-base",
        headers=headers,
        json={
            "expected_revision_number": 1,
            "operation_intent_id": "update-revision-base",
            "reason_code": "PLACE_FACTS_EDITED",
            "canonical_name": "Should Be Rejected",
        },
    )
    assert immutable.status_code == 409
    assert immutable.json()["error"]["code"] == "review_revision_not_candidate"


def test_new_revision_copies_active_evidence_as_unverified_children(
    admin_context: AdminTestContext,
) -> None:
    context = admin_context
    _seed_candidate_revision(context, "revision-with-evidence")
    with context.sessions() as session:
        session.add(PlaceSourceRecordRow(
            source_record_id="source-copy", place_id="place-1", source_id="manual",
            registry_id="registry-v1", registry_sha256="a" * 64,
            field_dictionary_id="fields-v1", field_dictionary_sha256="b" * 64,
            source_url="https://example.test/source", collection_mode="manual_reference",
            target_stage="staging", source_decision="approved", observed_at=NOW.isoformat(),
            content_sha256="c" * 64, status="active", created_at=NOW.isoformat(),
        ))
        base = session.get(PlaceRevisionRow, "revision-with-evidence")
        assert base is not None
        base.source_record_ids = ["source-copy"]
        session.add(PlaceGeometryRow(
            geometry_id="geometry-copy", place_revision_id=base.place_revision_id,
            geometry_kind="point", geometry={"type": "Point", "coordinates": [120.1, 30.2]},
            source_record_id="source-copy", review_status="human_verified", active=True,
            created_at=NOW.isoformat(), reviewed_at=NOW.isoformat(),
        ))
        session.add(PlaceAccessPointRow(
            access_point_id="access-copy", place_revision_id=base.place_revision_id,
            access_point_kind="visitor_entrance", name="主入口", lat=30.2, lng=120.1,
            source_record_id="source-copy", review_status="human_verified", active=True,
            fetched_at=NOW.isoformat(), reviewed_at=NOW.isoformat(), created_at=NOW.isoformat(),
        ))
        session.add(PlaceTimeRuleRow(
            time_rule_id="time-copy", place_revision_id=base.place_revision_id,
            rule_kind="opening_hours", weekdays=[1, 2, 3, 4, 5, 6, 7],
            start_minute=540, end_minute=1020, last_entry_minute=990,
            valid_from=None, valid_to=None, source_record_id="source-copy",
            review_status="human_verified", active=True,
            created_at=NOW.isoformat(), reviewed_at=NOW.isoformat(),
        ))
        session.commit()

    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)
    response = context.client.post(
        "/api/v1/admin/places/place-1/revisions", headers=headers,
        json={"base_revision_id": "revision-with-evidence", "operation_intent_id": "copy-evidence-1", "reason_code": "PLACE_FACTS_REFRESH"},
    )
    assert response.status_code == 201, response.text
    new_id = response.json()["place_revision_id"]
    with context.sessions() as session:
        geometries = tuple(session.scalars(select(PlaceGeometryRow).where(PlaceGeometryRow.place_revision_id == new_id)))
        access_points = tuple(session.scalars(select(PlaceAccessPointRow).where(PlaceAccessPointRow.place_revision_id == new_id)))
        time_rules = tuple(session.scalars(select(PlaceTimeRuleRow).where(PlaceTimeRuleRow.place_revision_id == new_id)))
    assert len(geometries) == len(access_points) == len(time_rules) == 1
    assert geometries[0].geometry_id != "geometry-copy"
    assert access_points[0].access_point_id != "access-copy"
    assert time_rules[0].time_rule_id != "time-copy"
    assert geometries[0].review_status == access_points[0].review_status == time_rules[0].review_status == "candidate"
    assert geometries[0].reviewed_at is None and access_points[0].reviewed_at is None and time_rules[0].reviewed_at is None
def test_place_review_request_changes_keeps_candidate_and_rejects_stale_version(
    admin_context: AdminTestContext,
) -> None:
    context = admin_context
    _seed_candidate_revision(context, "revision-2")
    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)
    task = context.client.post(
        "/api/v1/admin/place-revisions/revision-2/review-tasks",
        headers=headers,
        json={
            "operation_intent_id": "review-submit-2",
            "reason_code": "OM1_CANDIDATE_READY",
        },
    ).json()
    decision = {
        "operation_intent_id": "review-changes-2",
        "expected_version": 1,
        "decision_kind": "request_changes",
        "reason_code": "OM1_SOURCE_MISSING",
        "reason_text": "请补充来源记录",
    }
    changed = context.client.post(
        f"/api/v1/admin/review-tasks/{task['review_task_id']}/decisions",
        headers=headers,
        json=decision,
    )
    assert changed.status_code == 200
    assert changed.json()["status"] == "changes_requested"

    stale = context.client.post(
        f"/api/v1/admin/review-tasks/{task['review_task_id']}/decisions",
        headers=headers,
        json={**decision, "operation_intent_id": "review-stale-2"},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "review_task_conflict"
    with context.sessions() as session:
        revision = session.get(PlaceRevisionRow, "revision-2")
    assert revision is not None
    assert revision.lifecycle_status == "candidate"


def test_resubmitting_after_changes_requested_reopens_task_for_review(
    admin_context: AdminTestContext,
) -> None:
    context = admin_context
    _seed_candidate_revision(context, "revision-resubmit")
    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)
    submit_path = "/api/v1/admin/place-revisions/revision-resubmit/review-tasks"
    first = context.client.post(
        submit_path,
        headers=headers,
        json={"operation_intent_id": "resubmit-first", "reason_code": "READY_FOR_REVIEW"},
    )
    assert first.status_code == 201
    task_id = first.json()["review_task_id"]
    changed = context.client.post(
        f"/api/v1/admin/review-tasks/{task_id}/decisions",
        headers=headers,
        json={
            "operation_intent_id": "resubmit-changes",
            "expected_version": 1,
            "decision_kind": "request_changes",
            "reason_code": "OM1_SOURCE_MISSING",
            "reason_text": "请补充来源记录",
        },
    )
    assert changed.status_code == 200
    assert changed.json()["status"] == "changes_requested"

    reopened = context.client.post(
        submit_path,
        headers=headers,
        json={"operation_intent_id": "resubmit-second", "reason_code": "READY_FOR_REVIEW"},
    )
    assert reopened.status_code == 201
    assert reopened.json()["review_task_id"] == task_id
    assert reopened.json()["status"] == "ready_for_review"
    assert reopened.json()["version"] == 3

    queue = context.client.get(
        "/api/v1/admin/review-tasks?review_status=ready_for_review",
        headers=headers,
    )
    assert queue.status_code == 200
    assert any(item["review_task_id"] == task_id for item in queue.json()["items"])


def test_review_rejects_non_candidate_revision_and_audits_rejection(
    admin_context: AdminTestContext,
) -> None:
    context = admin_context
    _seed_candidate_revision(context, "revision-3")
    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)
    task = context.client.post(
        "/api/v1/admin/place-revisions/revision-3/review-tasks",
        headers=headers,
        json={
            "operation_intent_id": "review-submit-3",
            "reason_code": "OM1_CANDIDATE_READY",
        },
    ).json()
    approved = context.client.post(
        f"/api/v1/admin/review-tasks/{task['review_task_id']}/decisions",
        headers=headers,
        json={
            "operation_intent_id": "review-approve-3",
            "expected_version": 1,
            "decision_kind": "approve",
            "reason_code": "OM1_FACTS_VERIFIED",
        },
    )
    assert approved.status_code == 200
    rejected = context.client.post(
        "/api/v1/admin/place-revisions/revision-3/review-tasks",
        headers=headers,
        json={
            "operation_intent_id": "review-submit-again-3",
            "reason_code": "OM1_CANDIDATE_READY",
        },
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "review_revision_not_candidate"


def test_editing_uncollected_candidate_recommended_duration_establishes_valid_range(
    admin_context: AdminTestContext,
) -> None:
    with admin_context.sessions() as session:
        session.add(PlaceRow(
            place_id="place-duration", city_id="hangzhou", status="active",
            merged_into_place_id=None, created_at=NOW.isoformat(), updated_at=NOW.isoformat(),
        ))
        session.add(PlaceRevisionRow(
            place_revision_id="revision-duration", place_id="place-duration", revision_number=1,
            lifecycle_status="candidate", canonical_name="待采集时长地点", aliases=[],
            place_kind="attraction", category="museum", admin_area="西湖区", address=None,
            geometry_kind="point", duration_min=1, duration_recommended=1, duration_max=1,
            internal_travel_min=0, energy_level=2, indoor_outdoor="indoor",
            suitable_periods=["morning"], audience_tags=[], rain_suitability="suitable",
            is_always_open=False, solver_eligible=False, conflicts_resolved=False,
            source_record_ids=["source-duration"], created_at=NOW.isoformat(),
            reviewed_at=None, published_at=None,
            review_flags=["DURATION_NOT_COLLECTED"],
        ))
        session.commit()
    _, headers = _login(admin_context.client, ROOT_LOGIN, ROOT_PASSWORD)
    response = admin_context.client.patch(
        "/api/v1/admin/place-revisions/revision-duration",
        headers=headers,
        json={
            "expected_revision_number": 1,
            "operation_intent_id": "update-duration-only",
            "reason_code": "PLACE_FACTS_EDITED",
            "duration_recommended": 60,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["duration_min"], body["duration_recommended"], body["duration_max"]) == (60, 60, 60)
    assert "DURATION_NOT_COLLECTED" not in body["review_flags"]
