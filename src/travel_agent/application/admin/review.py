"""Application use cases for candidate place-revision review."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal

from travel_agent.application.common.clock import Clock
from travel_agent.application.common.errors import ResourceNotFoundError
from travel_agent.application.planning.ports import IdGenerator
from travel_agent.domain.admin import AdminPrincipal
from travel_agent.domain.place_catalog import (
    HolidayCalendar,
    PlaceReviewDecision,
    PlaceReviewTask,
    PlaceRevision,
    PlaceRevisionEvidence,
    PublicationBatchItem,
    ResearchSnapshot,
    SolverPlaceProjection,
)

from .audit_events import (
    review_flow_role,
)
from .review_evidence import EvidenceMutationSupport
from .review_geometry import ReviewGeometryService
from .review_ports import ActorRepository as ActorRepository
from .review_ports import AuditRepository as AuditRepository
from .review_ports import ReviewRepository as ReviewRepository
from .review_ports import ReviewUnitOfWork as ReviewUnitOfWork
from .review_publication import PublicationService
from .review_readiness import evaluate_review_readiness as evaluate_review_readiness
from .review_relations import ReviewRelationService
from .review_revision import RevisionLifecycleService
from .review_sources import ReviewSourceService
from .review_support import _digest
from .review_tasks import ReviewTaskService
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
        self._tasks = ReviewTaskService(uow_factory, clock, ids)
        self._publication = PublicationService(uow_factory, clock, ids)
        self._revisions = RevisionLifecycleService(uow_factory, clock, ids)

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
        return self._tasks.list_tasks(
            principal,
            status=status,
            limit=limit,
            offset=offset,
            keyword=keyword,
            admin_area=admin_area,
            place_kind=place_kind,
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
        return self._tasks.count_tasks(
            principal,
            status=status,
            keyword=keyword,
            admin_area=admin_area,
            place_kind=place_kind,
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
        return self._revisions.review_evidence(
            principal,
            revision_id=revision_id,
            evidence_kind=evidence_kind,
            evidence_id=evidence_id,
            review_status=review_status,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
        )

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
        return self._revisions.create_revision(
            principal,
            place_id=place_id,
            base_revision_id=base_revision_id,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
        )

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
        return self._revisions.update_revision(
            principal,
            revision_id=revision_id,
            expected_revision_number=expected_revision_number,
            changes=changes,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
        )

    def publication_check(self, principal: AdminPrincipal, *, revision_id: str) -> tuple[str, ...]:
        return self._publication.publication_check(
            principal,
            revision_id=revision_id,
        )

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
        return self._publication.prepare_projection(
            principal,
            revision_id=revision_id,
            data_snapshot_version=data_snapshot_version,
            solver_node_id=solver_node_id,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
        )

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
        return self._publication.publish_revision(
            principal,
            revision_id=revision_id,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
        )

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
        return self._publication.preview_publication_batch(
            principal,
            city_id=city_id,
            revision_ids=revision_ids,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
        )

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
        return self._publication.execute_publication_batch(
            principal,
            batch_id=batch_id,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
        )

    def list_research_snapshots(
        self, principal: AdminPrincipal, *, city_id: str | None, limit: int, offset: int
    ) -> tuple[ResearchSnapshot, ...]:
        return self._publication.list_research_snapshots(
            principal,
            city_id=city_id,
            limit=limit,
            offset=offset,
        )

    def get_research_snapshot(
        self, principal: AdminPrincipal, *, snapshot_id: str
    ) -> ResearchSnapshot:
        return self._publication.get_research_snapshot(
            principal,
            snapshot_id=snapshot_id,
        )

    def list_decisions(
        self, principal: AdminPrincipal, *, task_id: str
    ) -> tuple[PlaceReviewDecision, ...]:
        return self._tasks.list_decisions(
            principal,
            task_id=task_id,
        )

    def get_task(self, principal: AdminPrincipal, *, task_id: str) -> PlaceReviewTask:
        return self._tasks.get_task(
            principal,
            task_id=task_id,
        )

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
        return self._tasks.submit(
            principal,
            place_revision_id=place_revision_id,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
        )

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
        return self._tasks.decide(
            principal,
            task_id=task_id,
            operation_intent_id=operation_intent_id,
            expected_version=expected_version,
            decision_kind=decision_kind,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
        )

    def decide_batch(
        self, principal: AdminPrincipal, *, items: tuple[dict[str, object], ...], request_id: str
    ) -> dict[str, object]:
        return self._tasks.decide_batch(
            principal,
            items=items,
            request_id=request_id,
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
