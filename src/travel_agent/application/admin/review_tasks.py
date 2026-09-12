"""Application use cases for candidate place-revision review."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from travel_agent.application.common.clock import Clock
from travel_agent.application.common.errors import ResourceNotFoundError
from travel_agent.application.planning.ports import IdGenerator
from travel_agent.domain.admin import AdminActor, AdminAuditEvent, AdminPrincipal
from travel_agent.domain.place_catalog import (
    PlaceReviewDecision,
    PlaceReviewTask,
)

from .audit_events import (
    review_flow_role,
)
from .errors import (
    ReviewRevisionNotApprovableError,
    ReviewRevisionNotCandidateError,
    ReviewTaskConflictError,
    ReviewTaskNotFoundError,
)
from .review_ports import ReviewTaskUnitOfWork as ReviewUnitOfWork
from .review_readiness import evaluate_review_readiness
from .review_support import ReviewSupport, _digest, _revision_digest
from .review_time import (
    HolidayCalendarCatalog as HolidayCalendarCatalog,
)

_OPEN_TASK_STATUSES = frozenset({"ready_for_review", "in_review", "changes_requested"})


class ReviewTaskService(ReviewSupport):
    def __init__(
        self, uow_factory: Callable[[], ReviewUnitOfWork], clock: Clock, ids: IdGenerator
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._ids = ids

    def list_tasks(
        self,
        principal: AdminPrincipal,
        *,
        status: str | None,
        limit: int,
        offset: int,
        keyword: str | None = None,
        admin_area: str | None = None,
        place_kind: str | None = None,
    ) -> tuple[PlaceReviewTask, ...]:
        self._require(principal, "place:review:read")
        with self._uow_factory() as uow:
            return uow.reviews.list_tasks(
                status=status,
                keyword=_optional_query(keyword),
                admin_area=_optional_query(admin_area),
                place_kind=_optional_query(place_kind),
                limit=limit,
                offset=offset,
            )

    def count_tasks(
        self,
        principal: AdminPrincipal,
        *,
        status: str | None,
        keyword: str | None = None,
        admin_area: str | None = None,
        place_kind: str | None = None,
    ) -> int:
        self._require(principal, "place:review:read")
        with self._uow_factory() as uow:
            return uow.reviews.count_tasks(
                status=status,
                keyword=_optional_query(keyword),
                admin_area=_optional_query(admin_area),
                place_kind=_optional_query(place_kind),
            )

    def list_decisions(
        self, principal: AdminPrincipal, *, task_id: str
    ) -> tuple[PlaceReviewDecision, ...]:
        self._require(principal, "place:review:read")
        with self._uow_factory() as uow:
            if uow.reviews.get_task(task_id) is None:
                raise ReviewTaskNotFoundError
            return uow.reviews.list_decisions(task_id)

    def get_task(self, principal: AdminPrincipal, *, task_id: str) -> PlaceReviewTask:
        self._require(principal, "place:review:read")
        with self._uow_factory() as uow:
            task = uow.reviews.get_task(task_id)
            if task is None:
                raise ReviewTaskNotFoundError
            return task

    def submit(
        self,
        principal: AdminPrincipal,
        *,
        place_revision_id: str,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceReviewTask:
        self._require(principal, "place:review:request")
        reason_text = self._validate_reason(reason_code, reason_text)
        operation_digest = _digest(
            {
                "place_revision_id": place_revision_id,
                "reason_code": reason_code,
                "reason_text": reason_text,
            }
        )
        now = self._clock.now()
        with self._uow_factory() as uow:
            replay = self._replay(uow, operation_intent_id, operation_digest)
            if replay is not None:
                return self._task_for_replay(uow, replay)
            actor = self._actor(uow, principal)
            revision = uow.reviews.get_revision(place_revision_id)
            if revision is None:
                self._reject(
                    uow,
                    actor,
                    action="PLACE_REVIEW_SUBMITTED",
                    target_type="place_revision",
                    target_id=place_revision_id,
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=operation_digest,
                    error_code="resource_not_found",
                )
                uow.commit()
                raise ResourceNotFoundError
            if revision.lifecycle_status != "candidate":
                self._reject(
                    uow,
                    actor,
                    action="PLACE_REVIEW_SUBMITTED",
                    target_type="place_revision",
                    target_id=place_revision_id,
                    target_revision=str(revision.revision_number),
                    before_digest=_revision_digest(revision),
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=operation_digest,
                    error_code="review_revision_not_candidate",
                )
                uow.commit()
                raise ReviewRevisionNotCandidateError
            existing = uow.reviews.get_open_task_for_revision(place_revision_id)
            if existing is not None:
                if existing.status == "changes_requested":
                    reopened = replace(
                        existing,
                        status="ready_for_review",
                        version=existing.version + 1,
                        updated_at=now,
                    )
                    try:
                        uow.reviews.advance_task(
                            existing,
                            expected_version=existing.version,
                            status="ready_for_review",
                            now=now,
                        )
                    except ValueError as exc:
                        raise ReviewTaskConflictError from exc
                    uow.audits.add(
                        self._event(
                            actor,
                            action="PLACE_REVIEW_SUBMITTED",
                            target_type="review_task",
                            target_id=existing.review_task_id,
                            target_revision=str(revision.revision_number),
                            before_digest=_task_digest(existing),
                            after_digest=_task_digest(reopened),
                            reason_code=reason_code,
                            reason_text=reason_text,
                            request_id=request_id,
                            operation_intent_id=operation_intent_id,
                            operation_digest=operation_digest,
                        )
                    )
                    uow.commit()
                    return reopened
                uow.audits.add(
                    self._event(
                        actor,
                        action="PLACE_REVIEW_SUBMITTED",
                        target_type="review_task",
                        target_id=existing.review_task_id,
                        target_revision=str(revision.revision_number),
                        before_digest=_revision_digest(revision),
                        after_digest=_task_digest(existing),
                        reason_code=reason_code,
                        reason_text=reason_text,
                        request_id=request_id,
                        operation_intent_id=operation_intent_id,
                        operation_digest=operation_digest,
                    )
                )
                uow.commit()
                return existing
            task = PlaceReviewTask(
                self._ids.new_id("review_task"),
                place_revision_id,
                "ready_for_review",
                None,
                1,
                actor.admin_actor_id,
                now,
                now,
            )
            try:
                uow.reviews.add_task(task)
            except ValueError as exc:
                raise ReviewTaskConflictError from exc
            uow.audits.add(
                self._event(
                    actor,
                    action="PLACE_REVIEW_SUBMITTED",
                    target_type="review_task",
                    target_id=task.review_task_id,
                    target_revision=str(revision.revision_number),
                    before_digest=_revision_digest(revision),
                    after_digest=_task_digest(task),
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=operation_digest,
                )
            )
            uow.commit()
            return task

    def decide(
        self,
        principal: AdminPrincipal,
        *,
        task_id: str,
        operation_intent_id: str,
        expected_version: int,
        decision_kind: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceReviewTask:
        self._require(principal, "place:review:decide")
        reason_text = self._validate_reason(reason_code, reason_text)
        operation_digest = _digest(
            {
                "task_id": task_id,
                "expected_version": expected_version,
                "decision_kind": decision_kind,
                "reason_code": reason_code,
                "reason_text": reason_text,
            }
        )
        now = self._clock.now()
        with self._uow_factory() as uow:
            replay = self._replay(uow, operation_intent_id, operation_digest)
            if replay is not None:
                return self._task_for_replay(uow, replay)
            actor = self._actor(uow, principal)
            task = uow.reviews.get_task(task_id)
            if task is None:
                self._reject(
                    uow,
                    actor,
                    action="PLACE_REVIEW_DECIDED",
                    target_type="review_task",
                    target_id=task_id,
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=operation_digest,
                    error_code="review_task_not_found",
                )
                uow.commit()
                raise ReviewTaskNotFoundError
            revision = uow.reviews.get_revision(task.place_revision_id)
            if revision is None:
                raise ResourceNotFoundError
            if task.version != expected_version or task.status not in _OPEN_TASK_STATUSES:
                self._reject(
                    uow,
                    actor,
                    action="PLACE_REVIEW_DECIDED",
                    target_type="review_task",
                    target_id=task_id,
                    target_revision=str(revision.revision_number),
                    before_digest=_task_digest(task),
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=operation_digest,
                    error_code="review_task_conflict",
                )
                uow.commit()
                raise ReviewTaskConflictError
            next_status = {
                "approve": "approved",
                "request_changes": "changes_requested",
                "cancel": "closed",
            }.get(decision_kind)
            if next_status is None:
                raise ValueError("review decision kind is invalid")
            if decision_kind == "approve" and revision.lifecycle_status != "candidate":
                self._reject(
                    uow,
                    actor,
                    action="PLACE_REVIEW_DECIDED",
                    target_type="review_task",
                    target_id=task_id,
                    target_revision=str(revision.revision_number),
                    before_digest=_revision_digest(revision),
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=operation_digest,
                    error_code="review_revision_not_approvable",
                )
                uow.commit()
                raise ReviewRevisionNotApprovableError(not_candidate=True)
            if decision_kind == "approve":
                evidence = uow.catalog.load_revision_evidence(task.place_revision_id)
                readiness = (
                    evaluate_review_readiness(evidence, task) if evidence is not None else None
                )
                if readiness is None or readiness["verified_checks"] != readiness["total_checks"]:
                    missing = readiness["missing_checks"] if readiness is not None else ()
                    pending = readiness["pending_review_checks"] if readiness is not None else ()
                    self._reject(
                        uow,
                        actor,
                        action="PLACE_REVIEW_DECIDED",
                        target_type="review_task",
                        target_id=task_id,
                        target_revision=str(revision.revision_number),
                        before_digest=_revision_digest(revision),
                        reason_code=reason_code,
                        reason_text=reason_text,
                        request_id=request_id,
                        operation_intent_id=operation_intent_id,
                        operation_digest=operation_digest,
                        error_code="review_revision_not_approvable",
                    )
                    uow.commit()
                    raise ReviewRevisionNotApprovableError(
                        missing_checks=tuple(str(item) for item in missing),
                        pending_review_checks=tuple(str(item) for item in pending),
                    )
            uow.reviews.add_decision(
                PlaceReviewDecision(
                    self._ids.new_id("review_decision"),
                    task.review_task_id,
                    task.place_revision_id,
                    actor.admin_actor_id,
                    _reviewer_role(principal.role_keys),
                    decision_kind,
                    reason_code,
                    reason_text,
                    now,
                )
            )
            if decision_kind == "approve":
                try:
                    uow.reviews.approve_revision(task.place_revision_id, reviewed_at=now)
                except ValueError as exc:
                    raise ReviewRevisionNotApprovableError(not_candidate=True) from exc
            try:
                uow.reviews.advance_task(
                    task, expected_version=expected_version, status=next_status, now=now
                )
            except ValueError as exc:
                raise ReviewTaskConflictError from exc
            updated = PlaceReviewTask(
                task.review_task_id,
                task.place_revision_id,
                next_status,
                task.assigned_reviewer_id,
                expected_version + 1,
                task.created_by,
                task.created_at,
                now,
            )
            uow.audits.add(
                self._event(
                    actor,
                    action="PLACE_REVIEW_DECIDED",
                    target_type="review_task",
                    target_id=task_id,
                    target_revision=str(revision.revision_number),
                    before_digest=_task_digest(task),
                    after_digest=_task_digest(updated),
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=operation_digest,
                )
            )
            uow.commit()
            return updated

    def decide_batch(
        self, principal: AdminPrincipal, *, items: tuple[dict[str, object], ...], request_id: str
    ) -> dict[str, object]:
        self._require(principal, "place:review:decide")
        if not items or len(items) > 100:
            raise ValueError("batch must contain 1 to 100 decisions")
        succeeded: list[PlaceReviewTask] = []
        failed: list[dict[str, object]] = []
        for item in items:
            try:
                task = self.decide(
                    principal,
                    task_id=str(item["task_id"]),
                    operation_intent_id=str(item["operation_intent_id"]),
                    expected_version=int(item["expected_version"]),
                    decision_kind=str(item["decision_kind"]),
                    reason_code=str(item["reason_code"]),
                    reason_text=item.get("reason_text")
                    if isinstance(item.get("reason_text"), str)
                    else None,
                    request_id=request_id,
                )
                succeeded.append(task)
            except Exception as exc:
                failed.append(
                    {
                        "task_id": item.get("task_id"),
                        "error_code": getattr(exc, "code", "batch_item_failed"),
                        "message": str(exc),
                    }
                )
        return {"succeeded": tuple(succeeded), "failed": tuple(failed), "total": len(items)}

    @staticmethod
    def _task_for_replay(uow: ReviewUnitOfWork, event: AdminAuditEvent) -> PlaceReviewTask:
        task_id = event.target_id if event.target_type == "review_task" else None
        if task_id is None:
            task = uow.reviews.get_open_task_for_revision(event.target_id)
        else:
            task = uow.reviews.get_task(task_id)
        if task is None:
            raise ReviewTaskNotFoundError
        return task

    def _reject(
        self,
        uow: ReviewUnitOfWork,
        actor: AdminActor,
        *,
        action: str,
        target_type: str,
        target_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
        operation_intent_id: str,
        operation_digest: str,
        error_code: str,
        target_revision: str | None = None,
        before_digest: str | None = None,
    ) -> None:
        uow.audits.add(
            self._event(
                actor,
                action=action,
                target_type=target_type,
                target_id=target_id,
                target_revision=target_revision,
                before_digest=before_digest,
                after_digest=None,
                reason_code=reason_code,
                reason_text=reason_text,
                request_id=request_id,
                operation_intent_id=operation_intent_id,
                operation_digest=operation_digest,
                result="rejected",
                error_code=error_code,
            )
        )


def _reviewer_role(role_keys: tuple[str, ...]) -> str:
    return review_flow_role(role_keys)


def _optional_query(value: str | None) -> str | None:
    normalized = value.strip() if value else ""
    return normalized or None


def _task_digest(task: PlaceReviewTask) -> str:
    return _digest(
        {
            "review_task_id": task.review_task_id,
            "place_revision_id": task.place_revision_id,
            "status": task.status,
            "version": task.version,
        }
    )
