"""Shared evidence mutation transaction (H3/S7-1)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from travel_agent.application.common.errors import ResourceNotFoundError
from travel_agent.domain.admin import AdminPrincipal
from travel_agent.domain.place_catalog import (
    PlaceRevision,
)

from .errors import (
    PlaceRevisionVersionConflictError,
    ReviewRevisionNotCandidateError,
)
from .review_ports import EvidenceReviewUnitOfWork
from .review_support import ReviewSupport, _digest, _revision_digest


class EvidenceMutationSupport[EvidenceUow: EvidenceReviewUnitOfWork](ReviewSupport):
    _uow_factory: Callable[[], EvidenceUow]

    def _mutate_evidence(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        expected_revision_version: int,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
        action: str,
        target_id: str,
        payload: dict[str, object],
        mutate: Callable[[EvidenceUow, PlaceRevision], tuple[PlaceRevision, str]],
    ) -> PlaceRevision:
        self._require(principal, "place:candidate:write")
        reason_text = self._validate_reason(reason_code, reason_text)
        operation_digest = _digest(
            {**payload, "reason_code": reason_code, "reason_text": reason_text}
        )
        with self._uow_factory() as uow:
            existing = self._replay(uow, operation_intent_id, operation_digest)
            if existing is not None:
                revision = uow.reviews.get_revision(revision_id)
                if revision is None:
                    raise ResourceNotFoundError
                return revision
            actor = self._actor(uow, principal)
            revision = uow.reviews.get_revision(revision_id)
            if revision is None:
                raise ResourceNotFoundError
            if revision.lifecycle_status != "candidate":
                raise ReviewRevisionNotCandidateError
            if revision.revision_version != expected_revision_version:
                raise PlaceRevisionVersionConflictError
            try:
                updated, actual_target_id = mutate(uow, revision)
            except ValueError as exc:
                if "version conflict" in str(exc):
                    raise PlaceRevisionVersionConflictError from exc
                if "not found" in str(exc):
                    raise ResourceNotFoundError from exc
                raise
            flags_to_clear = _evidence_flags_cleared_by_action(action)
            if flags_to_clear:
                cleaned = replace(
                    updated,
                    review_flags=tuple(
                        flag for flag in updated.review_flags if flag not in flags_to_clear
                    ),
                )
                if cleaned != updated:
                    uow.reviews.update_revision(
                        cleaned,
                        expected_revision_number=updated.revision_number,
                        expected_revision_version=updated.revision_version,
                    )
                    updated = cleaned
            uow.audits.add(
                self._event(
                    actor,
                    action=action,
                    target_type=_evidence_target_type(action),
                    target_id=actual_target_id,
                    target_revision=str(updated.revision_number),
                    before_digest=_revision_digest(revision),
                    after_digest=_revision_digest(updated),
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=operation_digest,
                )
            )
            uow.commit()
            return updated


def _evidence_target_type(action: str) -> str:
    for marker, target_type in (
        ("HOLIDAY_EXCEPTIONS", "place_date_exception"),
        ("DATE_EXCEPTION", "place_date_exception"),
        ("ACCESS_POINT", "place_access_point"),
        ("TIME_RULE", "place_time_rule"),
        ("GEOMETRY", "place_geometry"),
        ("CLOSURE", "place_closure"),
    ):
        if marker in action:
            return target_type
    raise ValueError("unknown place evidence action")


def _evidence_flags_cleared_by_action(action: str) -> frozenset[str]:
    if action in {"PLACE_GEOMETRY_CREATED", "PLACE_GEOMETRY_UPDATED"}:
        return frozenset({"GEOMETRY_UNVERIFIED", "PROVIDER_POINT_IS_NOT_PLACE_GEOMETRY"})
    if action in {"PLACE_ACCESS_POINT_CREATED", "PLACE_ACCESS_POINT_UPDATED"}:
        return frozenset({"ACCESS_POINT_UNVERIFIED"})
    if action in {"PLACE_TIME_RULE_CREATED", "PLACE_TIME_RULE_UPDATED"}:
        return frozenset({"TIME_RULES_NOT_COLLECTED"})
    return frozenset()
