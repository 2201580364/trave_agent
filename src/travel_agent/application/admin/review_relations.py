"""Relation resolution use cases (H3/S7-1)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from travel_agent.application.common.clock import Clock
from travel_agent.application.common.errors import ResourceNotFoundError
from travel_agent.application.planning.ports import IdGenerator
from travel_agent.domain.admin import AdminPrincipal
from travel_agent.domain.place_catalog import (
    PlaceRevision,
)

from .errors import (
    PlaceRevisionVersionConflictError,
    ReviewRevisionNotCandidateError,
    ReviewTaskConflictError,
)
from .review_evidence import _evidence_digest
from .review_ports import RelationReviewUnitOfWork
from .review_support import ReviewSupport, _digest, _revision_digest


class ReviewRelationService(ReviewSupport):
    def __init__(
        self, uow_factory: Callable[[], RelationReviewUnitOfWork], clock: Clock, ids: IdGenerator
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._ids = ids

    def resolve_relation(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        relation_id: str,
        expected_revision_version: int,
        resolution_status: str,
        decision_note: str | None,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        self._require(principal, "place:candidate:write")
        if resolution_status not in {"resolved", "not_required", "pending"}:
            raise ValueError("invalid relation resolution status")
        if resolution_status == "resolved" and not decision_note:
            raise ValueError("resolved relation requires decision note")
        reason_text = self._validate_reason(reason_code, reason_text)
        digest = _digest(
            {
                "revision_id": revision_id,
                "relation_id": relation_id,
                "expected_revision_version": expected_revision_version,
                "resolution_status": resolution_status,
                "decision_note": decision_note,
                "reason_code": reason_code,
                "reason_text": reason_text,
            }
        )
        with self._uow_factory() as uow:
            existing = self._replay(uow, operation_intent_id, digest)
            if existing is not None:
                # The audit target is the relation ID; replay returns the
                # revision being edited, which is the operation's resource.
                revision = uow.reviews.get_revision(revision_id)
                if revision is None:
                    raise ResourceNotFoundError
                return revision
            actor = self._actor(uow, principal)
            revision = uow.reviews.get_revision(revision_id)
            evidence = uow.catalog.load_revision_evidence(revision_id)
            if revision is None or evidence is None:
                raise ResourceNotFoundError
            if revision.lifecycle_status != "candidate":
                raise ReviewRevisionNotCandidateError
            relation = next(
                (
                    item
                    for item in evidence.relations
                    if item.relation_id == relation_id and item.active
                ),
                None,
            )
            if relation is None or revision.place_id not in {
                relation.from_place_id,
                relation.to_place_id,
            }:
                raise ResourceNotFoundError
            updated_relation = replace(
                relation,
                resolution_status=resolution_status,
                decision_note=decision_note,
                # A裁决 changes the relation fact but does not
                # itself constitute reviewer verification.
                review_status="candidate",
                reviewed_at=None,
            )
            updated = uow.catalog.update_relation(
                updated_relation,
                revision_id=revision_id,
                expected_revision_version=expected_revision_version,
            )
            uow.audits.add(
                self._event(
                    actor,
                    action="PLACE_RELATION_RESOLUTION_UPDATED",
                    target_type="place_relation",
                    target_id=relation_id,
                    target_revision=str(updated.revision_number),
                    before_digest=_evidence_digest(relation),
                    after_digest=_evidence_digest(updated_relation),
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=digest,
                )
            )
            uow.commit()
            return updated

    def confirm_no_relations(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        expected_revision_number: int,
        expected_revision_version: int,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        """Record that this revision was checked and has no relation evidence to裁决."""
        self._require(principal, "place:candidate:write")
        reason_text = self._validate_reason(reason_code, reason_text)
        digest = _digest(
            {
                "revision_id": revision_id,
                "expected_revision_number": expected_revision_number,
                "expected_revision_version": expected_revision_version,
                "reason_code": reason_code,
                "reason_text": reason_text,
            }
        )
        with self._uow_factory() as uow:
            existing = self._replay(uow, operation_intent_id, digest)
            if existing is not None:
                revision = uow.reviews.get_revision(existing.target_id)
                if revision is None:
                    raise ResourceNotFoundError
                return revision
            actor = self._actor(uow, principal)
            current = uow.reviews.get_revision(revision_id)
            evidence = uow.catalog.load_revision_evidence(revision_id)
            if current is None or evidence is None:
                raise ResourceNotFoundError
            if current.lifecycle_status != "candidate":
                raise ReviewRevisionNotCandidateError
            if current.revision_number != expected_revision_number:
                raise ReviewTaskConflictError
            if current.revision_version != expected_revision_version:
                raise PlaceRevisionVersionConflictError
            if any(item.active for item in evidence.relations):
                raise ValueError("当前存在关系记录，请逐条完成关系裁决")
            updated = replace(
                current,
                relation_review_status="no_relations",
                solver_eligible=False,
                conflicts_resolved=False,
                reviewed_at=None,
                published_at=None,
                revision_version=current.revision_version + 1,
            )
            uow.reviews.update_revision(
                updated,
                expected_revision_number=expected_revision_number,
                expected_revision_version=expected_revision_version,
            )
            uow.audits.add(
                self._event(
                    actor,
                    action="PLACE_RELATION_REVIEW_CONFIRMED_NONE",
                    target_type="place_revision",
                    target_id=revision_id,
                    target_revision=str(updated.revision_number),
                    before_digest=_revision_digest(current),
                    after_digest=_revision_digest(updated),
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=digest,
                )
            )
            uow.commit()
            return updated
