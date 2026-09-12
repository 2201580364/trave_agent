"""H3/S7-1: revision lifecycle writes keep evidence and audit atomic."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from tests.application.test_admin_identity_http import (
    ROOT_LOGIN,
    ROOT_PASSWORD,
    AdminTestContext,
    _login,
    _seed_approvable_candidate,
)
from tests.application.test_admin_identity_http import admin_context as admin_context
from travel_agent.infrastructure.database.admin_identity import (
    AdminAuditEventRow,
    SqlAlchemyAdminAuditRepository,
)
from travel_agent.infrastructure.database.place_catalog import (
    PlaceAccessPointRow,
    PlaceClosureRow,
    PlaceDateExceptionRow,
    PlaceGeometryRow,
    PlaceRevisionRow,
    PlaceTimeRuleRow,
)


@pytest.mark.parametrize("operation", ["create", "update", "evidence"])
def test_revision_lifecycle_audit_failure_rolls_back_and_retries(
    admin_context: AdminTestContext, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    context = admin_context
    _seed_approvable_candidate(context, "revision-lifecycle-base")
    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)
    create_url = "/api/v1/admin/places/place-1/revisions"
    create_payload = {
        "base_revision_id": "revision-lifecycle-base",
        "operation_intent_id": "lifecycle-create",
        "reason_code": "PLACE_FACTS_REFRESH",
    }
    if operation == "create":
        url, payload, status = create_url, create_payload, 201
    else:
        created = context.client.post(create_url, headers=headers, json=create_payload)
        assert created.status_code == 201, created.text
        rid = created.json()["place_revision_id"]
        if operation == "update":
            url = f"/api/v1/admin/place-revisions/{rid}"
            payload = {
                "expected_revision_number": 2,
                "operation_intent_id": "lifecycle-update",
                "reason_code": "PLACE_FACTS_EDITED",
                "canonical_name": "Changed",
            }
        else:
            root = f"/api/v1/admin/place-revisions/{rid}"
            submitted = context.client.post(
                root + "/review-tasks",
                headers=headers,
                json={"operation_intent_id": "lifecycle-submit", "reason_code": "READY_FOR_REVIEW"},
            )
            assert submitted.status_code == 201, submitted.text
            evidence = context.client.get(root + "/evidence", headers=headers).json()
            geometry_id = evidence["geometries"][0]["geometry_id"]
            url = root + f"/evidence/geometry/{geometry_id}/review"
            payload = {
                "operation_intent_id": "lifecycle-evidence",
                "review_status": "human_verified",
                "reason_code": "EVIDENCE_APPROVED",
            }
        status = 200

    def state():
        with context.sessions() as session:
            return [
                [dict(row) for row in session.execute(select(model.__table__)).mappings()]
                for model in (
                    PlaceRevisionRow,
                    PlaceGeometryRow,
                    PlaceAccessPointRow,
                    PlaceTimeRuleRow,
                    PlaceClosureRow,
                    PlaceDateExceptionRow,
                    AdminAuditEventRow,
                )
            ]

    method = "PATCH" if operation == "update" else "POST"
    before = state()
    add = SqlAlchemyAdminAuditRepository.add

    def fail(repository, event):
        add(repository, event)
        raise RuntimeError("simulated lifecycle audit failure")

    with monkeypatch.context() as patch:
        patch.setattr(SqlAlchemyAdminAuditRepository, "add", fail)
        with pytest.raises(RuntimeError, match="simulated lifecycle audit failure"):
            context.client.request(method, url, headers=headers, json=payload)
    assert state() == before
    result = context.client.request(method, url, headers=headers, json=payload)
    assert result.status_code == status, result.text
    committed = state()
    assert (
        context.client.request(method, url, headers=headers, json=payload).json() == result.json()
    )
    assert state() == committed
