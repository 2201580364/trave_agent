"""H3/S7-1: review task writes keep evidence and audit atomic."""

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
    PlaceRevisionRow,
)
from travel_agent.infrastructure.database.place_review import (
    PlaceReviewDecisionRow,
    PlaceReviewTaskRow,
)


@pytest.mark.parametrize(
    "operation", ["submit", "resubmit", "approve", "request_changes", "cancel"]
)
def test_task_audit_failure_rolls_back_and_allows_idempotent_retry(
    admin_context: AdminTestContext, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    context = admin_context
    revision_id = "revision-task-boundary"
    _seed_approvable_candidate(context, revision_id)
    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)
    submit_url = f"/api/v1/admin/place-revisions/{revision_id}/review-tasks"
    url = submit_url
    payload = {"operation_intent_id": "task-boundary-retry", "reason_code": "FACTS_VERIFIED"}
    expected_status = "ready_for_review"
    expected_version = 1
    if operation != "submit":
        seed = context.client.post(
            submit_url,
            headers=headers,
            json={"operation_intent_id": "task-boundary-seed", "reason_code": "READY_FOR_REVIEW"},
        )
        assert seed.status_code == 201, seed.text
        task = seed.json()
        decision_url = f"/api/v1/admin/review-tasks/{task['review_task_id']}/decisions"
        if operation == "resubmit":
            returned = context.client.post(
                decision_url,
                headers=headers,
                json={
                    "operation_intent_id": "task-boundary-return",
                    "reason_code": "CHANGES_REQUIRED",
                    "expected_version": 1,
                    "decision_kind": "request_changes",
                },
            )
            assert returned.status_code == 200, returned.text
            expected_version = 3
        else:
            url = decision_url
            payload.update(expected_version=1, decision_kind=operation)
            expected_status = {
                "approve": "approved",
                "request_changes": "changes_requested",
                "cancel": "closed",
            }[operation]
            expected_version = 2

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
                    PlaceReviewTaskRow,
                    PlaceReviewDecisionRow,
                    AdminAuditEventRow,
                )
            ]

    before = state()
    add = SqlAlchemyAdminAuditRepository.add

    def fail(repository: SqlAlchemyAdminAuditRepository, event: AdminAuditEvent) -> None:
        add(repository, event)
        raise RuntimeError("simulated task audit failure")

    with monkeypatch.context() as patch:
        patch.setattr(SqlAlchemyAdminAuditRepository, "add", fail)
        with pytest.raises(RuntimeError, match="simulated task audit failure"):
            context.client.post(url, headers=headers, json=payload)
    assert state() == before
    response = context.client.post(url, headers=headers, json=payload)
    assert response.status_code == (201 if url == submit_url else 200), response.text
    assert response.json()["status"] == expected_status
    assert response.json()["version"] == expected_version
    committed = state()
    replay = context.client.post(url, headers=headers, json=payload)
    assert replay.status_code == response.status_code
    assert replay.json() == response.json()
    assert state() == committed
    conflict = context.client.post(
        url, headers=headers, json={**payload, "reason_code": "CHANGED_REASON"}
    )
    assert conflict.status_code == 409
    assert state() == committed


def test_batch_commits_successful_items_and_retries_only_failed_items(
    admin_context: AdminTestContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = admin_context
    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)
    from travel_agent.application.admin.review_tasks import ReviewTaskService

    captured = []
    submit = ReviewTaskService.submit

    def capture(service, principal, **kwargs):
        captured.append((service, principal))
        return submit(service, principal, **kwargs)

    monkeypatch.setattr(ReviewTaskService, "submit", capture)
    items = []
    for index in range(2):
        revision_id = f"revision-batch-boundary-{index}"
        if index == 0:
            _seed_approvable_candidate(context, revision_id)
        else:
            with context.sessions() as session:
                original = session.get(PlaceRevisionRow, "revision-batch-boundary-0")
                assert original is not None
                values = {
                    column.name: getattr(original, column.name)
                    for column in PlaceRevisionRow.__table__.columns
                }
                values.update(place_revision_id=revision_id, revision_number=2)
                session.add(PlaceRevisionRow(**values))
                session.commit()
        submitted = context.client.post(
            f"/api/v1/admin/place-revisions/{revision_id}/review-tasks",
            headers=headers,
            json={"operation_intent_id": f"seed-batch-{index}", "reason_code": "READY_FOR_REVIEW"},
        )
        assert submitted.status_code == 201
        items.append(
            {
                "task_id": submitted.json()["review_task_id"],
                "operation_intent_id": f"batch-boundary-{index}",
                "expected_version": 1,
                "decision_kind": "request_changes",
                "reason_code": "FACTS_VERIFIED",
            }
        )
    add = SqlAlchemyAdminAuditRepository.add

    def fail_first(repository: SqlAlchemyAdminAuditRepository, event: AdminAuditEvent) -> None:
        add(repository, event)
        if event.operation_intent_id == "batch-boundary-0":
            raise RuntimeError("simulated batch item failure")

    service, principal = captured[0]
    with monkeypatch.context() as patch:
        patch.setattr(SqlAlchemyAdminAuditRepository, "add", fail_first)
        response = service.decide_batch(principal, items=tuple(items), request_id="batch-test")
    assert len(response["succeeded"]) == len(response["failed"]) == 1
    assert response["failed"][0]["task_id"] == items[0]["task_id"]
    with context.sessions() as session:
        first = session.get(PlaceReviewTaskRow, items[0]["task_id"])
        second = session.get(PlaceReviewTaskRow, items[1]["task_id"])
        assert first is not None and second is not None
        assert (first.status, first.version) == ("ready_for_review", 1)
        assert (second.status, second.version) == ("changes_requested", 2)
    retried = service.decide_batch(principal, items=tuple(items), request_id="batch-retry")
    assert len(retried["succeeded"]) == 2
    assert retried["failed"] == ()
    with context.sessions() as session:
        decisions = list(session.scalars(select(PlaceReviewDecisionRow)))
        assert len(decisions) == 2
        for item in items:
            audits = list(
                session.scalars(
                    select(AdminAuditEventRow).where(
                        AdminAuditEventRow.operation_intent_id == item["operation_intent_id"]
                    )
                )
            )
            assert len(audits) == 1
