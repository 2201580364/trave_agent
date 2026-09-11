"""Governed source evidence use cases (H3/S7-1)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime

from travel_agent.application.common.clock import Clock
from travel_agent.application.common.errors import ResourceNotFoundError
from travel_agent.application.planning.ports import IdGenerator
from travel_agent.domain.admin import AdminPrincipal
from travel_agent.domain.place_catalog import (
    PlaceRevision,
    PlaceSourceRecord,
)

from .errors import (
    PlaceRevisionVersionConflictError,
    ReviewRevisionNotCandidateError,
    ReviewTaskConflictError,
    SourceRecordInUseError,
    SourceRecordValidationError,
)
from .review_ports import SourceReviewUnitOfWork
from .review_support import ReviewSupport, _digest, _revision_digest
from .sources import GovernedSourceCatalog, GovernedSourceChannel, SourceRecordInputError


class ReviewSourceService(ReviewSupport):
    def __init__(
        self,
        uow_factory: Callable[[], SourceReviewUnitOfWork],
        clock: Clock,
        ids: IdGenerator,
        source_catalog: GovernedSourceCatalog,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._ids = ids
        self._source_catalog = source_catalog

    def list_source_conflicts(
        self, principal: AdminPrincipal, *, revision_id: str
    ) -> tuple[dict[str, object], ...]:
        self._require(principal, "place:candidate:read")
        with self._uow_factory() as uow:
            evidence = uow.catalog.load_revision_evidence(revision_id)
            if evidence is None:
                raise ResourceNotFoundError
        groups: dict[str, list[PlaceSourceRecord]] = {}
        for record in evidence.source_records:
            groups.setdefault(record.source_id, []).append(record)
        conflicts = []
        for source_id, records in sorted(groups.items()):
            fingerprints = {record.content_sha256 or record.registry_sha256 for record in records}
            if len(records) > 1 and len(fingerprints) > 1:
                conflicts.append(
                    {
                        "source_id": source_id,
                        "records": tuple(records),
                        "resolved": evidence.revision.conflicts_resolved,
                    }
                )
        return tuple(conflicts)

    def resolve_source_conflicts(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        expected_revision_number: int,
        expected_revision_version: int,
        resolved: bool,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        self._require(principal, "place:candidate:write")
        reason_text = self._validate_reason(reason_code, reason_text)
        digest = _digest(
            {
                "revision_id": revision_id,
                "expected_revision_number": expected_revision_number,
                "expected_revision_version": expected_revision_version,
                "resolved": resolved,
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
            if current is None:
                raise ResourceNotFoundError
            if current.lifecycle_status != "candidate":
                raise ReviewRevisionNotCandidateError
            if current.revision_number != expected_revision_number:
                raise ReviewTaskConflictError
            if current.revision_version != expected_revision_version:
                raise PlaceRevisionVersionConflictError
            updated = replace(
                current,
                conflicts_resolved=resolved,
                solver_eligible=False,
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
                    action="PLACE_SOURCE_CONFLICTS_RESOLVED",
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

    def list_source_channels(self, principal: AdminPrincipal) -> tuple[GovernedSourceChannel, ...]:
        self._require(principal, "place:candidate:read")
        return self._source_catalog.list_channels()

    def create_source_record(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        expected_revision_version: int,
        source_id: str,
        source_url: str,
        collection_mode: str,
        observed_at: datetime,
        content_sha256: str | None,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        self._require(principal, "place:candidate:write")
        reason_text = self._validate_reason(reason_code, reason_text)
        normalized_url = source_url.strip()
        normalized_hash = content_sha256.lower() if content_sha256 else None
        try:
            channel = self._source_catalog.require_valid_input(
                source_id=source_id,
                source_url=normalized_url,
                collection_mode=collection_mode,
            )
        except SourceRecordInputError as exc:
            raise SourceRecordValidationError(str(exc)) from exc
        payload = {
            "revision_id": revision_id,
            "expected_revision_version": expected_revision_version,
            "source_id": source_id,
            "source_url": normalized_url,
            "collection_mode": collection_mode,
            "observed_at": observed_at.isoformat(),
            "content_sha256": normalized_hash,
            "reason_code": reason_code,
            "reason_text": reason_text,
        }
        operation_digest = _digest(payload)
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
            record = PlaceSourceRecord(
                source_record_id=self._ids.new_id("place_source_record"),
                place_id=revision.place_id,
                source_id=channel.source_id,
                registry_id=channel.registry_id,
                registry_sha256=channel.registry_sha256,
                field_dictionary_id=channel.field_dictionary_id,
                field_dictionary_sha256=channel.field_dictionary_sha256,
                source_url=normalized_url,
                collection_mode=collection_mode,
                target_stage="staging",
                source_decision=channel.decision,
                observed_at=observed_at,
                content_sha256=normalized_hash,
                status="active",
                created_at=self._clock.now(),
            )
            try:
                updated = uow.catalog.create_source_record(
                    record,
                    revision_id=revision_id,
                    expected_revision_version=expected_revision_version,
                )
            except ValueError as exc:
                if "version conflict" in str(exc):
                    raise PlaceRevisionVersionConflictError from exc
                if "not found" in str(exc):
                    raise ResourceNotFoundError from exc
                raise
            uow.audits.add(
                self._event(
                    actor,
                    action="PLACE_SOURCE_RECORD_CREATED",
                    target_type="place_source_record",
                    target_id=record.source_record_id,
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

    def detach_source_record(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        source_record_id: str,
        expected_revision_version: int,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        self._require(principal, "place:candidate:write")
        reason_text = self._validate_reason(reason_code, reason_text)
        operation_digest = _digest(
            {
                "revision_id": revision_id,
                "source_record_id": source_record_id,
                "expected_revision_version": expected_revision_version,
                "reason_code": reason_code,
                "reason_text": reason_text,
            }
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
            if source_record_id not in revision.source_record_ids:
                raise ResourceNotFoundError
            references = uow.catalog.source_record_references(
                source_record_id, revision_id=revision_id
            )
            if references:
                raise SourceRecordInUseError(references)
            try:
                updated = uow.catalog.detach_source_record(
                    source_record_id,
                    revision_id=revision_id,
                    expected_revision_version=expected_revision_version,
                )
            except ValueError as exc:
                if "version conflict" in str(exc):
                    raise PlaceRevisionVersionConflictError from exc
                if "not attached" in str(exc) or "not found" in str(exc):
                    raise ResourceNotFoundError from exc
                raise
            uow.audits.add(
                self._event(
                    actor,
                    action="PLACE_SOURCE_RECORD_DETACHED",
                    target_type="place_source_record",
                    target_id=source_record_id,
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
