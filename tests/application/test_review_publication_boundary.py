"""H3/S7-1: publication writes keep evidence and audit atomic."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from tests.application.test_admin_identity_http import (
    ROOT_LOGIN,
    ROOT_PASSWORD,
    AdminTestContext,
    _login,
    _seed_human_verified_revision_with_evidence,
)
from tests.application.test_admin_identity_http import admin_context as admin_context
from travel_agent.infrastructure.database.admin_identity import (
    AdminAuditEventRow,
    SqlAlchemyAdminAuditRepository,
)
from travel_agent.infrastructure.database.place_catalog import (
    PlaceRevisionRow,
    PublicationBatchItemRow,
    PublicationBatchRow,
    ResearchSnapshotRow,
    SolverPlaceProjectionRow,
)


@pytest.mark.parametrize("operation", ["prepare", "publish", "preview", "execute"])
def test_publication_audit_failure_rolls_back_and_retries(
    admin_context: AdminTestContext, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    context = admin_context
    _seed_human_verified_revision_with_evidence(context)
    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)
    root = "/api/v1/admin/place-revisions/revision-projection"
    prepare_url = root + "/projection-preparations"
    prepare = {
        "data_snapshot_version": "publication-boundary",
        "operation_intent_id": "prepare-seed",
        "reason_code": "PROJECTION_PREPARED",
    }
    preview_url = "/api/v1/admin/publication-batches/previews"
    preview = {
        "city_id": "hangzhou",
        "place_revision_ids": ["revision-projection"],
        "operation_intent_id": "preview-seed",
        "reason_code": "PUBLICATION_PREVIEW",
    }
    if operation != "prepare":
        result = context.client.post(prepare_url, headers=headers, json=prepare)
        assert result.status_code == 200, result.text
    if operation == "execute":
        result = context.client.post(preview_url, headers=headers, json=preview)
        assert result.status_code == 201, result.text
        url = f"/api/v1/admin/publication-batches/{result.json()['batch_id']}/execute"
    else:
        url = {"prepare": prepare_url, "publish": root + "/publications", "preview": preview_url}[
            operation
        ]
    payload = dict(prepare if operation == "prepare" else preview if operation == "preview" else {})
    payload.update(operation_intent_id="publication-retry", reason_code="PUBLICATION_TEST")

    def state():
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
                    SolverPlaceProjectionRow,
                    PublicationBatchRow,
                    PublicationBatchItemRow,
                    ResearchSnapshotRow,
                    AdminAuditEventRow,
                )
            ]

    before = state()
    add = SqlAlchemyAdminAuditRepository.add

    def fail(repository, event):
        add(repository, event)
        raise RuntimeError("simulated publication audit failure")

    with monkeypatch.context() as patch:
        patch.setattr(SqlAlchemyAdminAuditRepository, "add", fail)
        with pytest.raises(RuntimeError, match="simulated publication audit failure"):
            context.client.post(url, headers=headers, json=payload)
    assert state() == before
    result = context.client.post(url, headers=headers, json=payload)
    assert result.status_code == (201 if operation == "preview" else 200), result.text
    committed = state()
    replay = context.client.post(url, headers=headers, json=payload)
    assert replay.status_code == result.status_code
    assert state() == committed
    if operation == "execute":
        assert result.json()["snapshot"] is not None
        assert replay.json()["snapshot"] == result.json()["snapshot"]
        assert replay.json()["reused"] is True
    else:
        assert replay.json() == result.json()
