"""Time evidence and calendar review use cases (H3/S7-1, O05)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import date
from typing import Protocol

from travel_agent.application.common.clock import Clock
from travel_agent.application.common.errors import ResourceNotFoundError
from travel_agent.application.planning.ports import IdGenerator
from travel_agent.domain.admin import AdminPrincipal
from travel_agent.domain.place_catalog import (
    HolidayCalendar,
    PlaceClosure,
    PlaceDateException,
    PlaceRevision,
    PlaceTimeRule,
    resolve_holiday_closure_conflicts,
)
from travel_agent.domain.place_catalog.holiday_calendar import (
    get_holiday_calendar,
    list_holiday_calendars,
)

from .errors import (
    SourceRecordValidationError,
)
from .review_evidence import EvidenceMutationSupport
from .review_ports import TimeReviewUnitOfWork as ReviewUnitOfWork
from .review_time_preview import ReviewTimePreviewService


class HolidayCalendarCatalog(Protocol):
    def list_calendars(self) -> tuple[HolidayCalendar, ...]: ...
    def get_calendar(self, calendar_id: str) -> HolidayCalendar: ...


class BuiltinHolidayCalendarCatalog:
    def list_calendars(self) -> tuple[HolidayCalendar, ...]:
        return list_holiday_calendars()

    def get_calendar(self, calendar_id: str) -> HolidayCalendar:
        return get_holiday_calendar(calendar_id)


class ReviewTimeService(EvidenceMutationSupport[ReviewUnitOfWork]):
    def __init__(
        self,
        uow_factory: Callable[[], ReviewUnitOfWork],
        clock: Clock,
        ids: IdGenerator,
        holiday_calendars: HolidayCalendarCatalog,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._ids = ids
        self._holiday_calendars = holiday_calendars
        self._preview = ReviewTimePreviewService(uow_factory, holiday_calendars)

    def list_holiday_calendars(self, principal: AdminPrincipal) -> tuple[HolidayCalendar, ...]:
        self._require(principal, "place:candidate:read")
        return self._holiday_calendars.list_calendars()

    def preview_time(
        self, principal: AdminPrincipal, *, revision_id: str, service_date: date
    ) -> dict[str, object]:
        return self._preview.preview_time(
            principal, revision_id=revision_id, service_date=service_date
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
        """Delete candidate time evidence with versioning and atomic audit (H3/C2)."""

        def mutate(uow: ReviewUnitOfWork, _revision: PlaceRevision) -> tuple[PlaceRevision, str]:
            return (
                uow.catalog.delete_time_rule(
                    time_rule_id,
                    place_revision_id=revision_id,
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
            action="PLACE_TIME_RULE_DELETED",
            target_id=time_rule_id,
            payload={
                "revision_id": revision_id,
                "time_rule_id": time_rule_id,
                "expected_revision_version": expected_revision_version,
                "operation": "delete",
            },
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

        def mutate(uow: ReviewUnitOfWork, _revision: PlaceRevision) -> tuple[PlaceRevision, str]:
            evidence = uow.catalog.load_revision_evidence(revision_id)
            if evidence is None:
                raise ResourceNotFoundError
            if any(
                item.active and item.service_date == service_date
                for item in evidence.date_exceptions
            ):
                raise ValueError(
                    "该日期已存在有效日期例外；同一天只能保留一条例外，请编辑或停用原记录"
                )
            return (
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
            )

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
            mutate=mutate,
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
        """Materialize a verified holiday policy as auditable date exceptions.

        Date exceptions remain the solver contract.  This operation only
        expands a versioned calendar into candidate evidence; every generated
        row must still be reviewed before the Revision can be approved.
        """
        calendar = self._holiday_calendars.get_calendar(calendar_id)
        # The annual calendar carries its own official provenance. Older
        # clients may omit it; resolve it server-side to keep the operation
        # compatible while preserving mandatory place sources elsewhere.
        source_record_id = source_record_id or getattr(calendar, "source_record_id", None) or ""
        if not source_record_id:
            raise ValueError("该年度法定节假日历缺少官方来源记录，请重新同步并发布日历")
        if open_end_minute <= open_start_minute:
            raise ValueError("holiday opening end must be after opening start")
        payload = {
            "revision_id": revision_id,
            "expected_revision_version": expected_revision_version,
            "calendar_id": calendar_id,
            "source_record_id": source_record_id,
            "open_start_minute": open_start_minute,
            "open_end_minute": open_end_minute,
            "open_last_entry_minute": open_last_entry_minute,
            "shift_closure": shift_closure,
        }

        def mutate(uow: ReviewUnitOfWork, revision: PlaceRevision) -> tuple[PlaceRevision, str]:
            evidence = uow.catalog.load_revision_evidence(revision_id)
            if evidence is None:
                raise ResourceNotFoundError
            source = next(
                (
                    item
                    for item in evidence.source_records
                    if item.source_record_id == source_record_id
                ),
                None,
            )
            calendar_source = getattr(calendar, "source_record_id", None) == source_record_id
            if (source is None or source.status != "active") and not calendar_source:
                raise SourceRecordValidationError(
                    "holiday calendar requires an active source record"
                )
            closure_weekdays = {item.weekday for item in evidence.closures if item.active}
            if not closure_weekdays:
                raise ValueError("请先维护固定闭馆日，再生成节假日开放和顺延闭馆例外")
            holiday_dates, shifted_dates = resolve_holiday_closure_conflicts(
                calendar, frozenset(closure_weekdays), shift_closure=shift_closure
            )
            existing_dates = {item.service_date for item in evidence.date_exceptions if item.active}
            current = revision
            generated: list[str] = []
            offset = 0
            values = [
                *(
                    (
                        day,
                        "open_override",
                        open_start_minute,
                        open_end_minute,
                        open_last_entry_minute,
                    )
                    for day in sorted(holiday_dates)
                ),
                *((day, "closed", None, None, None) for day in sorted(shifted_dates)),
            ]
            for service_date, kind, start, end, last_entry in values:
                # An explicit manual exception has higher authority than the
                # generated annual policy, regardless of its kind.
                if service_date in existing_dates:
                    continue
                exception_id = self._ids.new_id("date_exception")
                current = uow.catalog.create_date_exception(
                    PlaceDateException(
                        exception_id,
                        revision_id,
                        service_date,
                        kind,
                        start,
                        end,
                        last_entry,
                        source_record_id,
                        "candidate",
                        True,
                        self._clock.now(),
                        holiday_calendar_id=calendar_id,
                    ),
                    expected_revision_version=expected_revision_version + offset,
                )
                generated.append(exception_id)
                offset += 1
            payload["generated_exception_ids"] = generated
            return current, generated[0] if generated else revision_id

        return self._mutate_evidence(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
            action="PLACE_HOLIDAY_EXCEPTIONS_GENERATED",
            target_id=revision_id,
            payload=payload,
            mutate=mutate,
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
            if any(
                item.active
                and item.date_exception_id != date_exception_id
                and item.service_date == service_date
                for item in evidence.date_exceptions
            ):
                raise ValueError("该日期已存在其他有效日期例外；同一天只能保留一条例外")
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
