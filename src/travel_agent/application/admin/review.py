"""Application use cases for candidate place-revision review."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from types import TracebackType
from typing import Protocol, Self

from travel_agent.application.common.clock import Clock
from travel_agent.application.common.errors import ResourceNotFoundError
from travel_agent.application.planning.ports import IdGenerator
from travel_agent.domain.admin import AdminActor, AdminAuditEvent, AdminPrincipal
from travel_agent.domain.place_catalog import (
    PlaceAccessPoint,
    PlaceClosure,
    PlaceDateException,
    PlaceGeometry,
    PlaceReviewDecision,
    PlaceReviewTask,
    PlaceRevision,
    PlaceRevisionEvidence,
    PlaceSourceRecord,
    PlaceTimeRule,
    ProjectionPublicationError,
    SolverPlaceProjection,
    evaluate_projection_publication,
)
from travel_agent.domain.place_catalog.repositories import PlaceCatalogRepository

from .errors import (
    AdminAuthenticationError,
    AdminOperationIntentConflictError,
    AdminPermissionDeniedError,
    PlaceRevisionVersionConflictError,
    PublicationGateRejectedError,
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

    def count_tasks(self, *, status: str | None) -> int: ...

    def list_decisions(self, task_id: str) -> tuple[PlaceReviewDecision, ...]: ...

    def get_revision(self, revision_id: str) -> PlaceRevision | None: ...

    def get_latest_revision(self, place_id: str) -> PlaceRevision | None: ...

    def list_revisions(
        self, *, lifecycle_status: str | None, limit: int, offset: int
    ) -> tuple[PlaceRevision, ...]: ...

    def count_revisions(self, *, lifecycle_status: str | None) -> int: ...

    def add_task(self, task: PlaceReviewTask) -> None: ...

    def add_decision(self, decision: PlaceReviewDecision) -> None: ...

    def add_revision(self, revision: PlaceRevision) -> None: ...

    def update_revision(
        self,
        revision: PlaceRevision,
        *,
        expected_revision_number: int,
        expected_revision_version: int,
    ) -> None: ...

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
    catalog: PlaceCatalogRepository
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

    def list_revisions(
        self,
        principal: AdminPrincipal,
        *,
        lifecycle_status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[PlaceRevision, ...]:
        self._require(principal, "place:candidate:read")
        with self._uow_factory() as uow:
            return uow.reviews.list_revisions(
                lifecycle_status=lifecycle_status,
                limit=limit,
                offset=offset,
            )

    def count_revisions(self, principal: AdminPrincipal, *, lifecycle_status: str | None) -> int:
        self._require(principal, "place:candidate:read")
        with self._uow_factory() as uow:
            return uow.reviews.count_revisions(lifecycle_status=lifecycle_status)

    def dashboard_summary(self, principal: AdminPrincipal) -> dict[str, object]:
        self._require(principal, "place:candidate:read")
        with self._uow_factory() as uow:
            candidates = uow.reviews.count_revisions(lifecycle_status="candidate")
            verified = uow.reviews.count_revisions(lifecycle_status="human_verified")
            published = uow.reviews.count_revisions(lifecycle_status="published")
            tasks: dict[str, int] = {}
            for task_status in ("ready_for_review", "in_review", "changes_requested", "approved", "closed"):
                tasks[task_status] = uow.reviews.count_tasks(status=task_status)
            recent = uow.reviews.list_tasks(status="ready_for_review", limit=5, offset=0)
            return {
                "revisions": {"candidate": candidates, "human_verified": verified, "published": published},
                "review_tasks": tasks,
                "recent_ready_tasks": tuple(recent),
            }

    def list_source_conflicts(self, principal: AdminPrincipal, *, revision_id: str) -> tuple[dict[str, object], ...]:
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
                conflicts.append({"source_id": source_id, "records": tuple(records), "resolved": evidence.revision.conflicts_resolved})
        return tuple(conflicts)

    def resolve_source_conflicts(self, principal: AdminPrincipal, *, revision_id: str,
                                 expected_revision_number: int, expected_revision_version: int,
                                 resolved: bool, operation_intent_id: str, reason_code: str,
                                 reason_text: str | None, request_id: str) -> PlaceRevision:
        self._require(principal, "place:candidate:write")
        reason_text = self._validate_reason(reason_code, reason_text)
        digest = _digest({"revision_id": revision_id, "expected_revision_number": expected_revision_number,
                          "expected_revision_version": expected_revision_version, "resolved": resolved,
                          "reason_code": reason_code, "reason_text": reason_text})
        now = self._clock.now()
        with self._uow_factory() as uow:
            existing = self._replay(uow, operation_intent_id, digest)
            if existing is not None:
                revision = uow.reviews.get_revision(existing.target_id)
                if revision is None: raise ResourceNotFoundError
                return revision
            actor = self._actor(uow, principal)
            current = uow.reviews.get_revision(revision_id)
            if current is None: raise ResourceNotFoundError
            if current.lifecycle_status != "candidate": raise ReviewRevisionNotCandidateError
            if current.revision_number != expected_revision_number: raise ReviewTaskConflictError
            if current.revision_version != expected_revision_version: raise PlaceRevisionVersionConflictError
            updated = replace(current, conflicts_resolved=resolved, solver_eligible=False,
                              reviewed_at=None, published_at=None, revision_version=current.revision_version + 1)
            uow.reviews.update_revision(updated, expected_revision_number=expected_revision_number,
                                        expected_revision_version=expected_revision_version)
            uow.audits.add(self._event(actor, action="PLACE_SOURCE_CONFLICTS_RESOLVED",
                                        target_type="place_revision", target_id=revision_id,
                                        target_revision=str(updated.revision_number),
                                        before_digest=_revision_digest(current), after_digest=_revision_digest(updated),
                                        reason_code=reason_code, reason_text=reason_text, request_id=request_id,
                                        operation_intent_id=operation_intent_id, operation_digest=digest))
            uow.commit()
            return updated

    def get_revision(self, principal: AdminPrincipal, *, revision_id: str) -> PlaceRevision:
        self._require(principal, "place:candidate:read")
        with self._uow_factory() as uow:
            revision = uow.reviews.get_revision(revision_id)
            if revision is None:
                raise ResourceNotFoundError
            return revision

    def get_revision_evidence(
        self, principal: AdminPrincipal, *, revision_id: str
    ) -> PlaceRevisionEvidence:
        """Return revision-scoped geometry/access-point evidence for O04."""

        self._require(principal, "place:candidate:read")
        with self._uow_factory() as uow:
            evidence = uow.catalog.load_revision_evidence(revision_id)
            if evidence is None:
                raise ResourceNotFoundError
            return evidence

    def preview_time(
        self, principal: AdminPrincipal, *, revision_id: str, service_date: date
    ) -> dict[str, object]:
        """Resolve one service date from verified O05 evidence without mutation."""
        self._require(principal, "place:candidate:read")
        with self._uow_factory() as uow:
            evidence = uow.catalog.load_revision_evidence(revision_id)
            if evidence is None:
                raise ResourceNotFoundError
        revision = evidence.revision
        active = lambda item: item.active and item.review_status == "human_verified"
        rules = tuple(sorted((r for r in evidence.time_rules if active(r)), key=lambda r: (r.rule_kind, r.time_rule_id)))
        closures = tuple(c for c in evidence.closures if active(c))
        exceptions = tuple(e for e in evidence.date_exceptions if active(e) and e.service_date == service_date)
        reasons: list[str] = []
        sessions: list[dict[str, object]] = []
        if revision.is_always_open:
            reasons.append("PLACE_ALWAYS_OPEN")
            return {"revision_id": revision_id, "service_date": service_date.isoformat(), "open": True,
                    "windows": [{"start_minute": 0, "end_minute": 1440, "last_entry_minute": None}],
                    "fixed_sessions": [], "reason_codes": reasons, "applied_exception_ids": [], "rule_ids": []}
        if len(exceptions) > 1:
            reasons.append("TIME_RULE_OVERLAP")
        if exceptions:
            exception = exceptions[0]
            if exception.exception_kind == "closed":
                reasons.append("PLACE_DATE_EXCEPTION_CLOSED")
                return {"revision_id": revision_id, "service_date": service_date.isoformat(), "open": False,
                        "windows": [], "fixed_sessions": [], "reason_codes": reasons,
                        "applied_exception_ids": [e.date_exception_id for e in exceptions], "rule_ids": []}
            reasons.append("PLACE_DATE_EXCEPTION_APPLIED")
            if exception.start_minute is not None and exception.end_minute is not None:
                windows = [{"start_minute": exception.start_minute, "end_minute": exception.end_minute,
                            "last_entry_minute": exception.last_entry_minute}]
                if exception.exception_kind == "session_override":
                    sessions.append({"date_exception_id": exception.date_exception_id,
                                     "start_minute": exception.start_minute,
                                     "end_minute": exception.end_minute,
                                     "last_entry_minute": exception.last_entry_minute})
                if exception.end_minute > 1440:
                    reasons.append("CROSS_MIDNIGHT_WINDOW")
                return {"revision_id": revision_id, "service_date": service_date.isoformat(), "open": True,
                        "windows": windows, "fixed_sessions": sessions, "reason_codes": reasons,
                        "applied_exception_ids": [e.date_exception_id for e in exceptions], "rule_ids": []}
        if any(c.weekday == service_date.isoweekday() for c in closures):
            reasons.append("PLACE_WEEKLY_CLOSED")
            return {"revision_id": revision_id, "service_date": service_date.isoformat(), "open": False,
                    "windows": [], "fixed_sessions": [], "reason_codes": reasons,
                    "applied_exception_ids": [], "rule_ids": []}
        matching = tuple(r for r in rules if service_date.isoweekday() in r.weekdays and
                         (r.valid_from is None or service_date >= r.valid_from) and
                         (r.valid_to is None or service_date <= r.valid_to))
        opening = tuple(r for r in matching if r.rule_kind == "opening_hours")
        fixed = tuple(r for r in matching if r.rule_kind == "fixed_session")
        last_entry = tuple(r for r in matching if r.rule_kind == "last_entry")
        if len(opening) > 1:
            reasons.append("TIME_RULE_OVERLAP")
        if not opening:
            reasons.append("TIME_RULE_NOT_MATCHED")
            return {"revision_id": revision_id, "service_date": service_date.isoformat(), "open": False,
                    "windows": [], "fixed_sessions": [], "reason_codes": reasons,
                    "applied_exception_ids": [], "rule_ids": [r.time_rule_id for r in matching]}
        rule = opening[0]
        end = rule.end_minute
        last = rule.last_entry_minute
        if last_entry and last_entry[0].last_entry_minute is not None:
            last = last_entry[0].last_entry_minute
        if end is None:
            end = 1440
        if last is not None and last > end:
            reasons.append("LAST_ENTRY_AFTER_CLOSE")
        if end > 1440 or (rule.start_minute or 0) >= 1440:
            reasons.append("CROSS_MIDNIGHT_WINDOW")
        for item in fixed:
            if item.start_minute is not None and item.end_minute is not None:
                sessions.append({"time_rule_id": item.time_rule_id, "start_minute": item.start_minute,
                                 "end_minute": item.end_minute, "last_entry_minute": item.last_entry_minute})
        if len(sessions) > 1:
            reasons.append("FIXED_SESSION_AMBIGUOUS")
        return {"revision_id": revision_id, "service_date": service_date.isoformat(), "open": True,
                "windows": [{"start_minute": rule.start_minute, "end_minute": end, "last_entry_minute": last}],
                "fixed_sessions": sessions, "reason_codes": reasons,
                "applied_exception_ids": [], "rule_ids": [r.time_rule_id for r in matching]}

    def create_geometry(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        expected_revision_version: int,
        geometry_kind: str,
        geometry: dict[str, object],
        source_record_id: str,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        geometry_id = self._ids.new_id("geometry")
        payload = {
            "revision_id": revision_id,
            "expected_revision_version": expected_revision_version,
            "geometry_kind": geometry_kind,
            "geometry": geometry,
            "source_record_id": source_record_id,
        }
        return self._mutate_evidence(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
            action="PLACE_GEOMETRY_CREATED",
            target_id=geometry_id,
            payload=payload,
            mutate=lambda uow, revision: (
                uow.catalog.create_geometry(
                    PlaceGeometry(
                        geometry_id,
                        revision_id,
                        geometry_kind,
                        geometry,
                        source_record_id,
                        "candidate",
                        True,
                        self._clock.now(),
                    ),
                    expected_revision_version=expected_revision_version,
                ),
                geometry_id,
            ),
        )

    def update_geometry(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        geometry_id: str,
        expected_revision_version: int,
        geometry_kind: str,
        geometry: dict[str, object],
        source_record_id: str,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        payload = {
            "revision_id": revision_id,
            "geometry_id": geometry_id,
            "expected_revision_version": expected_revision_version,
            "geometry_kind": geometry_kind,
            "geometry": geometry,
            "source_record_id": source_record_id,
        }

        def mutate(uow: ReviewUnitOfWork, revision: PlaceRevision) -> tuple[PlaceRevision, str]:
            evidence = uow.catalog.load_revision_evidence(revision_id)
            if evidence is None:
                raise ResourceNotFoundError
            current = next(
                (item for item in evidence.geometries if item.geometry_id == geometry_id),
                None,
            )
            if current is None:
                raise ResourceNotFoundError
            updated = replace(
                current,
                geometry_kind=geometry_kind,
                geometry=geometry,
                source_record_id=source_record_id,
                review_status="candidate",
                active=True,
                reviewed_at=None,
            )
            return (
                uow.catalog.update_geometry(
                    updated,
                    expected_revision_version=expected_revision_version,
                ),
                geometry_id,
            )

        return self._mutate_evidence(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
            action="PLACE_GEOMETRY_UPDATED",
            target_id=geometry_id,
            payload=payload,
            mutate=mutate,
        )

    def retire_geometry(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        geometry_id: str,
        expected_revision_version: int,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        payload = {
            "revision_id": revision_id,
            "geometry_id": geometry_id,
            "expected_revision_version": expected_revision_version,
        }
        return self._mutate_evidence(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
            action="PLACE_GEOMETRY_RETIRED",
            target_id=geometry_id,
            payload=payload,
            mutate=lambda uow, _revision: (
                uow.catalog.retire_geometry(
                    geometry_id,
                    place_revision_id=revision_id,
                    expected_revision_version=expected_revision_version,
                ),
                geometry_id,
            ),
        )

    def create_access_point(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        expected_revision_version: int,
        access_point_kind: str,
        name: str,
        lat: Decimal,
        lng: Decimal,
        source_record_id: str,
        fetched_at: datetime | None,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        access_point_id = self._ids.new_id("access_point")
        payload = {
            "revision_id": revision_id,
            "expected_revision_version": expected_revision_version,
            "access_point_kind": access_point_kind,
            "name": name,
            "lat": str(lat),
            "lng": str(lng),
            "source_record_id": source_record_id,
            "fetched_at": fetched_at.isoformat() if fetched_at else None,
        }
        return self._mutate_evidence(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
            action="PLACE_ACCESS_POINT_CREATED",
            target_id=access_point_id,
            payload=payload,
            mutate=lambda uow, _revision: (
                uow.catalog.create_access_point(
                    PlaceAccessPoint(
                        access_point_id,
                        revision_id,
                        access_point_kind,
                        name,
                        lat,
                        lng,
                        source_record_id,
                        "candidate",
                        True,
                        fetched_at,
                        None,
                        self._clock.now(),
                    ),
                    expected_revision_version=expected_revision_version,
                ),
                access_point_id,
            ),
        )

    def update_access_point(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        access_point_id: str,
        expected_revision_version: int,
        access_point_kind: str,
        name: str,
        lat: Decimal,
        lng: Decimal,
        source_record_id: str,
        fetched_at: datetime | None,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        payload = {
            "revision_id": revision_id,
            "access_point_id": access_point_id,
            "expected_revision_version": expected_revision_version,
            "access_point_kind": access_point_kind,
            "name": name,
            "lat": str(lat),
            "lng": str(lng),
            "source_record_id": source_record_id,
            "fetched_at": fetched_at.isoformat() if fetched_at else None,
        }

        def mutate(uow: ReviewUnitOfWork, _revision: PlaceRevision) -> tuple[PlaceRevision, str]:
            evidence = uow.catalog.load_revision_evidence(revision_id)
            if evidence is None:
                raise ResourceNotFoundError
            current = next(
                (
                    item
                    for item in evidence.access_points
                    if item.access_point_id == access_point_id
                ),
                None,
            )
            if current is None:
                raise ResourceNotFoundError
            updated = replace(
                current,
                access_point_kind=access_point_kind,
                name=name,
                lat=lat,
                lng=lng,
                source_record_id=source_record_id,
                review_status="candidate",
                active=True,
                fetched_at=fetched_at,
                reviewed_at=None,
            )
            return (
                uow.catalog.update_access_point(
                    updated,
                    expected_revision_version=expected_revision_version,
                ),
                access_point_id,
            )

        return self._mutate_evidence(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
            action="PLACE_ACCESS_POINT_UPDATED",
            target_id=access_point_id,
            payload=payload,
            mutate=mutate,
        )

    def retire_access_point(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        access_point_id: str,
        expected_revision_version: int,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        payload = {
            "revision_id": revision_id,
            "access_point_id": access_point_id,
            "expected_revision_version": expected_revision_version,
        }
        return self._mutate_evidence(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
            action="PLACE_ACCESS_POINT_RETIRED",
            target_id=access_point_id,
            payload=payload,
            mutate=lambda uow, _revision: (
                uow.catalog.retire_access_point(
                    access_point_id,
                    place_revision_id=revision_id,
                    expected_revision_version=expected_revision_version,
                ),
                access_point_id,
            ),
        )

    def create_time_rule(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        expected_revision_version: int,
        rule_kind: str,
        weekdays: tuple[int, ...],
        start_minute: int | None,
        end_minute: int | None,
        last_entry_minute: int | None,
        valid_from: date | None,
        valid_to: date | None,
        source_record_id: str,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        time_rule_id = self._ids.new_id("time_rule")
        payload = {
            "revision_id": revision_id,
            "expected_revision_version": expected_revision_version,
            "rule_kind": rule_kind,
            "weekdays": list(weekdays),
            "start_minute": start_minute,
            "end_minute": end_minute,
            "last_entry_minute": last_entry_minute,
            "valid_from": valid_from.isoformat() if valid_from else None,
            "valid_to": valid_to.isoformat() if valid_to else None,
            "source_record_id": source_record_id,
        }
        return self._mutate_evidence(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
            action="PLACE_TIME_RULE_CREATED",
            target_id=time_rule_id,
            payload=payload,
            mutate=lambda uow, _revision: (
                uow.catalog.create_time_rule(
                    PlaceTimeRule(
                        time_rule_id,
                        revision_id,
                        rule_kind,
                        weekdays,
                        start_minute,
                        end_minute,
                        last_entry_minute,
                        valid_from,
                        valid_to,
                        source_record_id,
                        "candidate",
                        True,
                        self._clock.now(),
                    ),
                    expected_revision_version=expected_revision_version,
                ),
                time_rule_id,
            ),
        )

    def update_time_rule(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        time_rule_id: str,
        expected_revision_version: int,
        rule_kind: str,
        weekdays: tuple[int, ...],
        start_minute: int | None,
        end_minute: int | None,
        last_entry_minute: int | None,
        valid_from: date | None,
        valid_to: date | None,
        source_record_id: str,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        payload = {
            "revision_id": revision_id,
            "time_rule_id": time_rule_id,
            "expected_revision_version": expected_revision_version,
            "rule_kind": rule_kind,
            "weekdays": list(weekdays),
            "start_minute": start_minute,
            "end_minute": end_minute,
            "last_entry_minute": last_entry_minute,
            "valid_from": valid_from.isoformat() if valid_from else None,
            "valid_to": valid_to.isoformat() if valid_to else None,
            "source_record_id": source_record_id,
        }

        def mutate(uow: ReviewUnitOfWork, _revision: PlaceRevision) -> tuple[PlaceRevision, str]:
            evidence = uow.catalog.load_revision_evidence(revision_id)
            if evidence is None:
                raise ResourceNotFoundError
            current = next(
                (item for item in evidence.time_rules if item.time_rule_id == time_rule_id),
                None,
            )
            if current is None:
                raise ResourceNotFoundError
            updated = replace(
                current,
                rule_kind=rule_kind,
                weekdays=weekdays,
                start_minute=start_minute,
                end_minute=end_minute,
                last_entry_minute=last_entry_minute,
                valid_from=valid_from,
                valid_to=valid_to,
                source_record_id=source_record_id,
                review_status="candidate",
                active=True,
                reviewed_at=None,
            )
            return (
                uow.catalog.update_time_rule(
                    updated,
                    expected_revision_version=expected_revision_version,
                ),
                time_rule_id,
            )

        return self._mutate_evidence(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
            action="PLACE_TIME_RULE_UPDATED",
            target_id=time_rule_id,
            payload=payload,
            mutate=mutate,
        )

    def retire_time_rule(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        time_rule_id: str,
        expected_revision_version: int,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        return self._retire_time_evidence(
            principal,
            revision_id=revision_id,
            evidence_kind="time_rule",
            evidence_id=time_rule_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
        )

    def create_closure(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        expected_revision_version: int,
        weekday: int,
        source_record_id: str,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        closure_id = self._ids.new_id("closure")
        payload = {
            "revision_id": revision_id,
            "expected_revision_version": expected_revision_version,
            "weekday": weekday,
            "source_record_id": source_record_id,
        }
        return self._mutate_evidence(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
            action="PLACE_CLOSURE_CREATED",
            target_id=closure_id,
            payload=payload,
            mutate=lambda uow, _revision: (
                uow.catalog.create_closure(
                    PlaceClosure(
                        closure_id,
                        revision_id,
                        weekday,
                        source_record_id,
                        "candidate",
                        True,
                        self._clock.now(),
                    ),
                    expected_revision_version=expected_revision_version,
                ),
                closure_id,
            ),
        )

    def update_closure(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        closure_id: str,
        expected_revision_version: int,
        weekday: int,
        source_record_id: str,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        payload = {
            "revision_id": revision_id,
            "closure_id": closure_id,
            "expected_revision_version": expected_revision_version,
            "weekday": weekday,
            "source_record_id": source_record_id,
        }

        def mutate(uow: ReviewUnitOfWork, _revision: PlaceRevision) -> tuple[PlaceRevision, str]:
            evidence = uow.catalog.load_revision_evidence(revision_id)
            if evidence is None:
                raise ResourceNotFoundError
            current = next(
                (item for item in evidence.closures if item.closure_id == closure_id),
                None,
            )
            if current is None:
                raise ResourceNotFoundError
            updated = replace(
                current,
                weekday=weekday,
                source_record_id=source_record_id,
                review_status="candidate",
                active=True,
                reviewed_at=None,
            )
            return (
                uow.catalog.update_closure(
                    updated,
                    expected_revision_version=expected_revision_version,
                ),
                closure_id,
            )

        return self._mutate_evidence(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
            action="PLACE_CLOSURE_UPDATED",
            target_id=closure_id,
            payload=payload,
            mutate=mutate,
        )

    def retire_closure(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        closure_id: str,
        expected_revision_version: int,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        return self._retire_time_evidence(
            principal,
            revision_id=revision_id,
            evidence_kind="closure",
            evidence_id=closure_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
        )

    def create_date_exception(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        expected_revision_version: int,
        service_date: date,
        exception_kind: str,
        start_minute: int | None,
        end_minute: int | None,
        last_entry_minute: int | None,
        source_record_id: str,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        date_exception_id = self._ids.new_id("date_exception")
        payload = {
            "revision_id": revision_id,
            "expected_revision_version": expected_revision_version,
            "service_date": service_date.isoformat(),
            "exception_kind": exception_kind,
            "start_minute": start_minute,
            "end_minute": end_minute,
            "last_entry_minute": last_entry_minute,
            "source_record_id": source_record_id,
        }
        return self._mutate_evidence(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
            action="PLACE_DATE_EXCEPTION_CREATED",
            target_id=date_exception_id,
            payload=payload,
            mutate=lambda uow, _revision: (
                uow.catalog.create_date_exception(
                    PlaceDateException(
                        date_exception_id,
                        revision_id,
                        service_date,
                        exception_kind,
                        start_minute,
                        end_minute,
                        last_entry_minute,
                        source_record_id,
                        "candidate",
                        True,
                        self._clock.now(),
                    ),
                    expected_revision_version=expected_revision_version,
                ),
                date_exception_id,
            ),
        )

    def update_date_exception(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        date_exception_id: str,
        expected_revision_version: int,
        service_date: date,
        exception_kind: str,
        start_minute: int | None,
        end_minute: int | None,
        last_entry_minute: int | None,
        source_record_id: str,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        payload = {
            "revision_id": revision_id,
            "date_exception_id": date_exception_id,
            "expected_revision_version": expected_revision_version,
            "service_date": service_date.isoformat(),
            "exception_kind": exception_kind,
            "start_minute": start_minute,
            "end_minute": end_minute,
            "last_entry_minute": last_entry_minute,
            "source_record_id": source_record_id,
        }

        def mutate(uow: ReviewUnitOfWork, _revision: PlaceRevision) -> tuple[PlaceRevision, str]:
            evidence = uow.catalog.load_revision_evidence(revision_id)
            if evidence is None:
                raise ResourceNotFoundError
            current = next(
                (
                    item
                    for item in evidence.date_exceptions
                    if item.date_exception_id == date_exception_id
                ),
                None,
            )
            if current is None:
                raise ResourceNotFoundError
            updated = replace(
                current,
                service_date=service_date,
                exception_kind=exception_kind,
                start_minute=start_minute,
                end_minute=end_minute,
                last_entry_minute=last_entry_minute,
                source_record_id=source_record_id,
                review_status="candidate",
                active=True,
                reviewed_at=None,
            )
            return (
                uow.catalog.update_date_exception(
                    updated,
                    expected_revision_version=expected_revision_version,
                ),
                date_exception_id,
            )

        return self._mutate_evidence(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
            action="PLACE_DATE_EXCEPTION_UPDATED",
            target_id=date_exception_id,
            payload=payload,
            mutate=mutate,
        )

    def retire_date_exception(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        date_exception_id: str,
        expected_revision_version: int,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        return self._retire_time_evidence(
            principal,
            revision_id=revision_id,
            evidence_kind="date_exception",
            evidence_id=date_exception_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
        )

    def _retire_time_evidence(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        evidence_kind: str,
        evidence_id: str,
        expected_revision_version: int,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        repository_method = {
            "time_rule": "retire_time_rule",
            "closure": "retire_closure",
            "date_exception": "retire_date_exception",
        }[evidence_kind]
        action = f"PLACE_{evidence_kind.upper()}_RETIRED"
        payload = {
            "revision_id": revision_id,
            f"{evidence_kind}_id": evidence_id,
            "expected_revision_version": expected_revision_version,
        }

        def mutate(uow: ReviewUnitOfWork, _revision: PlaceRevision) -> tuple[PlaceRevision, str]:
            method = getattr(uow.catalog, repository_method)
            return (
                method(
                    evidence_id,
                    place_revision_id=revision_id,
                    expected_revision_version=expected_revision_version,
                ),
                evidence_id,
            )

        return self._mutate_evidence(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
            action=action,
            target_id=evidence_id,
            payload=payload,
            mutate=mutate,
        )

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
        mutate: Callable[[ReviewUnitOfWork, PlaceRevision], tuple[PlaceRevision, str]],
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

    def review_evidence(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        evidence_kind: str,
        evidence_id: str,
        review_status: str,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        self._require(principal, "place:review:decide")
        reason_text = self._validate_reason(reason_code, reason_text)
        digest = _digest(
            {
                "revision_id": revision_id,
                "evidence_kind": evidence_kind,
                "evidence_id": evidence_id,
                "review_status": review_status,
                "reason_code": reason_code,
                "reason_text": reason_text,
            }
        )
        now = self._clock.now()
        with self._uow_factory() as uow:
            replay = self._replay(uow, operation_intent_id, digest)
            if replay is not None:
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
            task = uow.reviews.get_open_task_for_revision(revision_id)
            if task is None:
                raise ReviewTaskNotFoundError
            evidence = uow.catalog.load_revision_evidence(revision_id)
            if evidence is None:
                raise ResourceNotFoundError
            items = (
                evidence.geometries
                if evidence_kind == "geometry"
                else evidence.access_points
                if evidence_kind == "access_point"
                else evidence.time_rules
                if evidence_kind == "time_rule"
                else evidence.closures
                if evidence_kind == "closure"
                else evidence.date_exceptions
                if evidence_kind == "date_exception"
                else ()
            )
            current = next(
                (
                    item
                    for item in items
                    if getattr(item, f"{evidence_kind}_id", None) == evidence_id
                ),
                None,
            )
            if current is None or not current.active:
                raise ResourceNotFoundError
            try:
                updated = uow.catalog.review_evidence(
                    revision_id=revision_id,
                    evidence_kind=evidence_kind,
                    evidence_id=evidence_id,
                    review_status=review_status,
                    reviewed_at=now,
                )
            except ValueError as exc:
                if "not found" in str(exc):
                    raise ResourceNotFoundError from exc
                raise
            uow.audits.add(
                self._event(
                    actor,
                    action="PLACE_EVIDENCE_REVIEWED",
                    target_type=f"place_{evidence_kind}",
                    target_id=evidence_id,
                    target_revision=str(updated.revision_number),
                    before_digest=_evidence_digest(current),
                    after_digest=_digest(
                        {
                            "evidence_id": evidence_id,
                            "review_status": review_status,
                            "reviewed_at": (
                                now.isoformat()
                                if review_status == "human_verified"
                                else None
                            ),
                            "active": True,
                        }
                    ),
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=digest,
                )
            )
            uow.commit()
            return updated

    def create_revision(
        self,
        principal: AdminPrincipal,
        *,
        place_id: str,
        base_revision_id: str,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        self._require(principal, "place:candidate:write")
        reason_text = self._validate_reason(reason_code, reason_text)
        operation_digest = _digest(
            {
                "place_id": place_id,
                "base_revision_id": base_revision_id,
                "reason_code": reason_code,
                "reason_text": reason_text,
            }
        )
        now = self._clock.now()
        with self._uow_factory() as uow:
            existing = self._replay(uow, operation_intent_id, operation_digest)
            if existing is not None:
                revision = uow.reviews.get_revision(existing.target_id)
                if revision is None:
                    raise ResourceNotFoundError
                return revision
            actor = self._actor(uow, principal)
            base = uow.reviews.get_revision(base_revision_id)
            latest = uow.reviews.get_latest_revision(place_id)
            if base is None or latest is None or base.place_id != place_id:
                raise ResourceNotFoundError
            revision = replace(
                base,
                place_revision_id=self._ids.new_id("place_revision"),
                revision_number=latest.revision_number + 1,
                lifecycle_status="candidate",
                solver_eligible=False,
                conflicts_resolved=False,
                reviewed_at=None,
                published_at=None,
                revision_version=1,
                created_at=now,
            )
            uow.reviews.add_revision(revision)
            uow.audits.add(
                self._event(
                    actor,
                    action="PLACE_REVISION_CREATED",
                    target_type="place_revision",
                    target_id=revision.place_revision_id,
                    target_revision=str(revision.revision_number),
                    before_digest=_revision_digest(base),
                    after_digest=_revision_digest(revision),
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=operation_digest,
                )
            )
            uow.commit()
            return revision

    def update_revision(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        expected_revision_number: int,
        changes: dict[str, object],
        expected_revision_version: int | None = None,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        self._require(principal, "place:candidate:write")
        reason_text = self._validate_reason(reason_code, reason_text)
        allowed = {
            "canonical_name",
            "aliases",
            "place_kind",
            "category",
            "admin_area",
            "address",
            "geometry_kind",
            "duration_min",
            "duration_recommended",
            "duration_max",
            "internal_travel_min",
            "energy_level",
            "indoor_outdoor",
            "suitable_periods",
            "audience_tags",
            "rain_suitability",
            "is_always_open",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError("unsupported revision fields: " + ", ".join(sorted(unknown)))
        normalized = {
            key: tuple(value)
            if key in {"aliases", "suitable_periods", "audience_tags"} and isinstance(value, list)
            else value
            for key, value in changes.items()
        }
        operation_digest = _digest(
            {
                "revision_id": revision_id,
                "expected_revision_number": expected_revision_number,
                "changes": normalized,
                "reason_code": reason_code,
                "reason_text": reason_text,
            }
        )
        with self._uow_factory() as uow:
            existing = self._replay(uow, operation_intent_id, operation_digest)
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
            expected_version = (
                current.revision_version
                if expected_revision_version is None
                else expected_revision_version
            )
            if current.revision_version != expected_version:
                raise PlaceRevisionVersionConflictError
            updated = replace(
                current,
                **normalized,
                solver_eligible=False,
                conflicts_resolved=False,
                reviewed_at=None,
                published_at=None,
                revision_version=current.revision_version + 1,
            )
            uow.reviews.update_revision(
                updated,
                expected_revision_number=expected_revision_number,
                expected_revision_version=expected_version,
            )
            uow.audits.add(
                self._event(
                    actor,
                    action="PLACE_REVISION_UPDATED",
                    target_type="place_revision",
                    target_id=revision_id,
                    target_revision=str(updated.revision_number),
                    before_digest=_revision_digest(current),
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

    def publication_check(self, principal: AdminPrincipal, *, revision_id: str) -> tuple[str, ...]:
        self._require(principal, "place:publication:check")
        with self._uow_factory() as uow:
            revision = uow.reviews.get_revision(revision_id)
            if revision is None:
                raise ResourceNotFoundError
            projection = uow.catalog.get_projection_for_revision(revision_id)
            if projection is None:
                return ("PROJECTION_NOT_FOUND",)
            context = uow.catalog.load_publication_context(projection.projection_id)
            if context is None:
                return ("PROJECTION_DEPENDENCY_MISSING",)
            return evaluate_projection_publication(context)

    def publish_revision(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> SolverPlaceProjection:
        self._require(principal, "place:publication:write")
        reason_text = self._validate_reason(reason_code, reason_text)
        now = self._clock.now()
        with self._uow_factory() as uow:
            actor = self._actor(uow, principal)
            revision = uow.reviews.get_revision(revision_id)
            projection = uow.catalog.get_projection_for_revision(revision_id)
            if revision is None or projection is None:
                raise ResourceNotFoundError
            operation_digest = _digest(
                {
                    "revision_id": revision_id,
                    "projection_id": projection.projection_id,
                    "reason_code": reason_code,
                    "reason_text": reason_text,
                }
            )
            existing = self._replay(uow, operation_intent_id, operation_digest)
            if existing is not None:
                return projection
            context = uow.catalog.load_publication_context(projection.projection_id)
            if context is None:
                raise PublicationGateRejectedError(("PROJECTION_DEPENDENCY_MISSING",))
            reasons = evaluate_projection_publication(context)
            if reasons:
                raise PublicationGateRejectedError(reasons)
            before_digest = _revision_digest(revision)
            try:
                published = uow.catalog.publish_projection(
                    projection.projection_id, published_at=now
                )
            except ProjectionPublicationError as exc:
                raise PublicationGateRejectedError(exc.reason_codes) from exc
            uow.audits.add(
                self._event(
                    actor,
                    action="PLACE_REVISION_PUBLISHED",
                    target_type="place_revision",
                    target_id=revision_id,
                    target_revision=str(revision.revision_number),
                    before_digest=before_digest,
                    after_digest=_digest(
                        {"projection_id": published.projection_id, "status": published.status}
                    ),
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=operation_digest,
                )
            )
            uow.commit()
            return published

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
            if decision_kind == "approve":
                evidence = uow.catalog.load_revision_evidence(task.place_revision_id)
                source_conflict = False
                if evidence is not None:
                    grouped: dict[str, set[str]] = {}
                    for source in evidence.source_records:
                        grouped.setdefault(source.source_id, set()).add(
                            source.content_sha256 or source.registry_sha256
                        )
                    source_conflict = any(len(fingerprints) > 1 for fingerprints in grouped.values())
                if evidence is None or source_conflict and not revision.conflicts_resolved or evidence is not None and any(
                    item.active and item.review_status != "human_verified"
                    for item in (
                        *evidence.geometries,
                        *evidence.access_points,
                        *evidence.time_rules,
                        *evidence.closures,
                        *evidence.date_exceptions,
                        *evidence.relations,
                    )
                ):
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
    if error_code == "publication_gate_rejected":
        raise PublicationGateRejectedError(())
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
            "revision_version": revision.revision_version,
            "lifecycle_status": revision.lifecycle_status,
            "canonical_name": revision.canonical_name,
        }
    )


def _evidence_target_type(action: str) -> str:
    for marker, target_type in (
        ("DATE_EXCEPTION", "place_date_exception"),
        ("ACCESS_POINT", "place_access_point"),
        ("TIME_RULE", "place_time_rule"),
        ("GEOMETRY", "place_geometry"),
        ("CLOSURE", "place_closure"),
    ):
        if marker in action:
            return target_type
    raise ValueError("unknown place evidence action")


def _evidence_digest(
    value: PlaceGeometry
    | PlaceAccessPoint
    | PlaceTimeRule
    | PlaceClosure
    | PlaceDateException,
) -> str:
    evidence_id = next(
        getattr(value, name)
        for name in (
            "geometry_id",
            "access_point_id",
            "time_rule_id",
            "closure_id",
            "date_exception_id",
        )
        if hasattr(value, name)
    )
    return _digest(
        {
            "evidence_id": evidence_id,
            "review_status": value.review_status,
            "reviewed_at": value.reviewed_at.isoformat() if value.reviewed_at else None,
            "active": value.active,
        }
    )


def _digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
