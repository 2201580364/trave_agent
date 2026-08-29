"""G7-R0.2-05-01 administrator identity, RBAC, and audit tests."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from travel_agent.application.admin import AdminIdentityService, PlaceReviewWorkflowService
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
from travel_agent.infrastructure.database.place_catalog import PlaceRevisionRow, PlaceRow
from travel_agent.infrastructure.database.place_review import PlaceReviewDecisionRow
from travel_agent.infrastructure.memory import (
    FixedDataSnapshotVersionProvider,
    InMemoryGenerationExecutor,
    SequenceIdGenerator,
)
from travel_agent.interfaces.http import HttpContainer, create_app

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
            lambda: SqlAlchemyAdminUnitOfWork(sessions), clock, ids
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

    assert revision == "0008_place_review_workflow"
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
