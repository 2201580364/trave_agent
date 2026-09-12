"""H3/S7-1: relation decisions retain revision and audit atomicity."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from tests.application.test_admin_identity_http import (
    NOW,
    ROOT_LOGIN,
    ROOT_PASSWORD,
    AdminTestContext,
    _login,
    _seed_approvable_candidate,
)
from tests.application.test_admin_identity_http import admin_context as admin_context
from travel_agent.domain.admin import AdminAuditEvent
from travel_agent.infrastructure.database.admin_identity import (
    AdminAuditEventRow,
    SqlAlchemyAdminAuditRepository,
)
from travel_agent.infrastructure.database.place_catalog import (
    PlaceRelationRow,
    PlaceRevisionRow,
    PlaceRow,
)


@pytest.mark.parametrize("has_relation", [False, True])
def test_relation_audit_failure_rolls_back_then_same_intent_can_retry(
    admin_context: AdminTestContext, monkeypatch: pytest.MonkeyPatch, has_relation: bool
) -> None:
    context = admin_context
    revision_id = "revision-relation-boundary"
    _seed_approvable_candidate(context, revision_id)
    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)
    if has_relation:
        with context.sessions() as session:
            session.add(
                PlaceRow(
                    place_id="place-2",
                    city_id="hangzhou",
                    status="active",
                    created_at=NOW.isoformat(),
                    updated_at=NOW.isoformat(),
                )
            )
            session.add(
                PlaceRelationRow(
                    relation_id="relation-boundary",
                    from_place_id="place-1",
                    to_place_id="place-2",
                    relation_type="overlaps",
                    source_record_id=f"source-{revision_id}",
                    review_status="human_verified",
                    resolution_status="pending",
                    decision_note=None,
                    active=True,
                    created_at=NOW.isoformat(),
                    reviewed_at=NOW.isoformat(),
                )
            )
            session.commit()
    root = f"/api/v1/admin/place-revisions/{revision_id}/relations"
    payload = {
        "expected_revision_version": 1,
        "operation_intent_id": "relation-boundary-retry",
        "reason_code": "RELATION_CONFIRMED",
    }
    if has_relation:
        url = f"{root}/relation-boundary/resolve"
        payload.update(resolution_status="resolved", decision_note="按来源核实重叠关系")
    else:
        url = f"{root}/confirm-none"
        payload.update(expected_revision_number=1)

    def state() -> list[list[dict[str, object]]]:
        with context.sessions() as session:
            return [
                [
                    dict(row)
                    for row in session.execute(
                        select(model.__table__).order_by(*model.__table__.primary_key.columns)
                    ).mappings()
                ]
                for model in (PlaceRevisionRow, PlaceRelationRow, AdminAuditEventRow)
            ]

    before = state()
    add = SqlAlchemyAdminAuditRepository.add

    def fail(repository: SqlAlchemyAdminAuditRepository, event: AdminAuditEvent) -> None:
        add(repository, event)
        raise RuntimeError("simulated relation audit failure")

    with monkeypatch.context() as patch:
        patch.setattr(SqlAlchemyAdminAuditRepository, "add", fail)
        with pytest.raises(RuntimeError, match="simulated relation audit failure"):
            context.client.post(url, headers=headers, json=payload)
    assert state() == before

    response = context.client.post(url, headers=headers, json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["revision_version"] == 2
    if has_relation:
        with context.sessions() as session:
            relation = session.get(PlaceRelationRow, "relation-boundary")
            assert relation is not None
            assert relation.resolution_status == "resolved"
            assert relation.review_status == "pending"
            assert relation.reviewed_at is None
    else:
        assert response.json()["relation_review_status"] == "no_relations"
        committed = state()
        replay = context.client.post(url, headers=headers, json=payload)
        assert replay.status_code == 200
        assert replay.json() == response.json()
        assert state() == committed
