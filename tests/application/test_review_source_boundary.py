"""S7-1/H3: extracted source writes keep audit atomicity and retry semantics."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from tests.application.test_admin_identity_http import (
    NOW,
    ROOT_LOGIN,
    ROOT_PASSWORD,
    AdminTestContext,
    _login,
    _seed_candidate_revision,
)
from tests.application.test_admin_identity_http import admin_context as admin_context
from travel_agent.domain.admin import AdminAuditEvent
from travel_agent.infrastructure.database.admin_identity import (
    AdminAuditEventRow,
    SqlAlchemyAdminAuditRepository,
)
from travel_agent.infrastructure.database.place_catalog import (
    PlaceRevisionRow,
    PlaceSourceRecordRow,
)


@pytest.mark.parametrize("operation", ["create_source", "resolve_conflict"])
def test_source_write_rolls_back_with_audit_then_retries_once(
    admin_context: AdminTestContext, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    context = admin_context
    revision_id = "revision-source-boundary"
    _seed_candidate_revision(context, revision_id)
    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)
    payload = {
        "expected_revision_version": 1,
        "operation_intent_id": "source-boundary-retry",
        "reason_code": "SOURCE_EVIDENCE_CONFIRMED",
    }
    if operation == "create_source":
        suffix = "source-records"
        payload.update(
            source_id="hangzhou-westlake-admin-public-web",
            source_url="https://westlake.hangzhou.gov.cn/art/2026/8/29/example.html",
            collection_mode="manual_reference",
            observed_at=NOW.isoformat(),
            content_sha256="c" * 64,
        )
    else:
        suffix = "source-conflicts/resolve"
        payload.update(expected_revision_number=1, resolved=True)
    url = f"/api/v1/admin/place-revisions/{revision_id}/{suffix}"

    def state() -> tuple[object, ...]:
        with context.sessions() as session:
            revision = session.get(PlaceRevisionRow, revision_id)
            assert revision is not None
            return (
                revision.revision_version,
                revision.conflicts_resolved,
                tuple(revision.source_record_ids),
                session.scalar(select(func.count()).select_from(PlaceSourceRecordRow)),
                session.scalar(select(func.count()).select_from(AdminAuditEventRow)),
            )

    before = state()
    original_add = SqlAlchemyAdminAuditRepository.add

    def fail_after_audit_add(
        repository: SqlAlchemyAdminAuditRepository, event: AdminAuditEvent
    ) -> None:
        original_add(repository, event)
        raise RuntimeError("simulated audit persistence failure")

    with monkeypatch.context() as patch:
        patch.setattr(SqlAlchemyAdminAuditRepository, "add", fail_after_audit_add)
        with pytest.raises(RuntimeError, match="simulated audit persistence failure"):
            context.client.post(url, headers=headers, json=payload)
    assert state() == before

    response = context.client.post(url, headers=headers, json=payload)
    assert response.status_code == (201 if operation == "create_source" else 200), response.text
    assert response.json()["revision_version"] == 2
    committed = state()
    replay = context.client.post(url, headers=headers, json=payload)
    assert replay.status_code == response.status_code
    assert replay.json() == response.json()
    assert state() == committed
