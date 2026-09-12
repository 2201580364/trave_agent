from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from travel_agent.application.admin.errors import AdminPermissionDeniedError
from travel_agent.application.admin.holiday_calendar_sync import ChinaHolidayCalendarSyncService
from travel_agent.domain.admin import AdminPrincipal

from .admin import (
    ConfirmHolidayCalendarPreviewInput,
    CreateHolidayCalendarSyncJobInput,
    _holiday_calendar_version_response,
    _holiday_sync_job_response,
)


def register_o17_routes(
    router: APIRouter,
    holiday_calendar_sync: ChinaHolidayCalendarSyncService | None,
    principal_dependency: Depends,
) -> None:
    if holiday_calendar_sync is None:
        return

    @router.get("/holiday-calendar-sync-capability")
    def get_holiday_calendar_sync_capability(
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        if not current.has_permission("holiday:calendar:read"):
            raise AdminPermissionDeniedError
        return {
            "execution_available": holiday_calendar_sync.execution_available,
            "region_code": "CN",
        }

    @router.post("/holiday-calendar-sync-jobs", status_code=status.HTTP_202_ACCEPTED)
    def create_holiday_calendar_sync_job(
        payload: CreateHolidayCalendarSyncJobInput,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        if not current.has_permission("holiday:calendar:write"):
            raise AdminPermissionDeniedError
        if not holiday_calendar_sync.job_submission_available:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "节假日历自动同步执行服务尚未启用",
            )
        job = holiday_calendar_sync.create_job(
            year=payload.year,
            mode=payload.mode,
            operation_intent_id=payload.operation_intent_id,
            created_by=current.admin_actor_id,
        )
        return _holiday_sync_job_response(job)

    @router.get("/holiday-calendar-sync-jobs")
    def list_holiday_calendar_sync_jobs(
        year: int | None = Query(default=None, ge=2000, le=2200),
        job_status: str | None = Query(default=None, alias="status", max_length=32),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        if not current.has_permission("holiday:calendar:read"):
            raise AdminPermissionDeniedError
        jobs = holiday_calendar_sync.list_jobs(
            year=year, status=job_status, limit=limit, offset=offset
        )
        return {
            "items": [_holiday_sync_job_response(job) for job in jobs],
            "limit": limit,
            "offset": offset,
        }

    @router.get("/holiday-calendar-sync-jobs/{job_id}")
    def get_holiday_calendar_sync_job(
        job_id: str,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        if not current.has_permission("holiday:calendar:read"):
            raise AdminPermissionDeniedError
        return _holiday_sync_job_response(holiday_calendar_sync.get_job(job_id))

    @router.post("/holiday-calendar-sync-jobs/{job_id}/cancel")
    def cancel_holiday_calendar_sync_job(
        job_id: str,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        if not current.has_permission("holiday:calendar:write"):
            raise AdminPermissionDeniedError
        return _holiday_sync_job_response(
            holiday_calendar_sync.cancel_job(job_id, cancelled_by=current.admin_actor_id)
        )

    @router.post("/holiday-calendar-sync-jobs/{job_id}/confirm")
    def confirm_holiday_calendar_preview(
        job_id: str,
        payload: ConfirmHolidayCalendarPreviewInput,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        if not current.has_permission("holiday:calendar:write"):
            raise AdminPermissionDeniedError
        return _holiday_sync_job_response(
            holiday_calendar_sync.confirm_preview(
                job_id=job_id,
                periods=[item.model_dump(mode="json") for item in payload.periods],
                adjusted_workdays=[
                    item.model_dump(mode="json") for item in payload.adjusted_workdays
                ],
                operation_intent_id=payload.operation_intent_id,
                confirmed_by=current.admin_actor_id,
            )
        )

    @router.get("/holiday-calendars/{calendar_id}")
    def get_holiday_calendar_detail(
        calendar_id: str,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        if not current.has_permission("holiday:calendar:read"):
            raise AdminPermissionDeniedError
        return _holiday_calendar_version_response(holiday_calendar_sync.get_calendar(calendar_id))

    @router.get("/holiday-calendars/{calendar_id}/impact")
    def get_holiday_calendar_impact(
        calendar_id: str,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        if not current.has_permission("holiday:calendar:read"):
            raise AdminPermissionDeniedError
        impact = holiday_calendar_sync.get_calendar_impact(calendar_id)
        return {
            "calendar_id": impact.calendar_id,
            "compared_calendar_id": impact.compared_calendar_id,
            "changed_date_count": impact.changed_date_count,
            "added_holiday_dates": [item.isoformat() for item in impact.added_holiday_dates],
            "removed_holiday_dates": [item.isoformat() for item in impact.removed_holiday_dates],
            "added_adjusted_workdays": [
                item.isoformat() for item in impact.added_adjusted_workdays
            ],
            "removed_adjusted_workdays": [
                item.isoformat() for item in impact.removed_adjusted_workdays
            ],
            "affected_places": [
                {
                    "place_revision_id": item[0],
                    "place_name": item[1],
                    "admin_area": item[2],
                    "materialized_exception_count": item[3],
                }
                for item in impact.affected_places
            ],
            "historical_rows_without_provenance_excluded": True,
        }
