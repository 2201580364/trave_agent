"""Application use cases for candidate place-revision review."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal

from travel_agent.application.common.clock import Clock
from travel_agent.application.common.errors import ResourceNotFoundError
from travel_agent.application.planning.ports import IdGenerator
from travel_agent.domain.admin import AdminActor, AdminAuditEvent, AdminPrincipal
from travel_agent.domain.place_catalog import (
    HolidayCalendar,
    PlaceReviewDecision,
    PlaceReviewTask,
    PlaceRevision,
    PlaceRevisionEvidence,
    ProjectionPublicationContext,
    ProjectionPublicationError,
    PublicationBatch,
    PublicationBatchItem,
    ResearchSnapshot,
    SolverPlaceProjection,
    evaluate_projection_publication,
)
from travel_agent.domain.place_catalog.session_payload import (
    build_fixed_session_payload,
)

from .audit_events import (
    review_flow_role,
)
from .errors import (
    AdminOperationIntentConflictError,
    PlaceRevisionVersionConflictError,
    ProjectionPreparationRejectedError,
    PublicationGateRejectedError,
    ReviewRevisionNotApprovableError,
    ReviewRevisionNotCandidateError,
    ReviewTaskConflictError,
    ReviewTaskNotFoundError,
)
from .review_evidence import EvidenceMutationSupport, _evidence_digest
from .review_geometry import ReviewGeometryService
from .review_ports import ActorRepository as ActorRepository
from .review_ports import AuditRepository as AuditRepository
from .review_ports import ReviewRepository as ReviewRepository
from .review_ports import ReviewUnitOfWork as ReviewUnitOfWork
from .review_readiness import evaluate_review_readiness as evaluate_review_readiness
from .review_relations import ReviewRelationService
from .review_sources import ReviewSourceService
from .review_support import _digest, _revision_digest
from .review_time import (
    BuiltinHolidayCalendarCatalog,
    ReviewTimeService,
)
from .review_time import (
    HolidayCalendarCatalog as HolidayCalendarCatalog,
)
from .sources import GovernedSourceCatalog, GovernedSourceChannel

_REASON_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_SENSITIVE_REASON_PATTERN = re.compile(
    r"(?i)(api[ _-]?key|access[ _-]?token|password|passwd|cookie|secret|私钥|密码|令牌)"
)
_OPEN_TASK_STATUSES = frozenset({"ready_for_review", "in_review", "changes_requested"})


def _access_rank(kind: str, departure: bool) -> int:
    order = (
        {"visitor_exit": 0, "route_end": 1, "visitor_entrance": 2, "route_start": 3}
        if departure
        else {
            "visitor_entrance": 0,
            "route_start": 1,
            "performance_location": 2,
            "area_representative": 3,
        }
    )
    return order.get(kind, 10)


class PlaceReviewWorkflowService(EvidenceMutationSupport[ReviewUnitOfWork]):
    def __init__(
        self,
        uow_factory: Callable[[], ReviewUnitOfWork],
        clock: Clock,
        ids: IdGenerator,
        source_catalog: GovernedSourceCatalog,
        holiday_calendars: HolidayCalendarCatalog | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._ids = ids
        self._source_catalog = source_catalog
        self._holiday_calendars = holiday_calendars or BuiltinHolidayCalendarCatalog()
        self._sources = ReviewSourceService(uow_factory, clock, ids, source_catalog)
        self._geometry = ReviewGeometryService(uow_factory, clock, ids)
        self._relations = ReviewRelationService(uow_factory, clock, ids)
        self._time = ReviewTimeService(uow_factory, clock, ids, self._holiday_calendars)

    def list_holiday_calendars(self, principal: AdminPrincipal) -> tuple[HolidayCalendar, ...]:
        return self._time.list_holiday_calendars(
            principal,
        )

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

    def revisions_by_ids(
        self,
        principal: AdminPrincipal,
        *,
        revision_ids: tuple[str, ...],
    ) -> dict[str, PlaceRevision]:
        self._require(principal, "place:review:read")
        normalized = tuple(dict.fromkeys(revision_ids))
        with self._uow_factory() as uow:
            return {
                revision.place_revision_id: revision
                for revision in uow.reviews.get_revisions(normalized)
            }

    def list_revisions(
        self,
        principal: AdminPrincipal,
        *,
        lifecycle_status: str | None,
        limit: int,
        offset: int,
        keyword: str | None = None,
        admin_area: str | None = None,
        place_kind: str | None = None,
    ) -> tuple[PlaceRevision, ...]:
        self._require(principal, "place:candidate:read")
        with self._uow_factory() as uow:
            return uow.reviews.list_revisions(
                lifecycle_status=lifecycle_status,
                keyword=_optional_query(keyword),
                admin_area=_optional_query(admin_area),
                place_kind=_optional_query(place_kind),
                limit=limit,
                offset=offset,
            )

    def count_revisions(
        self,
        principal: AdminPrincipal,
        *,
        lifecycle_status: str | None,
        keyword: str | None = None,
        admin_area: str | None = None,
        place_kind: str | None = None,
    ) -> int:
        self._require(principal, "place:candidate:read")
        with self._uow_factory() as uow:
            return uow.reviews.count_revisions(
                lifecycle_status=lifecycle_status,
                keyword=_optional_query(keyword),
                admin_area=_optional_query(admin_area),
                place_kind=_optional_query(place_kind),
            )

    def review_readiness_by_revision_ids(
        self,
        principal: AdminPrincipal,
        *,
        revision_ids: tuple[str, ...],
    ) -> dict[str, dict[str, object]]:
        """Return collection/review readiness without mutating workflow state."""

        self._require(principal, "place:candidate:read")
        normalized = tuple(dict.fromkeys(revision_ids))
        with self._uow_factory() as uow:
            result: dict[str, dict[str, object]] = {}
            for revision_id in normalized:
                evidence = uow.catalog.load_revision_evidence(revision_id)
                if evidence is None:
                    continue
                result[revision_id] = evaluate_review_readiness(
                    evidence,
                    uow.reviews.get_open_task_for_revision(revision_id),
                )
            return result

    def dashboard_summary(self, principal: AdminPrincipal) -> dict[str, object]:
        self._require(principal, "place:candidate:read")
        with self._uow_factory() as uow:
            candidates = uow.reviews.count_revisions(lifecycle_status="candidate")
            verified = uow.reviews.count_revisions(lifecycle_status="human_verified")
            published = uow.reviews.count_revisions(lifecycle_status="published")
            tasks: dict[str, int] = {}
            for task_status in (
                "ready_for_review",
                "in_review",
                "changes_requested",
                "approved",
                "closed",
            ):
                tasks[task_status] = uow.reviews.count_tasks(status=task_status)
            recent = uow.reviews.list_tasks(
                status="ready_for_review",
                keyword=None,
                admin_area=None,
                place_kind=None,
                limit=5,
                offset=0,
            )
            return {
                "revisions": {
                    "candidate": candidates,
                    "human_verified": verified,
                    "published": published,
                },
                "review_tasks": tasks,
                "recent_ready_tasks": tuple(recent),
            }

    def list_source_conflicts(
        self, principal: AdminPrincipal, *, revision_id: str
    ) -> tuple[dict[str, object], ...]:
        return self._sources.list_source_conflicts(principal, revision_id=revision_id)

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
        return self._sources.resolve_source_conflicts(
            principal,
            revision_id=revision_id,
            expected_revision_number=expected_revision_number,
            expected_revision_version=expected_revision_version,
            resolved=resolved,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
        )

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
        return self._relations.resolve_relation(
            principal,
            revision_id=revision_id,
            relation_id=relation_id,
            expected_revision_version=expected_revision_version,
            resolution_status=resolution_status,
            decision_note=decision_note,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
        )

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
        return self._relations.confirm_no_relations(
            principal,
            revision_id=revision_id,
            expected_revision_number=expected_revision_number,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
        )

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

    def list_source_channels(self, principal: AdminPrincipal) -> tuple[GovernedSourceChannel, ...]:
        return self._sources.list_source_channels(principal)

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
        return self._sources.create_source_record(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            source_id=source_id,
            source_url=source_url,
            collection_mode=collection_mode,
            observed_at=observed_at,
            content_sha256=content_sha256,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
        )

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
        return self._sources.detach_source_record(
            principal,
            revision_id=revision_id,
            source_record_id=source_record_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
        )

    def preview_time(
        self, principal: AdminPrincipal, *, revision_id: str, service_date: date
    ) -> dict[str, object]:
        return self._time.preview_time(
            principal,
            revision_id=revision_id,
            service_date=service_date,
        )

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
        return self._geometry.create_geometry(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            geometry_kind=geometry_kind,
            geometry=geometry,
            source_record_id=source_record_id,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
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
        return self._geometry.update_geometry(
            principal,
            revision_id=revision_id,
            geometry_id=geometry_id,
            expected_revision_version=expected_revision_version,
            geometry_kind=geometry_kind,
            geometry=geometry,
            source_record_id=source_record_id,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
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
        return self._geometry.retire_geometry(
            principal,
            revision_id=revision_id,
            geometry_id=geometry_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
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
        return self._geometry.create_access_point(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            access_point_kind=access_point_kind,
            name=name,
            lat=lat,
            lng=lng,
            source_record_id=source_record_id,
            fetched_at=fetched_at,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
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
        return self._geometry.update_access_point(
            principal,
            revision_id=revision_id,
            access_point_id=access_point_id,
            expected_revision_version=expected_revision_version,
            access_point_kind=access_point_kind,
            name=name,
            lat=lat,
            lng=lng,
            source_record_id=source_record_id,
            fetched_at=fetched_at,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
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
        return self._geometry.retire_access_point(
            principal,
            revision_id=revision_id,
            access_point_id=access_point_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
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
        return self._time.create_time_rule(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            rule_kind=rule_kind,
            weekdays=weekdays,
            start_minute=start_minute,
            end_minute=end_minute,
            last_entry_minute=last_entry_minute,
            valid_from=valid_from,
            valid_to=valid_to,
            source_record_id=source_record_id,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
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
        return self._time.update_time_rule(
            principal,
            revision_id=revision_id,
            time_rule_id=time_rule_id,
            expected_revision_version=expected_revision_version,
            rule_kind=rule_kind,
            weekdays=weekdays,
            start_minute=start_minute,
            end_minute=end_minute,
            last_entry_minute=last_entry_minute,
            valid_from=valid_from,
            valid_to=valid_to,
            source_record_id=source_record_id,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
        )

    def delete_time_rule(
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
        return self._time.delete_time_rule(
            principal,
            revision_id=revision_id,
            time_rule_id=time_rule_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
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
        return self._time.retire_time_rule(
            principal,
            revision_id=revision_id,
            time_rule_id=time_rule_id,
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
        return self._time.create_closure(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            weekday=weekday,
            source_record_id=source_record_id,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
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
        return self._time.update_closure(
            principal,
            revision_id=revision_id,
            closure_id=closure_id,
            expected_revision_version=expected_revision_version,
            weekday=weekday,
            source_record_id=source_record_id,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
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
        return self._time.retire_closure(
            principal,
            revision_id=revision_id,
            closure_id=closure_id,
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
        return self._time.create_date_exception(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            service_date=service_date,
            exception_kind=exception_kind,
            start_minute=start_minute,
            end_minute=end_minute,
            last_entry_minute=last_entry_minute,
            source_record_id=source_record_id,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
        )

    def generate_holiday_exceptions(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        expected_revision_version: int,
        calendar_id: str,
        source_record_id: str,
        open_start_minute: int,
        open_end_minute: int,
        open_last_entry_minute: int | None,
        shift_closure: bool,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        return self._time.generate_holiday_exceptions(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            calendar_id=calendar_id,
            source_record_id=source_record_id,
            open_start_minute=open_start_minute,
            open_end_minute=open_end_minute,
            open_last_entry_minute=open_last_entry_minute,
            shift_closure=shift_closure,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
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
        return self._time.update_date_exception(
            principal,
            revision_id=revision_id,
            date_exception_id=date_exception_id,
            expected_revision_version=expected_revision_version,
            service_date=service_date,
            exception_kind=exception_kind,
            start_minute=start_minute,
            end_minute=end_minute,
            last_entry_minute=last_entry_minute,
            source_record_id=source_record_id,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
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
        return self._time.retire_date_exception(
            principal,
            revision_id=revision_id,
            date_exception_id=date_exception_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
        )

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
                else evidence.relations
                if evidence_kind == "relation"
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
                    place_id=revision.place_id,
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
                                now.isoformat() if review_status == "human_verified" else None
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
                relation_review_status="pending",
                created_at=now,
            )
            uow.reviews.add_revision(revision)
            # A new revision inherits the currently active evidence as a new,
            # unverified copy.  Child rows are revision-scoped, so merely
            # copying the parent row would leave the editor with an empty
            # evidence set and force needless re-entry of unchanged facts.
            evidence = uow.catalog.load_revision_evidence(base_revision_id)
            if evidence is not None:
                for item in evidence.geometries:
                    if item.active:
                        uow.catalog.add_geometry(
                            replace(
                                item,
                                geometry_id=self._ids.new_id("geometry"),
                                place_revision_id=revision.place_revision_id,
                                review_status="candidate",
                                reviewed_at=None,
                                created_at=now,
                            )
                        )
                for item in evidence.access_points:
                    if item.active:
                        uow.catalog.add_access_point(
                            replace(
                                item,
                                access_point_id=self._ids.new_id("access_point"),
                                place_revision_id=revision.place_revision_id,
                                review_status="candidate",
                                reviewed_at=None,
                                created_at=now,
                            )
                        )
                for item in evidence.time_rules:
                    if item.active:
                        uow.catalog.add_time_rule(
                            replace(
                                item,
                                time_rule_id=self._ids.new_id("time_rule"),
                                place_revision_id=revision.place_revision_id,
                                review_status="candidate",
                                reviewed_at=None,
                                created_at=now,
                            )
                        )
                for item in evidence.closures:
                    if item.active:
                        uow.catalog.add_closure(
                            replace(
                                item,
                                closure_id=self._ids.new_id("closure"),
                                place_revision_id=revision.place_revision_id,
                                review_status="candidate",
                                reviewed_at=None,
                                created_at=now,
                            )
                        )
                for item in evidence.date_exceptions:
                    if item.active:
                        uow.catalog.add_date_exception(
                            replace(
                                item,
                                date_exception_id=self._ids.new_id("date_exception"),
                                place_revision_id=revision.place_revision_id,
                                review_status="candidate",
                                reviewed_at=None,
                                created_at=now,
                            )
                        )
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

            # Imported candidates use 1/1/1 as a temporary "not collected"
            # duration marker.  The editor intentionally exposes the
            # recommended duration first; accepting that edit must establish
            # a valid range instead of returning an opaque 422.  For a real
            # range, retain the domain invariant and return a field-specific
            # validation message when the recommendation is outside it.
            if "duration_recommended" in normalized:
                recommended = normalized["duration_recommended"]
                if not isinstance(recommended, int):
                    raise ValueError("建议时长必须是整数分钟")
                has_explicit_range = "duration_min" in normalized or "duration_max" in normalized
                if (
                    not has_explicit_range
                    and current.duration_min
                    == current.duration_recommended
                    == current.duration_max
                    == 1
                    and "DURATION_NOT_COLLECTED" in current.review_flags
                ):
                    normalized["duration_min"] = recommended
                    normalized["duration_max"] = recommended
                    normalized["review_flags"] = tuple(
                        flag for flag in current.review_flags if flag != "DURATION_NOT_COLLECTED"
                    )
                else:
                    minimum = normalized.get("duration_min", current.duration_min)
                    maximum = normalized.get("duration_max", current.duration_max)
                    if (
                        not isinstance(minimum, int)
                        or not isinstance(maximum, int)
                        or not minimum <= recommended <= maximum
                    ):
                        msg = (
                            f"建议时长必须介于 {minimum} 到 {maximum} 分钟之间；"
                            f"如需调整范围，请同时修改最短和最长时长"
                        )
                        raise ValueError(msg)
            cleared_flags: set[str] = set()
            if "canonical_name" in normalized:
                cleared_flags.add("NAME_REQUIRES_HUMAN_VERIFICATION")
            if "category" in normalized:
                cleared_flags.add("CATEGORY_REQUIRES_HUMAN_VERIFICATION")
            if {"duration_min", "duration_recommended", "duration_max"}.intersection(normalized):
                cleared_flags.add("DURATION_NOT_COLLECTED")
            if normalized.get("is_always_open") is True:
                cleared_flags.add("TIME_RULES_NOT_COLLECTED")
            if cleared_flags:
                existing_flags = normalized.get("review_flags", current.review_flags)
                if not isinstance(existing_flags, tuple):
                    raise ValueError("review flags are invalid")
                normalized["review_flags"] = tuple(
                    flag for flag in existing_flags if flag not in cleared_flags
                )
            updated = replace(
                current,
                **normalized,
                solver_eligible=False,
                conflicts_resolved=False,
                reviewed_at=None,
                published_at=None,
                revision_version=current.revision_version + 1,
                relation_review_status="pending",
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

    def prepare_projection(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        data_snapshot_version: str,
        solver_node_id: int | None,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> SolverPlaceProjection:
        """Create an auditable candidate projection from a verified revision."""
        self._require(principal, "place:publication:write")
        reason_text = self._validate_reason(reason_code, reason_text)
        digest = _digest(
            {
                "revision_id": revision_id,
                "data_snapshot_version": data_snapshot_version,
                "solver_node_id": solver_node_id,
                "reason_code": reason_code,
                "reason_text": reason_text,
            }
        )
        with self._uow_factory() as uow:
            existing = self._replay(uow, operation_intent_id, digest)
            if existing is not None:
                projection = uow.catalog.get_projection(existing.target_id)
                if projection is None:
                    raise ResourceNotFoundError
                return projection
            actor = self._actor(uow, principal)
            revision = uow.reviews.get_revision(revision_id)
            evidence = uow.catalog.load_revision_evidence(revision_id)
            place = uow.catalog.get_place(revision.place_id) if revision else None
            if revision is None or evidence is None or place is None:
                raise ResourceNotFoundError
            if revision.lifecycle_status != "human_verified":
                raise ReviewRevisionNotApprovableError(not_candidate=True)
            if solver_node_id is None:
                solver_node_id = uow.catalog.next_solver_node_id(data_snapshot_version)
            elif solver_node_id <= 0:
                raise ValueError("solver node id must be positive")
            if uow.catalog.get_projection_for_revision(revision_id) is not None:
                raise ProjectionPreparationRejectedError(("PROJECTION_ALREADY_EXISTS",))
            access_points = tuple(
                item
                for item in evidence.access_points
                if item.active and item.review_status == "human_verified"
            )
            if not access_points:
                raise ProjectionPreparationRejectedError(("MISSING_VERIFIED_ACCESS_POINT",))
            arrival = min(
                access_points,
                key=lambda item: (
                    _access_rank(item.access_point_kind, False),
                    item.access_point_id,
                ),
            )
            departure = min(
                access_points,
                key=lambda item: (_access_rank(item.access_point_kind, True), item.access_point_id),
            )
            payload = {
                "attraction_id": revision.place_id,
                "name": revision.canonical_name,
                "suggested_duration": revision.duration_recommended,
                "close_days": sorted({item.weekday for item in evidence.closures if item.active}),
                "is_always_open": revision.is_always_open,
                "is_indoor": revision.indoor_outdoor == "indoor",
                "energy_level": revision.energy_level,
                "data_verified": False,
            }
            if revision.place_kind == "show":
                payload["fixed_sessions"] = build_fixed_session_payload(evidence)
            projection = SolverPlaceProjection(
                self._ids.new_id("solver_projection"),
                "solver-place-projection-v1",
                data_snapshot_version,
                revision.place_id,
                revision_id,
                solver_node_id,
                revision.place_kind,
                revision.geometry_kind,
                arrival.access_point_id,
                departure.access_point_id,
                revision.duration_min,
                revision.duration_recommended,
                revision.duration_max,
                revision.internal_travel_min,
                payload,
                "0" * 64,
                "candidate",
                (),
                self._clock.now(),
            )
            from travel_agent.domain.place_catalog import canonical_projection_sha256

            projection = replace(
                projection, projection_hash=canonical_projection_sha256(projection)
            )
            context = ProjectionPublicationContext(
                place,
                revision,
                evidence.source_records,
                evidence.geometries,
                evidence.access_points,
                evidence.time_rules,
                evidence.relations,
                projection,
            )
            reasons = evaluate_projection_publication(context)
            if not reasons:
                payload["data_verified"] = True
                projection = replace(
                    projection,
                    solver_payload=payload,
                    projection_hash=canonical_projection_sha256(
                        replace(projection, solver_payload=payload)
                    ),
                )
            projection = replace(projection, gate_reason_codes=reasons)
            uow.catalog.add_projection(projection)
            uow.audits.add(
                self._event(
                    actor,
                    action="SOLVER_PROJECTION_PREPARED",
                    target_type="solver_projection",
                    target_id=projection.projection_id,
                    target_revision=str(revision.revision_number),
                    before_digest=None,
                    after_digest=_digest(
                        {"revision_id": revision_id, "gate_reason_codes": reasons}
                    ),
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=digest,
                )
            )
            uow.commit()
            return projection

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

    def preview_publication_batch(
        self,
        principal: AdminPrincipal,
        *,
        city_id: str,
        revision_ids: tuple[str, ...],
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> dict[str, object]:
        """Create an auditable, non-mutating publication batch preview."""
        self._require(principal, "place:publication:write")
        reason_text = self._validate_reason(reason_code, reason_text)
        normalized_ids = tuple(dict.fromkeys(revision_ids))
        if not normalized_ids or len(normalized_ids) > 500:
            raise ValueError("publication batch must contain 1 to 500 revisions")
        operation_digest = _digest(
            {
                "city_id": city_id,
                "revision_ids": normalized_ids,
                "reason_code": reason_code,
                "reason_text": reason_text,
            }
        )
        with self._uow_factory() as uow:
            existing = uow.audits.get_by_operation_intent(operation_intent_id)
            if existing is not None:
                if existing.operation_digest != operation_digest:
                    raise AdminOperationIntentConflictError
                batch = uow.catalog.get_publication_batch(existing.target_id)
                if batch is None:
                    raise ResourceNotFoundError
                return self._publication_batch_response(uow, batch)
            actor = self._actor(uow, principal)
            batch = PublicationBatch(
                self._ids.new_id("publication_batch"),
                city_id,
                operation_intent_id,
                actor.admin_actor_id,
                self._clock.now(),
                "preview",
            )
            uow.catalog.add_publication_batch(batch)
            for revision_id in normalized_ids:
                revision = uow.reviews.get_revision(revision_id)
                status = "blocked"
                reasons: tuple[str, ...]
                projection_id: str | None = None
                if revision is None:
                    reasons = ("REVISION_NOT_FOUND",)
                elif (
                    revision.place_id
                    and (place := uow.catalog.get_place(revision.place_id)) is not None
                    and place.city_id != city_id
                ):
                    reasons = ("REVISION_CITY_MISMATCH",)
                else:
                    projection = uow.catalog.get_projection_for_revision(revision_id)
                    projection_id = projection.projection_id if projection else None
                    if projection is None:
                        reasons = ("PROJECTION_NOT_FOUND",)
                    else:
                        context = uow.catalog.load_publication_context(projection.projection_id)
                        reasons = (
                            ("PROJECTION_DEPENDENCY_MISSING",)
                            if context is None
                            else evaluate_projection_publication(context)
                        )
                        status = "publishable" if not reasons else "blocked"
                uow.catalog.add_publication_batch_item(
                    PublicationBatchItem(
                        self._ids.new_id("publication_batch_item"),
                        batch.batch_id,
                        revision_id,
                        status,
                        tuple(reasons),
                        projection_id,
                    )
                )
            uow.audits.add(
                self._event(
                    actor,
                    action="PUBLICATION_BATCH_PREVIEWED",
                    target_type="publication_batch",
                    target_id=batch.batch_id,
                    target_revision=None,
                    before_digest=None,
                    after_digest=_digest(
                        {"batch_id": batch.batch_id, "revision_ids": normalized_ids}
                    ),
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=operation_digest,
                )
            )
            uow.commit()
            return self._publication_batch_response(uow, batch)

    def execute_publication_batch(
        self,
        principal: AdminPrincipal,
        *,
        batch_id: str,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> dict[str, object]:
        self._require(principal, "place:publication:write")
        reason_text = self._validate_reason(reason_code, reason_text)
        with self._uow_factory() as uow:
            batch = uow.catalog.get_publication_batch(batch_id)
            if batch is None:
                raise ResourceNotFoundError
            items = uow.catalog.list_publication_batch_items(batch_id)
            if batch.snapshot_id:
                snapshot = uow.catalog.get_research_snapshot(batch.snapshot_id)
                return {
                    "batch": self._publication_batch_response(uow, batch),
                    "snapshot": _snapshot_response(snapshot),
                    "reused": True,
                }
            operation_digest = _digest(
                {
                    "batch_id": batch_id,
                    "item_ids": tuple(item.batch_item_id for item in items),
                    "reason_code": reason_code,
                    "reason_text": reason_text,
                }
            )
            existing = uow.audits.get_by_operation_intent(operation_intent_id)
            if existing is not None:
                if existing.operation_digest != operation_digest:
                    raise AdminOperationIntentConflictError
                if batch.snapshot_id:
                    snapshot = uow.catalog.get_research_snapshot(batch.snapshot_id)
                    if snapshot is not None:
                        return {
                            "batch": self._publication_batch_response(uow, batch),
                            "snapshot": _snapshot_response(snapshot),
                            "reused": True,
                        }
                return {
                    "batch": self._publication_batch_response(uow, batch),
                    "snapshot": None,
                    "reused": True,
                }
            actor = self._actor(uow, principal)
            published: list[SolverPlaceProjection] = []
            for item in items:
                if item.status not in {"publishable", "pending"}:
                    continue
                revision = uow.reviews.get_revision(item.place_revision_id)
                projection = uow.catalog.get_projection_for_revision(item.place_revision_id)
                if revision is None or projection is None:
                    updated = replace(item, status="failed", reason_codes=("PROJECTION_NOT_FOUND",))
                    uow.catalog.update_publication_batch_item(updated)
                    continue
                context = uow.catalog.load_publication_context(projection.projection_id)
                reasons = (
                    ("PROJECTION_DEPENDENCY_MISSING",)
                    if context is None
                    else evaluate_projection_publication(context)
                )
                if reasons:
                    uow.catalog.update_publication_batch_item(
                        replace(
                            item,
                            status="blocked",
                            reason_codes=reasons,
                            projection_id=projection.projection_id,
                        )
                    )
                    continue
                try:
                    result = uow.catalog.publish_projection(
                        projection.projection_id, published_at=self._clock.now()
                    )
                except ProjectionPublicationError as exc:
                    uow.catalog.update_publication_batch_item(
                        replace(
                            item,
                            status="failed",
                            reason_codes=exc.reason_codes,
                            projection_id=projection.projection_id,
                        )
                    )
                    continue
                uow.catalog.update_publication_batch_item(
                    replace(
                        item,
                        status="published",
                        reason_codes=(),
                        projection_id=result.projection_id,
                        published_at=result.published_at,
                    )
                )
                published.append(result)
            if published:
                payload = {
                    "schema_version": "research_snapshot.v1",
                    "city_id": batch.city_id,
                    "items": [
                        _projection_snapshot_payload(item)
                        for item in sorted(
                            published,
                            key=lambda value: (
                                value.place_id,
                                value.place_revision_id,
                                value.projection_id,
                            ),
                        )
                    ],
                }
                content_sha256 = _digest(payload)
                snapshot = ResearchSnapshot(
                    self._ids.new_id("research_snapshot"),
                    f"research-{batch.city_id}-{content_sha256[:16]}",
                    batch.city_id,
                    content_sha256,
                    batch.batch_id,
                    payload,
                    self._clock.now(),
                    "published",
                )
                uow.catalog.add_research_snapshot(snapshot)
                batch = replace(
                    batch,
                    status="published"
                    if all(
                        item.status == "published"
                        for item in uow.catalog.list_publication_batch_items(batch_id)
                    )
                    else "partial_failed",
                    snapshot_id=snapshot.snapshot_id,
                )
            else:
                snapshot = None
                batch = replace(batch, status="failed")
            uow.catalog.update_publication_batch(batch)
            uow.audits.add(
                self._event(
                    actor,
                    action="PUBLICATION_BATCH_EXECUTED",
                    target_type="publication_batch",
                    target_id=batch.batch_id,
                    target_revision=None,
                    before_digest=None,
                    after_digest=_digest(
                        {"status": batch.status, "snapshot_id": batch.snapshot_id}
                    ),
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=operation_digest,
                )
            )
            uow.commit()
            return {
                "batch": self._publication_batch_response(uow, batch),
                "snapshot": _snapshot_response(snapshot) if snapshot else None,
                "reused": False,
            }

    def list_research_snapshots(
        self, principal: AdminPrincipal, *, city_id: str | None, limit: int, offset: int
    ) -> tuple[ResearchSnapshot, ...]:
        self._require(principal, "place:candidate:read")
        with self._uow_factory() as uow:
            return uow.catalog.list_research_snapshots(city_id=city_id, limit=limit, offset=offset)

    def get_research_snapshot(
        self, principal: AdminPrincipal, *, snapshot_id: str
    ) -> ResearchSnapshot:
        self._require(principal, "place:candidate:read")
        with self._uow_factory() as uow:
            snapshot = uow.catalog.get_research_snapshot(snapshot_id)
            if snapshot is None:
                raise ResourceNotFoundError
            return snapshot

    @staticmethod
    def _publication_batch_response(
        uow: ReviewUnitOfWork, batch: PublicationBatch
    ) -> dict[str, object]:
        items = uow.catalog.list_publication_batch_items(batch.batch_id)
        return {
            "batch_id": batch.batch_id,
            "city_id": batch.city_id,
            "operation_intent_id": batch.operation_intent_id,
            "status": batch.status,
            "snapshot_id": batch.snapshot_id,
            "created_at": batch.created_at.isoformat(),
            "items": [
                _batch_item_response(item, uow.reviews.get_revision(item.place_revision_id))
                for item in items
            ],
        }

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


# Backward-compatible private name for existing callers while offline research
# reporting adopts the explicit public evaluator.
_review_readiness = evaluate_review_readiness


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


def _projection_snapshot_payload(projection: SolverPlaceProjection) -> dict[str, object]:
    """Return only immutable projection inputs for snapshot hashing."""
    return {
        "projection_id": projection.projection_id,
        "projection_version": projection.projection_version,
        "data_snapshot_version": projection.data_snapshot_version,
        "place_id": projection.place_id,
        "place_revision_id": projection.place_revision_id,
        "solver_node_id": projection.solver_node_id,
        "place_kind": projection.place_kind,
        "geometry_kind": projection.geometry_kind,
        "arrival_access_point_id": projection.arrival_access_point_id,
        "departure_access_point_id": projection.departure_access_point_id,
        "duration_min": projection.duration_min,
        "duration_recommended": projection.duration_recommended,
        "duration_max": projection.duration_max,
        "internal_travel_min": projection.internal_travel_min,
        "solver_payload": projection.solver_payload,
        "projection_hash": projection.projection_hash,
    }


def _batch_item_response(
    item: PublicationBatchItem, revision: PlaceRevision | None = None
) -> dict[str, object]:
    response: dict[str, object] = {
        "batch_item_id": item.batch_item_id,
        "place_revision_id": item.place_revision_id,
        "status": item.status,
        "reason_codes": list(item.reason_codes),
        "projection_id": item.projection_id,
        "published_at": item.published_at.isoformat() if item.published_at else None,
    }
    if revision is not None:
        response.update(
            {
                "canonical_name": revision.canonical_name,
                "admin_area": revision.admin_area,
                "place_kind": revision.place_kind,
                "category": revision.category,
                "revision_number": revision.revision_number,
            }
        )
    return response


def _snapshot_response(snapshot: ResearchSnapshot | None) -> dict[str, object] | None:
    if snapshot is None:
        return None
    return {
        "snapshot_id": snapshot.snapshot_id,
        "data_snapshot_version": snapshot.data_snapshot_version,
        "city_id": snapshot.city_id,
        "content_sha256": snapshot.content_sha256,
        "source_batch_id": snapshot.source_batch_id,
        "created_at": snapshot.created_at.isoformat(),
        "status": snapshot.status,
        "payload": snapshot.snapshot_payload,
    }
