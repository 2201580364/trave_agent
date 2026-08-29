"""Application use cases for candidate place-revision review."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self

from travel_agent.application.common.clock import Clock
from travel_agent.application.common.errors import ResourceNotFoundError
from travel_agent.application.planning.ports import IdGenerator
from travel_agent.domain.admin import AdminActor, AdminAuditEvent, AdminPrincipal
from travel_agent.domain.place_catalog import PlaceReviewDecision, PlaceReviewTask, PlaceRevision

from .errors import (
    AdminAuthenticationError,
    AdminOperationIntentConflictError,
    AdminPermissionDeniedError,
    ReviewRevisionNotApprovableError,
    ReviewRevisionNotCandidateError,
    ReviewTaskConflictError,
    ReviewTaskNotFoundError,
)

_REASON_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_SENSITIVE_REASON_PATTERN = re.compile(
    r"(?i)(api[ _-]?key|access[ _-]?token|password|passwd|cookie|secret|"
    r"缁変線鎸渱鐎靛棛鐖渱娴犮倗澧?)"
)
_OPEN_TASK_STATUSES = frozenset({"ready_for_review", "in_review", "changes_requested"})


class ReviewRepository(Protocol):
    def get_task(self, task_id: str) -> PlaceReviewTask | None: ...

    def get_open_task_for_revision(self, revision_id: str) -> PlaceReviewTask | None: ...

    def list_tasks(
        self, *, status: str | None, limit: int, offset: int
    ) -> tuple[PlaceReviewTask, ...]: ...

    def list_decisions(self, task_id: str) -> tuple[PlaceReviewDecision, ...]: ...

    def get_revision(self, revision_id: str) -> PlaceRevision | None: ...

    def add_task(self, task: PlaceReviewTask) -> None: ...

    def add_decision(self, decision: PlaceReviewDecision) -> None: ...

    def advance_task(
        self, task: PlaceReviewTask, *, expected_version: int, status: str, now: datetime
    ) -> None: ...

    def approve_revision(self, revision_id: str, *, reviewed_at: datetime) -> None: ...


class AuditRepository(Protocol):
    def add(self, event: AdminAuditEvent) -> None: ...

    def get_by_operation_intent(self, operation_intent_id: str) -> AdminAuditEvent | None: ...


class ActorRepository(Protocol):
    def get(self, actor_id: str) -> AdminActor | None: ...


class ReviewUnitOfWork(Protocol):
    reviews: ReviewRepository
    audits: AuditRepository
    actors: ActorRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...

    def commit(self) -> None: ...


class PlaceReviewWorkflowService:
    def __init__(
        self, uow_factory: Callable[[], ReviewUnitOfWork], clock: Clock, ids: IdGenerator
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._ids = ids

    def list_tasks(
        self, principal: AdminPrincipal, *, status: str | None, limit: int, offset: int
    ) -> tuple[PlaceReviewTask, ...]:
        self._require(principal, "place:review:read")
        with self._uow_factory() as uow:
            return uow.reviews.list_tasks(status=status, limit=limit, offset=offset)

    def list_decisions(
        self, principal: AdminPrincipal, *, task_id: str
    ) -> tuple[PlaceReviewDecision, ...]:
        self._require(principal, "place:review:read")
        with self._uow_factory() as uow:
            if uow.reviews.get_task(task_id) is None:
                raise ReviewTaskNotFoundError
            return uow.reviews.list_decisions(task_id)

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
                raise ReviewRevisionNotApprovableError
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
                    raise ReviewRevisionNotApprovableError from exc
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

    @staticmethod
    def _require(principal: AdminPrincipal, permission: str) -> None:
        if not principal.has_permission(permission):
            raise AdminPermissionDeniedError(permission)

    @staticmethod
    def _actor(uow: ReviewUnitOfWork, principal: AdminPrincipal) -> AdminActor:
        actor = uow.actors.get(principal.admin_actor_id)
        if actor is None:
            raise AdminAuthenticationError
        return actor

    @staticmethod
    def _replay(
        uow: ReviewUnitOfWork, operation_intent_id: str, operation_digest: str
    ) -> AdminAuditEvent | None:
        existing = uow.audits.get_by_operation_intent(operation_intent_id)
        if existing is None:
            return None
        if existing.operation_digest != operation_digest:
            raise AdminOperationIntentConflictError
        if existing.result == "rejected":
            _raise_review_error(existing.error_code)
        return existing

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

    def _event(
        self,
        actor: AdminActor,
        *,
        action: str,
        target_type: str,
        target_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
        operation_intent_id: str | None,
        operation_digest: str | None,
        target_revision: str | None = None,
        before_digest: str | None = None,
        after_digest: str | None = None,
        result: str = "succeeded",
        error_code: str | None = None,
    ) -> AdminAuditEvent:
        return AdminAuditEvent(
            self._ids.new_id("admin_audit"),
            actor.admin_actor_id,
            _reviewer_role(actor.role_keys),
            action,
            target_type,
            target_id,
            target_revision,
            before_digest,
            after_digest,
            reason_code,
            reason_text,
            request_id,
            operation_intent_id,
            operation_digest,
            result,
            error_code,
            self._clock.now(),
        )

    @staticmethod
    def _validate_reason(reason_code: str, reason_text: str | None) -> str | None:
        if _REASON_CODE_PATTERN.fullmatch(reason_code) is None:
            raise ValueError("reason_code must be a stable uppercase code")
        if reason_text and _SENSITIVE_REASON_PATTERN.search(reason_text):
            raise ValueError("reason_text must not contain credentials")
        normalized = reason_text.strip() if reason_text else None
        if normalized and any(ord(char) < 32 for char in normalized):
            raise ValueError("reason_text must be printable")
        if normalized and len(normalized) > 500:
            raise ValueError("reason_text is too long")
        return normalized


def _raise_review_error(error_code: str | None) -> None:
    if error_code == "review_task_not_found":
        raise ReviewTaskNotFoundError
    if error_code == "review_task_conflict":
        raise ReviewTaskConflictError
    if error_code == "review_revision_not_approvable":
        raise ReviewRevisionNotApprovableError
    if error_code == "review_revision_not_candidate":
        raise ReviewRevisionNotCandidateError
    if error_code == "resource_not_found":
        raise ResourceNotFoundError
    raise ValueError("review operation was previously rejected")


def _reviewer_role(role_keys: tuple[str, ...]) -> str:
    for role in ("data_reviewer", "admin_security", "data_editor", "data_publisher"):
        if role in role_keys:
            return role
    return "authenticated_admin"


def _task_digest(task: PlaceReviewTask) -> str:
    return _digest(
        {
            "review_task_id": task.review_task_id,
            "place_revision_id": task.place_revision_id,
            "status": task.status,
            "version": task.version,
        }
    )


def _revision_digest(revision: PlaceRevision) -> str:
    return _digest(
        {
            "place_revision_id": revision.place_revision_id,
            "revision_number": revision.revision_number,
            "lifecycle_status": revision.lifecycle_status,
            "canonical_name": revision.canonical_name,
        }
    )


def _digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
