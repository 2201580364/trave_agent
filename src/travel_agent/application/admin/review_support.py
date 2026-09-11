"""Shared permission, replay and audit support (H3/S7-1)."""

from __future__ import annotations

from travel_agent.application.common.clock import Clock
from travel_agent.application.common.errors import ResourceNotFoundError
from travel_agent.application.planning.ports import IdGenerator
from travel_agent.domain.admin import AdminActor, AdminAuditEvent, AdminPrincipal
from travel_agent.domain.place_catalog import (
    PlaceRevision,
)

from .audit_events import (
    build_audit_event,
    canonical_digest,
    review_flow_role,
    validate_audit_reason,
)
from .errors import (
    AdminAuthenticationError,
    AdminOperationIntentConflictError,
    AdminPermissionDeniedError,
    PublicationGateRejectedError,
    ReviewRevisionNotApprovableError,
    ReviewRevisionNotCandidateError,
    ReviewTaskConflictError,
    ReviewTaskNotFoundError,
)
from .review_ports import AuditContext


class ReviewSupport:
    _clock: Clock
    _ids: IdGenerator

    @staticmethod
    def _require(principal: AdminPrincipal, permission: str) -> None:
        if not principal.has_permission(permission):
            raise AdminPermissionDeniedError(permission)

    @staticmethod
    def _actor(uow: AuditContext, principal: AdminPrincipal) -> AdminActor:
        actor = uow.actors.get(principal.admin_actor_id)
        if actor is None:
            raise AdminAuthenticationError
        return actor

    @staticmethod
    def _replay(
        uow: AuditContext, operation_intent_id: str, operation_digest: str
    ) -> AdminAuditEvent | None:
        existing = uow.audits.get_by_operation_intent(operation_intent_id)
        if existing is None:
            return None
        if existing.operation_digest != operation_digest:
            raise AdminOperationIntentConflictError
        if existing.result == "rejected":
            _raise_review_error(existing.error_code)
        return existing

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
        # Thin delegate to the shared constructor (audit-logging.md §1.2);
        # actor_role follows the review-flow ordering (§6).
        return build_audit_event(
            event_id=self._ids.new_id("admin_audit"),
            actor=actor,
            actor_role=review_flow_role(actor.role_keys),
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_revision=target_revision,
            before_digest=before_digest,
            after_digest=after_digest,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
            operation_intent_id=operation_intent_id,
            operation_digest=operation_digest,
            result=result,
            error_code=error_code,
            occurred_at=self._clock.now(),
        )

    @staticmethod
    def _validate_reason(reason_code: str, reason_text: str | None) -> str | None:
        # Single authoritative validation lives in audit_events.py.
        return validate_audit_reason(reason_code, reason_text)


def _raise_review_error(error_code: str | None) -> None:
    if error_code == "review_task_not_found":
        raise ReviewTaskNotFoundError
    if error_code == "review_task_conflict":
        raise ReviewTaskConflictError
    if error_code == "review_revision_not_approvable":
        raise ReviewRevisionNotApprovableError(not_candidate=True)
    if error_code == "review_revision_not_candidate":
        raise ReviewRevisionNotCandidateError
    if error_code == "publication_gate_rejected":
        raise PublicationGateRejectedError(())
    if error_code == "resource_not_found":
        raise ResourceNotFoundError
    raise ValueError("review operation was previously rejected")


def _revision_digest(revision: PlaceRevision) -> str:
    return _digest(
        {
            "place_revision_id": revision.place_revision_id,
            "revision_number": revision.revision_number,
            "revision_version": revision.revision_version,
            "relation_review_status": revision.relation_review_status,
            "lifecycle_status": revision.lifecycle_status,
            "canonical_name": revision.canonical_name,
        }
    )


def _digest(value: object) -> str:
    # Single authoritative implementation lives in audit_events.py.
    return canonical_digest(value)
