"""H3/S7-1: time evidence writes keep evidence and audit atomic."""

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
    PlaceClosureRow,
    PlaceDateExceptionRow,
    PlaceRevisionRow,
    PlaceTimeRuleRow,
)


@pytest.mark.parametrize(
    ("kind", "operation"),
    [
        (kind, op)
        for kind in ("time_rule", "closure", "date_exception")
        for op in ("create", "update", "retire")
    ]
    + [("time_rule", "delete"), ("holiday", "generate")],
)
def test_time_write_rolls_back_and_retries_without_duplicate_audit(
    admin_context: AdminTestContext,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    operation: str,
) -> None:
    context = admin_context
    revision_id = "revision-time-boundary"
    _seed_approvable_candidate(context, revision_id)
    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)
    root = f"/api/v1/admin/place-revisions/{revision_id}"
    collections = {
        "time_rule": "time-rules",
        "closure": "closures",
        "date_exception": "date-exceptions",
        "holiday": "holiday-exceptions",
    }
    fields = {
        "time_rule": {
            "rule_kind": "fixed_session",
            "weekdays": [1, 2, 3, 4, 5, 6, 7],
            "start_minute": 1080,
            "end_minute": 1140,
            "last_entry_minute": 1070,
        },
        "closure": {"weekday": 1},
        "date_exception": {"service_date": "2026-09-12", "exception_kind": "closed"},
        "holiday": {
            "calendar_id": "cn-mainland-2026",
            "open_start_minute": 540,
            "open_end_minute": 1020,
            "open_last_entry_minute": 990,
            "shift_closure": True,
        },
    }
    source = {"source_record_id": f"source-{revision_id}"}
    # Build existing evidence through public endpoints before exercising update/retirement.
    seed_kind = "closure" if kind == "holiday" else kind
    if kind == "holiday" or (operation in {"update", "retire"} and kind != "time_rule"):
        seeded = context.client.post(
            f"{root}/{collections[seed_kind]}",
            headers=headers,
            json={
                **source,
                **fields[seed_kind],
                "expected_revision_version": 1,
                "operation_intent_id": "time-boundary-seed",
                "reason_code": "EVIDENCE_UPDATED",
            },
        )
        assert seeded.status_code == 200, seeded.text
    evidence = context.client.get(f"{root}/evidence", headers=headers).json()
    url = f"{root}/{collections[kind]}"
    method = {
        "create": "POST",
        "generate": "POST",
        "update": "PATCH",
        "retire": "DELETE",
        "delete": "POST",
    }[operation]
    if operation in {"update", "retire", "delete"}:
        collection = collections[kind].replace("-", "_")
        url += "/" + evidence[collection][0][f"{kind}_id"]
        if operation == "delete":
            url += "/deletions"
    with context.sessions() as session:
        revision = session.get(PlaceRevisionRow, revision_id)
        assert revision is not None
        version = revision.revision_version
        revision.review_flags = ["TIME_RULE_UNVERIFIED"]
        session.commit()
    payload = {
        "expected_revision_version": version,
        "operation_intent_id": "time-boundary-retry",
        "reason_code": "EVIDENCE_UPDATED",
    }
    if operation not in {"retire", "delete"}:
        payload.update(source)
        payload.update(fields[kind])

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
                    PlaceTimeRuleRow,
                    PlaceClosureRow,
                    PlaceDateExceptionRow,
                    AdminAuditEventRow,
                )
            ]

    before = state()
    add = SqlAlchemyAdminAuditRepository.add

    def fail(repository: SqlAlchemyAdminAuditRepository, event: AdminAuditEvent) -> None:
        add(repository, event)
        raise RuntimeError("simulated time audit failure")

    with monkeypatch.context() as patch:
        patch.setattr(SqlAlchemyAdminAuditRepository, "add", fail)
        with pytest.raises(RuntimeError, match="simulated time audit failure"):
            context.client.request(method, url, headers=headers, json=payload)
    assert state() == before
    response = context.client.request(method, url, headers=headers, json=payload)
    assert response.status_code == 200, response.text
    increment = 9 if kind == "holiday" else 1
    assert response.json()["revision_version"] == version + increment
    committed = state()
    replay = context.client.request(method, url, headers=headers, json=payload)
    assert replay.status_code == 200
    assert replay.json() == response.json()
    assert state() == committed
    conflict = context.client.request(
        method, url, headers=headers, json={**payload, "reason_code": "CHANGED_REASON"}
    )
    assert conflict.status_code == 409
    assert state() == committed
