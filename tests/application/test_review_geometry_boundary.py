"""H3/S7-1: geometry/access-point writes keep evidence and audit atomic."""

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
from travel_agent.domain.admin import AdminAuditEvent
from travel_agent.infrastructure.database.admin_identity import (
    AdminAuditEventRow,
    SqlAlchemyAdminAuditRepository,
)
from travel_agent.infrastructure.database.place_catalog import (
    PlaceAccessPointRow,
    PlaceGeometryRow,
    PlaceRevisionRow,
)


@pytest.mark.parametrize("kind", ["geometry", "access_point"])
@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE"])
def test_geometry_write_rolls_back_and_retries_without_duplicate_audit(
    admin_context: AdminTestContext, monkeypatch: pytest.MonkeyPatch, kind: str, method: str
) -> None:
    context = admin_context
    revision_id = "revision-geometry-boundary"
    _seed_approvable_candidate(context, revision_id)
    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)
    root = f"/api/v1/admin/place-revisions/{revision_id}"
    evidence = context.client.get(f"{root}/evidence", headers=headers).json()
    collection = "geometries" if kind == "geometry" else "access_points"
    url = f"{root}/{collection.replace('_', '-')}"
    if method != "POST":
        url += "/" + evidence[collection][0][f"{kind}_id"]
    with context.sessions() as session:
        revision = session.get(PlaceRevisionRow, revision_id)
        assert revision is not None
        version = revision.revision_version
        revision.review_flags = ["GEOMETRY_UNVERIFIED", "ACCESS_POINT_UNVERIFIED"]
        session.commit()
    payload = {
        "expected_revision_version": version,
        "operation_intent_id": "geometry-boundary-retry",
        "reason_code": "EVIDENCE_UPDATED",
    }
    if method != "DELETE":
        payload["source_record_id"] = f"source-{revision_id}"
        if kind == "geometry":
            payload.update(
                geometry_kind="point", geometry={"type": "Point", "coordinates": [120.15, 30.25]}
            )
        else:
            payload.update(
                access_point_kind="visitor_entrance", name="新入口", lat="30.25", lng="120.15"
            )

    def state() -> list[list[dict[str, object]]]:
        with context.sessions() as session:
            return [
                [
                    dict(row)
                    for row in session.execute(
                        select(model.__table__).order_by(*model.__table__.primary_key.columns)
                    ).mappings()
                ]
                for model in (
                    PlaceRevisionRow,
                    PlaceGeometryRow,
                    PlaceAccessPointRow,
                    AdminAuditEventRow,
                )
            ]

    before = state()
    add = SqlAlchemyAdminAuditRepository.add

    def fail(repository: SqlAlchemyAdminAuditRepository, event: AdminAuditEvent) -> None:
        add(repository, event)
        raise RuntimeError("simulated evidence audit failure")

    with monkeypatch.context() as patch:
        patch.setattr(SqlAlchemyAdminAuditRepository, "add", fail)
        with pytest.raises(RuntimeError, match="simulated evidence audit failure"):
            context.client.request(method, url, headers=headers, json=payload)
    assert state() == before

    response = context.client.request(method, url, headers=headers, json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["revision_version"] == version + 1
    committed = state()
    replay = context.client.request(method, url, headers=headers, json=payload)
    assert replay.status_code == 200
    assert replay.json() == response.json()
    assert state() == committed
