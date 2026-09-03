"""Independent administrator authentication and RBAC HTTP boundary."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    status,
)
from pydantic import BaseModel, ConfigDict, Field

from travel_agent.application.admin import (
    AdminAuthenticationError,
    AdminIdentityService,
    PlaceReviewWorkflowService,
)
from travel_agent.application.admin.errors import AdminPermissionDeniedError
from travel_agent.application.admin.holiday_calendar_sync import (
    ChinaHolidayCalendarSyncService,
)
from travel_agent.domain.admin import AdminActor, AdminAuditEvent, AdminPrincipal
from travel_agent.domain.place_catalog import (
    PlaceReviewDecision,
    PlaceReviewTask,
    PlaceRevision,
    PlaceRevisionEvidence,
)
from travel_agent.domain.place_catalog.holiday_sync import (
    HolidayCalendarSyncJob,
    HolidayCalendarVersion,
)


class CreateAdminSessionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login_name: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=14, max_length=256)


class ReplaceAdminRolesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_intent_id: str = Field(min_length=1, max_length=64)
    expected_version: int = Field(gt=0)
    role_keys: tuple[str, ...] = Field(min_length=1, max_length=6)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)


class CreateAdminActorInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_intent_id: str = Field(min_length=1, max_length=64)
    login_name: str = Field(min_length=3, max_length=64)
    initial_password: str = Field(min_length=14, max_length=256)
    role_keys: tuple[str, ...] = Field(min_length=1, max_length=6)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)


class SubmitPlaceReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)


class DecidePlaceReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_intent_id: str = Field(min_length=1, max_length=64)
    expected_version: int = Field(gt=0)
    decision_kind: str = Field(pattern="^(approve|request_changes|cancel)$")
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)

class BatchDecidePlaceReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[DecidePlaceReviewInput, ...] = Field(min_length=1, max_length=100)


class CreatePlaceRevisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_revision_id: str = Field(min_length=1, max_length=64)
    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)


class UpdatePlaceRevisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision_number: int = Field(gt=0)
    expected_revision_version: int | None = Field(default=None, gt=0)
    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)
    canonical_name: str | None = Field(default=None, min_length=1, max_length=160)
    aliases: tuple[str, ...] | None = None
    place_kind: str | None = Field(default=None, min_length=1, max_length=32)
    category: str | None = Field(default=None, min_length=1, max_length=64)
    admin_area: str | None = Field(default=None, min_length=1, max_length=120)
    address: str | None = Field(default=None, max_length=300)
    geometry_kind: str | None = Field(default=None, min_length=1, max_length=20)
    duration_min: int | None = Field(default=None, ge=0)
    duration_recommended: int | None = Field(default=None, ge=1)
    duration_max: int | None = Field(default=None, ge=0)
    internal_travel_min: int | None = Field(default=None, ge=0)
    energy_level: int | None = Field(default=None, ge=0, le=5)
    indoor_outdoor: str | None = Field(default=None, min_length=1, max_length=20)
    suitable_periods: tuple[str, ...] | None = None
    audience_tags: tuple[str, ...] | None = None
    rain_suitability: str | None = Field(default=None, min_length=1, max_length=20)
    is_always_open: bool | None = None


class PublishPlaceRevisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)


class PreviewPublicationBatchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city_id: str = Field(min_length=1, max_length=64)
    place_revision_ids: tuple[str, ...] = Field(min_length=1, max_length=500)
    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)


class ExecutePublicationBatchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)


class PrepareProjectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_snapshot_version: str = Field(min_length=1, max_length=80)
    solver_node_id: int | None = Field(default=None, gt=0)
    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)


class CreatePlaceSourceRecordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision_version: int = Field(gt=0)
    source_id: str = Field(min_length=1, max_length=80)
    source_url: str = Field(min_length=8, max_length=2048)
    collection_mode: str = Field(
        pattern="^(api|dataset_download|manual_reference|public_page_fetch)$"
    )
    observed_at: datetime
    content_sha256: str | None = Field(default=None, pattern="^[0-9a-fA-F]{64}$")
    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)


class DetachPlaceSourceRecordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision_version: int = Field(gt=0)
    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)


class PlaceGeometryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision_version: int = Field(gt=0)
    geometry_kind: str = Field(min_length=1, max_length=20)
    geometry: dict[str, object]
    source_record_id: str = Field(min_length=1, max_length=64)
    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)


class PlaceAccessPointInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision_version: int = Field(gt=0)
    access_point_kind: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=160)
    lat: Decimal = Field(ge=Decimal("-90"), le=Decimal("90"))
    lng: Decimal = Field(ge=Decimal("-180"), le=Decimal("180"))
    source_record_id: str = Field(min_length=1, max_length=64)
    fetched_at: datetime | None = None
    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)


class PlaceTimeRuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision_version: int = Field(gt=0)
    rule_kind: str = Field(pattern="^(opening_hours|fixed_session|last_entry)$")
    weekdays: tuple[int, ...] = Field(min_length=1, max_length=7)
    start_minute: int | None = Field(default=None, ge=0, le=2880)
    end_minute: int | None = Field(default=None, ge=0, le=2880)
    last_entry_minute: int | None = Field(default=None, ge=0, le=2880)
    valid_from: date | None = None
    valid_to: date | None = None
    source_record_id: str = Field(min_length=1, max_length=64)
    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)


class PlaceClosureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision_version: int = Field(gt=0)
    weekday: int = Field(ge=1, le=7)
    source_record_id: str = Field(min_length=1, max_length=64)
    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)


class PlaceDateExceptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision_version: int = Field(gt=0)
    service_date: date
    exception_kind: str = Field(pattern="^(closed|open_override|session_override)$")
    start_minute: int | None = Field(default=None, ge=0, le=2880)
    end_minute: int | None = Field(default=None, ge=0, le=2880)
    last_entry_minute: int | None = Field(default=None, ge=0, le=2880)
    source_record_id: str = Field(min_length=1, max_length=64)
    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)

class GenerateHolidayExceptionsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision_version: int = Field(gt=0)
    calendar_id: str = Field(min_length=1, max_length=64)
    source_record_id: str = Field(default="", max_length=64)
    open_start_minute: int = Field(ge=0, le=2880)
    open_end_minute: int = Field(ge=0, le=2880)
    open_last_entry_minute: int | None = Field(default=None, ge=0, le=2880)
    shift_closure: bool = True
    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)

class ResolveSourceConflictsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision_number: int = Field(gt=0)
    expected_revision_version: int = Field(gt=0)
    resolved: bool
    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)

class ResolveRelationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision_version: int = Field(gt=0)
    resolution_status: str = Field(pattern="^(resolved|not_required|pending)$")
    decision_note: str | None = Field(default=None, max_length=500)
    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)

class ConfirmNoRelationsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision_number: int = Field(gt=0)
    expected_revision_version: int = Field(gt=0)
    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)


class RetirePlaceEvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision_version: int = Field(gt=0)
    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)

class ReviewPlaceEvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_intent_id: str = Field(min_length=1, max_length=64)
    review_status: str = Field(pattern="^(human_verified|rejected)$")
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)


class CreateHolidayCalendarSyncJobInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int = Field(ge=2000, le=2200)
    mode: str = Field(pattern="^(preview|sync)$")
    operation_intent_id: str = Field(min_length=1, max_length=64)


class HolidayCalendarPreviewPeriodInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=50)
    start: date
    end: date
    evidence_quote: str = Field(min_length=1, max_length=1000)


class HolidayCalendarPreviewWorkdayInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    holiday_name: str = Field(min_length=1, max_length=50)
    evidence_quote: str = Field(min_length=1, max_length=1000)


class ConfirmHolidayCalendarPreviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_intent_id: str = Field(min_length=1, max_length=64)
    periods: list[HolidayCalendarPreviewPeriodInput] = Field(
        min_length=1, max_length=30
    )
    adjusted_workdays: list[HolidayCalendarPreviewWorkdayInput] = Field(
        default_factory=list, max_length=100
    )


def build_admin_router(
    service: AdminIdentityService,
    review_workflow: PlaceReviewWorkflowService | None = None,
    holiday_calendar_sync: ChinaHolidayCalendarSyncService | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

    def principal(
        authorization: Annotated[str | None, Header()] = None,
    ) -> AdminPrincipal:
        if authorization is None or not authorization.startswith("Bearer "):
            raise AdminAuthenticationError
        token = authorization.removeprefix("Bearer ").strip()
        if not token:
            raise AdminAuthenticationError
        return service.authenticate(token)

    principal_dependency = Depends(principal)

    @router.post("/sessions", status_code=status.HTTP_201_CREATED)
    def create_session(
        payload: CreateAdminSessionInput,
        request: Request,
    ) -> dict[str, object]:
        created = service.create_session(
            payload.login_name,
            payload.password,
            request_id=request.state.request_id,
            client_ip=request.client.host if request.client is not None else None,
            user_agent=request.headers.get("User-Agent"),
        )
        return {
            "admin_actor_id": created.principal.admin_actor_id,
            "access_token": created.access_token,
            "expires_at": created.principal.expires_at.isoformat(),
            "role_keys": list(created.principal.role_keys),
            "permissions": list(created.principal.permissions),
        }

    @router.delete("/sessions/current", status_code=status.HTTP_204_NO_CONTENT)
    def revoke_current_session(
        request: Request,
        current: AdminPrincipal = principal_dependency,
    ) -> Response:
        service.revoke_current(current, request_id=request.state.request_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get("/me")
    def get_me(
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        return {
            "admin_actor_id": current.admin_actor_id,
            "login_name": current.login_name,
            "role_keys": list(current.role_keys),
            "permissions": list(current.permissions),
            "expires_at": current.expires_at.isoformat(),
        }

    if holiday_calendar_sync is not None:

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

        @router.post(
            "/holiday-calendar-sync-jobs", status_code=status.HTTP_202_ACCEPTED
        )
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
                        item.model_dump(mode="json")
                        for item in payload.adjusted_workdays
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
            return _holiday_calendar_version_response(
                holiday_calendar_sync.get_calendar(calendar_id)
            )

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
                "removed_holiday_dates": [
                    item.isoformat() for item in impact.removed_holiday_dates
                ],
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

    @router.get("/admin-actors")
    def list_admin_actors(
        current: AdminPrincipal = principal_dependency,
        keyword: str | None = Query(default=None, max_length=100),
        actor_status: str | None = Query(
            default=None, pattern="^(active|disabled|locked)$"
        ),
        role_key: str | None = Query(default=None, max_length=64),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> dict[str, object]:
        actors = service.list_actors(
            current,
            keyword=keyword,
            status=actor_status,
            role_key=role_key,
            limit=limit,
            offset=offset,
        )
        return {
            "items": [_actor_response(actor) for actor in actors],
            "limit": limit,
            "offset": offset,
            "total": service.count_actors(
                current, keyword=keyword, status=actor_status, role_key=role_key
            ),
        }

    @router.post("/admin-actors", status_code=status.HTTP_201_CREATED)
    def create_admin_actor(
        payload: CreateAdminActorInput,
        request: Request,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        actor, reused = service.create_actor(
            current,
            login_name=payload.login_name,
            initial_password=payload.initial_password,
            role_keys=payload.role_keys,
            operation_intent_id=payload.operation_intent_id,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            request_id=request.state.request_id,
        )
        return {**_actor_response(actor), "reused": reused}

    @router.put("/admin-actors/{actor_id}/roles")
    def replace_admin_roles(
        actor_id: str,
        payload: ReplaceAdminRolesInput,
        request: Request,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        actor, reused = service.change_roles(
            current,
            actor_id,
            expected_version=payload.expected_version,
            role_keys=payload.role_keys,
            operation_intent_id=payload.operation_intent_id,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            request_id=request.state.request_id,
        )
        return {**_actor_response(actor), "reused": reused}

    @router.get("/audit-events")
    def list_audit_events(
        current: AdminPrincipal = principal_dependency,
        actor_id: str | None = Query(default=None, max_length=64),
        actor_login_name: str | None = Query(default=None, max_length=64),
        target_type: str | None = Query(default=None, max_length=64),
        target_id: str | None = Query(default=None, max_length=128),
        action: str | None = Query(default=None, max_length=80),
        result: str | None = Query(default=None, pattern="^(succeeded|rejected|failed)$"),
        keyword: str | None = Query(default=None, max_length=100),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> dict[str, object]:
        events = service.list_audit_events(
            current,
            actor_id=actor_id,
            actor_login_name=actor_login_name,
            target_type=target_type,
            target_id=target_id,
            action=action,
            result=result,
            keyword=keyword,
            limit=limit,
            offset=offset,
        )
        actor_login_names = service.audit_actor_login_names(
            current,
            actor_ids=tuple(event.actor_id for event in events),
        )
        return {
            "items": [
                _audit_response(
                    event,
                    actor_login_name=actor_login_names.get(event.actor_id),
                )
                for event in events
            ],
            "limit": limit,
            "offset": offset,
            "total": service.count_audit_events(
                current,
                actor_id=actor_id,
                actor_login_name=actor_login_name,
                target_type=target_type,
                target_id=target_id,
                action=action,
                result=result,
                keyword=keyword,
            ),
        }

    if review_workflow is not None:

        @router.get("/source-channels")
        def list_place_source_channels(
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            return {
                "items": [
                    {
                        "source_id": channel.source_id,
                        "display_name": channel.display_name,
                        "source_kind": channel.source_kind,
                        "decision": channel.decision,
                        "collection_modes": list(channel.collection_modes),
                        "base_urls": list(channel.base_urls),
                        "conditions": list(channel.conditions),
                    }
                    for channel in review_workflow.list_source_channels(current)
                ]
            }

        @router.get("/holiday-calendars")
        def list_holiday_calendars_endpoint(
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            return {
                "items": [
                    {
                        "calendar_id": item.calendar_id,
                        "display_name": item.display_name,
                        "source_note": item.source_note,
                        "source_record_id": item.source_record_id,
                        "periods": [
                            {
                                "name": period.name,
                                "start": period.start.isoformat(),
                                "end": period.end.isoformat(),
                            }
                            for period in item.periods
                        ],
                    }
                    for item in review_workflow.list_holiday_calendars(current)
                ]
            }

        @router.post("/places/{place_id}/revisions", status_code=status.HTTP_201_CREATED)
        def create_place_revision(
            place_id: str,
            payload: CreatePlaceRevisionInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.create_revision(
                current,
                place_id=place_id,
                base_revision_id=payload.base_revision_id,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.patch("/place-revisions/{revision_id}")
        def update_place_revision(
            revision_id: str,
            payload: UpdatePlaceRevisionInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            changes = payload.model_dump(
                exclude={
                    "expected_revision_number",
                    "expected_revision_version",
                    "operation_intent_id",
                    "reason_code",
                    "reason_text",
                },
                exclude_unset=True,
            )
            revision = review_workflow.update_revision(
                current,
                revision_id=revision_id,
                expected_revision_number=payload.expected_revision_number,
                expected_revision_version=payload.expected_revision_version,
                changes=changes,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.get("/place-revisions/{revision_id}/publication-checks")
        def check_place_revision_publication(
            revision_id: str,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            reasons = review_workflow.publication_check(current, revision_id=revision_id)
            return {
                "revision_id": revision_id,
                "publishable": not reasons,
                "reason_codes": list(reasons),
            }

        @router.get("/place-revisions/{revision_id}/evidence")
        def get_place_revision_evidence(
            revision_id: str,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            evidence = review_workflow.get_revision_evidence(
                current, revision_id=revision_id
            )
            return _revision_evidence_response(evidence)

        @router.post(
            "/place-revisions/{revision_id}/source-records",
            status_code=status.HTTP_201_CREATED,
        )
        def create_place_source_record(
            revision_id: str,
            payload: CreatePlaceSourceRecordInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.create_source_record(
                current,
                revision_id=revision_id,
                expected_revision_version=payload.expected_revision_version,
                source_id=payload.source_id,
                source_url=payload.source_url,
                collection_mode=payload.collection_mode,
                observed_at=payload.observed_at,
                content_sha256=payload.content_sha256,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.delete(
            "/place-revisions/{revision_id}/source-records/{source_record_id}"
        )
        def detach_place_source_record(
            revision_id: str,
            source_record_id: str,
            payload: DetachPlaceSourceRecordInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.detach_source_record(
                current,
                revision_id=revision_id,
                source_record_id=source_record_id,
                expected_revision_version=payload.expected_revision_version,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.get("/place-revisions/{revision_id}/source-conflicts")
        def list_place_source_conflicts(
            revision_id: str,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            conflicts = review_workflow.list_source_conflicts(current, revision_id=revision_id)
            return {
                "revision_id": revision_id,
                "items": [
                    {
                        "source_id": item["source_id"],
                        "resolved": item["resolved"],
                        "records": [
                            {
                                "source_record_id": record.source_record_id,
                                "source_url": safe_source_url(record.source_url),
                                "source_decision": record.source_decision,
                                "status": record.status,
                                "observed_at": record.observed_at.isoformat(),
                            }
                            for record in item["records"]
                        ],
                    }
                    for item in conflicts
                ],
            }

        @router.post("/place-revisions/{revision_id}/source-conflicts/resolve")
        def resolve_place_source_conflicts(
            revision_id: str, payload: ResolveSourceConflictsInput, request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.resolve_source_conflicts(
                current, revision_id=revision_id,
                expected_revision_number=payload.expected_revision_number,
                expected_revision_version=payload.expected_revision_version,
                resolved=payload.resolved, operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code, reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.post("/place-revisions/{revision_id}/relations/{relation_id}/resolve")
        def resolve_place_relation(
            revision_id: str, relation_id: str, payload: ResolveRelationInput, request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.resolve_relation(
                current, revision_id=revision_id, relation_id=relation_id,
                expected_revision_version=payload.expected_revision_version,
                resolution_status=payload.resolution_status, decision_note=payload.decision_note,
                operation_intent_id=payload.operation_intent_id, reason_code=payload.reason_code,
                reason_text=payload.reason_text, request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.post("/place-revisions/{revision_id}/relations/confirm-none")
        def confirm_no_place_relations(
            revision_id: str, payload: ConfirmNoRelationsInput, request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.confirm_no_relations(
                current, revision_id=revision_id,
                expected_revision_number=payload.expected_revision_number,
                expected_revision_version=payload.expected_revision_version,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code, reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.get("/place-revisions/{revision_id}/time-preview")
        def preview_place_revision_time(
            revision_id: str,
            service_date: date = Query(...),
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            return review_workflow.preview_time(
                current, revision_id=revision_id, service_date=service_date
            )

        @router.post("/place-revisions/{revision_id}/evidence/{evidence_kind}/{evidence_id}/review")
        def review_place_evidence(
            revision_id: str,
            evidence_kind: Annotated[
                str,
                Path(
                    pattern=(
                        "^(geometry|access_point|time_rule|closure|date_exception|relation)$"
                    )
                ),
            ],
            evidence_id: str,
            payload: ReviewPlaceEvidenceInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.review_evidence(
                current, revision_id=revision_id, evidence_kind=evidence_kind,
                evidence_id=evidence_id, review_status=payload.review_status,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code, reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.post("/place-revisions/{revision_id}/geometries")
        def create_place_geometry(
            revision_id: str,
            payload: PlaceGeometryInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.create_geometry(
                current,
                revision_id=revision_id,
                expected_revision_version=payload.expected_revision_version,
                geometry_kind=payload.geometry_kind,
                geometry=payload.geometry,
                source_record_id=payload.source_record_id,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.patch("/place-revisions/{revision_id}/geometries/{geometry_id}")
        def update_place_geometry(
            revision_id: str,
            geometry_id: str,
            payload: PlaceGeometryInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.update_geometry(
                current,
                revision_id=revision_id,
                geometry_id=geometry_id,
                expected_revision_version=payload.expected_revision_version,
                geometry_kind=payload.geometry_kind,
                geometry=payload.geometry,
                source_record_id=payload.source_record_id,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.delete("/place-revisions/{revision_id}/geometries/{geometry_id}")
        def retire_place_geometry(
            revision_id: str,
            geometry_id: str,
            payload: RetirePlaceEvidenceInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.retire_geometry(
                current,
                revision_id=revision_id,
                geometry_id=geometry_id,
                expected_revision_version=payload.expected_revision_version,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.post("/place-revisions/{revision_id}/access-points")
        def create_place_access_point(
            revision_id: str,
            payload: PlaceAccessPointInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.create_access_point(
                current,
                revision_id=revision_id,
                expected_revision_version=payload.expected_revision_version,
                access_point_kind=payload.access_point_kind,
                name=payload.name,
                lat=payload.lat,
                lng=payload.lng,
                source_record_id=payload.source_record_id,
                fetched_at=payload.fetched_at,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.patch("/place-revisions/{revision_id}/access-points/{access_point_id}")
        def update_place_access_point(
            revision_id: str,
            access_point_id: str,
            payload: PlaceAccessPointInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.update_access_point(
                current,
                revision_id=revision_id,
                access_point_id=access_point_id,
                expected_revision_version=payload.expected_revision_version,
                access_point_kind=payload.access_point_kind,
                name=payload.name,
                lat=payload.lat,
                lng=payload.lng,
                source_record_id=payload.source_record_id,
                fetched_at=payload.fetched_at,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.delete(
            "/place-revisions/{revision_id}/access-points/{access_point_id}"
        )
        def retire_place_access_point(
            revision_id: str,
            access_point_id: str,
            payload: RetirePlaceEvidenceInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.retire_access_point(
                current,
                revision_id=revision_id,
                access_point_id=access_point_id,
                expected_revision_version=payload.expected_revision_version,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.post("/place-revisions/{revision_id}/time-rules")
        def create_place_time_rule(
            revision_id: str,
            payload: PlaceTimeRuleInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.create_time_rule(
                current,
                revision_id=revision_id,
                expected_revision_version=payload.expected_revision_version,
                rule_kind=payload.rule_kind,
                weekdays=payload.weekdays,
                start_minute=payload.start_minute,
                end_minute=payload.end_minute,
                last_entry_minute=payload.last_entry_minute,
                valid_from=payload.valid_from,
                valid_to=payload.valid_to,
                source_record_id=payload.source_record_id,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.patch("/place-revisions/{revision_id}/time-rules/{time_rule_id}")
        def update_place_time_rule(
            revision_id: str,
            time_rule_id: str,
            payload: PlaceTimeRuleInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.update_time_rule(
                current,
                revision_id=revision_id,
                time_rule_id=time_rule_id,
                expected_revision_version=payload.expected_revision_version,
                rule_kind=payload.rule_kind,
                weekdays=payload.weekdays,
                start_minute=payload.start_minute,
                end_minute=payload.end_minute,
                last_entry_minute=payload.last_entry_minute,
                valid_from=payload.valid_from,
                valid_to=payload.valid_to,
                source_record_id=payload.source_record_id,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.delete("/place-revisions/{revision_id}/time-rules/{time_rule_id}")
        def retire_place_time_rule(
            revision_id: str,
            time_rule_id: str,
            payload: RetirePlaceEvidenceInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.retire_time_rule(
                current,
                revision_id=revision_id,
                time_rule_id=time_rule_id,
                expected_revision_version=payload.expected_revision_version,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.post("/place-revisions/{revision_id}/closures")
        def create_place_closure(
            revision_id: str,
            payload: PlaceClosureInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.create_closure(
                current,
                revision_id=revision_id,
                expected_revision_version=payload.expected_revision_version,
                weekday=payload.weekday,
                source_record_id=payload.source_record_id,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.post("/place-revisions/{revision_id}/holiday-exceptions")
        def generate_holiday_exceptions(
            revision_id: str,
            payload: GenerateHolidayExceptionsInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.generate_holiday_exceptions(
                current, revision_id=revision_id,
                expected_revision_version=payload.expected_revision_version,
                calendar_id=payload.calendar_id, source_record_id=payload.source_record_id,
                open_start_minute=payload.open_start_minute, open_end_minute=payload.open_end_minute,
                open_last_entry_minute=payload.open_last_entry_minute, shift_closure=payload.shift_closure,
                operation_intent_id=payload.operation_intent_id, reason_code=payload.reason_code,
                reason_text=payload.reason_text, request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.patch("/place-revisions/{revision_id}/closures/{closure_id}")
        def update_place_closure(
            revision_id: str,
            closure_id: str,
            payload: PlaceClosureInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.update_closure(
                current,
                revision_id=revision_id,
                closure_id=closure_id,
                expected_revision_version=payload.expected_revision_version,
                weekday=payload.weekday,
                source_record_id=payload.source_record_id,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.delete("/place-revisions/{revision_id}/closures/{closure_id}")
        def retire_place_closure(
            revision_id: str,
            closure_id: str,
            payload: RetirePlaceEvidenceInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.retire_closure(
                current,
                revision_id=revision_id,
                closure_id=closure_id,
                expected_revision_version=payload.expected_revision_version,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.post("/place-revisions/{revision_id}/date-exceptions")
        def create_place_date_exception(
            revision_id: str,
            payload: PlaceDateExceptionInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.create_date_exception(
                current,
                revision_id=revision_id,
                expected_revision_version=payload.expected_revision_version,
                service_date=payload.service_date,
                exception_kind=payload.exception_kind,
                start_minute=payload.start_minute,
                end_minute=payload.end_minute,
                last_entry_minute=payload.last_entry_minute,
                source_record_id=payload.source_record_id,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.patch(
            "/place-revisions/{revision_id}/date-exceptions/{date_exception_id}"
        )
        def update_place_date_exception(
            revision_id: str,
            date_exception_id: str,
            payload: PlaceDateExceptionInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.update_date_exception(
                current,
                revision_id=revision_id,
                date_exception_id=date_exception_id,
                expected_revision_version=payload.expected_revision_version,
                service_date=payload.service_date,
                exception_kind=payload.exception_kind,
                start_minute=payload.start_minute,
                end_minute=payload.end_minute,
                last_entry_minute=payload.last_entry_minute,
                source_record_id=payload.source_record_id,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.delete(
            "/place-revisions/{revision_id}/date-exceptions/{date_exception_id}"
        )
        def retire_place_date_exception(
            revision_id: str,
            date_exception_id: str,
            payload: RetirePlaceEvidenceInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.retire_date_exception(
                current,
                revision_id=revision_id,
                date_exception_id=date_exception_id,
                expected_revision_version=payload.expected_revision_version,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _revision_response(revision)

        @router.post("/place-revisions/{revision_id}/publications")
        def publish_place_revision(
            revision_id: str,
            payload: PublishPlaceRevisionInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            projection = review_workflow.publish_revision(
                current,
                revision_id=revision_id,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return {
                "projection_id": projection.projection_id,
                "place_revision_id": projection.place_revision_id,
                "data_snapshot_version": projection.data_snapshot_version,
                "status": projection.status,
                "published_at": (
                    projection.published_at.isoformat()
                    if projection.published_at
                    else None
                ),
            }

        @router.post("/place-revisions/{revision_id}/projection-preparations")
        def prepare_place_revision_projection(
            revision_id: str,
            payload: PrepareProjectionInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            projection = review_workflow.prepare_projection(
                current,
                revision_id=revision_id,
                data_snapshot_version=payload.data_snapshot_version,
                solver_node_id=payload.solver_node_id,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return {
                "projection_id": projection.projection_id,
                "place_revision_id": projection.place_revision_id,
                "status": projection.status,
                "projection_hash": projection.projection_hash,
                "gate_reason_codes": list(projection.gate_reason_codes),
            }

        @router.post("/publication-batches/previews", status_code=status.HTTP_201_CREATED)
        def preview_publication_batch(
            payload: PreviewPublicationBatchInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            return review_workflow.preview_publication_batch(
                current,
                city_id=payload.city_id,
                revision_ids=payload.place_revision_ids,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )

        @router.post("/publication-batches/{batch_id}/execute")
        def execute_publication_batch(
            batch_id: str,
            payload: ExecutePublicationBatchInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            return review_workflow.execute_publication_batch(
                current,
                batch_id=batch_id,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )

        @router.get("/research-snapshots")
        def list_research_snapshots(
            current: AdminPrincipal = principal_dependency,
            city_id: str | None = Query(default=None, max_length=64),
            limit: int = Query(default=50, ge=1, le=100),
            offset: int = Query(default=0, ge=0),
        ) -> dict[str, object]:
            snapshots = review_workflow.list_research_snapshots(current, city_id=city_id, limit=limit, offset=offset)
            return {"items": [_snapshot_api_response(item, include_payload=False) for item in snapshots], "limit": limit, "offset": offset}

        @router.get("/research-snapshots/{snapshot_id}")
        def get_research_snapshot(
            snapshot_id: str,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            return _snapshot_api_response(review_workflow.get_research_snapshot(current, snapshot_id=snapshot_id), include_payload=True)

        @router.get("/candidates")
        def list_candidates(
            current: AdminPrincipal = principal_dependency,
            lifecycle_status: str | None = Query(default="candidate", max_length=24),
            keyword: str | None = Query(default=None, max_length=100),
            admin_area: str | None = Query(default=None, max_length=120),
            place_kind: str | None = Query(default=None, max_length=32),
            limit: int = Query(default=50, ge=1, le=100),
            offset: int = Query(default=0, ge=0),
        ) -> dict[str, object]:
            revisions = review_workflow.list_revisions(
                current,
                lifecycle_status=lifecycle_status,
                keyword=keyword,
                admin_area=admin_area,
                place_kind=place_kind,
                limit=limit,
                offset=offset,
            )
            total = review_workflow.count_revisions(
                current,
                lifecycle_status=lifecycle_status,
                keyword=keyword,
                admin_area=admin_area,
                place_kind=place_kind,
            )
            readiness = review_workflow.review_readiness_by_revision_ids(
                current,
                revision_ids=tuple(revision.place_revision_id for revision in revisions),
            )
            return {
                "items": [
                    {
                        **_revision_response(revision),
                        "review_readiness": readiness.get(revision.place_revision_id),
                    }
                    for revision in revisions
                ],
                "limit": limit,
                "offset": offset,
                "total": total,
            }

        @router.get("/dashboard-summary")
        def get_dashboard_summary(
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            summary = review_workflow.dashboard_summary(current)
            return {
                "revisions": summary["revisions"],
                "review_tasks": summary["review_tasks"],
                "recent_ready_tasks": [_review_task_response(task) for task in summary["recent_ready_tasks"]],
            }

        @router.get("/place-revisions/{revision_id}")
        def get_place_revision(
            revision_id: str,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            revision = review_workflow.get_revision(current, revision_id=revision_id)
            return _revision_response(revision)

        @router.get("/review-tasks")
        def list_review_tasks(
            current: AdminPrincipal = principal_dependency,
            review_status: str | None = Query(default=None, max_length=32),
            keyword: str | None = Query(default=None, max_length=100),
            admin_area: str | None = Query(default=None, max_length=120),
            place_kind: str | None = Query(default=None, max_length=32),
            limit: int = Query(default=50, ge=1, le=100),
            offset: int = Query(default=0, ge=0),
        ) -> dict[str, object]:
            tasks = review_workflow.list_tasks(
                current,
                status=review_status,
                keyword=keyword,
                admin_area=admin_area,
                place_kind=place_kind,
                limit=limit,
                offset=offset,
            )
            revisions = review_workflow.revisions_by_ids(
                current,
                revision_ids=tuple(task.place_revision_id for task in tasks),
            )
            return {
                "items": [
                    _review_task_response(task, revisions.get(task.place_revision_id))
                    for task in tasks
                ],
                "limit": limit,
                "offset": offset,
                "total": review_workflow.count_tasks(
                    current,
                    status=review_status,
                    keyword=keyword,
                    admin_area=admin_area,
                    place_kind=place_kind,
                ),
            }

        @router.post(
            "/place-revisions/{revision_id}/review-tasks", status_code=status.HTTP_201_CREATED
        )
        def submit_place_review(
            revision_id: str,
            payload: SubmitPlaceReviewInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            task = review_workflow.submit(
                current,
                place_revision_id=revision_id,
                operation_intent_id=payload.operation_intent_id,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _review_task_response(task)

        @router.post("/review-tasks/{task_id}/decisions")
        def decide_place_review(
            task_id: str,
            payload: DecidePlaceReviewInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            task = review_workflow.decide(
                current,
                task_id=task_id,
                operation_intent_id=payload.operation_intent_id,
                expected_version=payload.expected_version,
                decision_kind=payload.decision_kind,
                reason_code=payload.reason_code,
                reason_text=payload.reason_text,
                request_id=request.state.request_id,
            )
            return _review_task_response(task)

        @router.get("/review-tasks/{task_id}")
        def get_review_task(
            task_id: str,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            return _review_task_response(review_workflow.get_task(current, task_id=task_id))

        @router.post("/review-tasks/batch-decisions")
        def decide_place_review_batch(
            payload: BatchDecidePlaceReviewInput,
            request: Request,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            result = review_workflow.decide_batch(
                current,
                items=tuple(item.model_dump() for item in payload.items),
                request_id=request.state.request_id,
            )
            return {
                "total": result["total"],
                "succeeded": [_review_task_response(task) for task in result["succeeded"]],
                "failed": list(result["failed"]),
            }

        @router.get("/review-tasks/{task_id}/decisions")
        def list_review_decisions(
            task_id: str,
            current: AdminPrincipal = principal_dependency,
        ) -> dict[str, object]:
            decisions = review_workflow.list_decisions(current, task_id=task_id)
            return {
                "items": [_review_decision_response(decision) for decision in decisions],
            }

    return router


def _snapshot_api_response(snapshot, *, include_payload: bool) -> dict[str, object]:
    response = {
        "snapshot_id": snapshot.snapshot_id,
        "data_snapshot_version": snapshot.data_snapshot_version,
        "city_id": snapshot.city_id,
        "content_sha256": snapshot.content_sha256,
        "source_batch_id": snapshot.source_batch_id,
        "created_at": snapshot.created_at.isoformat(),
        "status": snapshot.status,
    }
    if include_payload:
        response["payload"] = snapshot.snapshot_payload
    return response


def _actor_response(actor: AdminActor) -> dict[str, object]:
    return {
        "admin_actor_id": actor.admin_actor_id,
        "login_name": actor.login_name,
        "status": actor.status,
        "version": actor.version,
        "session_version": actor.session_version,
        "role_keys": list(actor.role_keys),
        "created_at": actor.created_at.isoformat(),
        "updated_at": actor.updated_at.isoformat(),
    }


def _audit_response(
    event: AdminAuditEvent,
    *,
    actor_login_name: str | None = None,
) -> dict[str, object]:
    return {
        "audit_event_id": event.audit_event_id,
        "actor_id": event.actor_id,
        "actor_login_name": actor_login_name,
        "actor_role": event.actor_role,
        "action": event.action,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "target_revision": event.target_revision,
        "before_digest": event.before_digest,
        "after_digest": event.after_digest,
        "reason_code": event.reason_code,
        "reason_text": event.reason_text,
        "request_id": event.request_id,
        "operation_intent_id": event.operation_intent_id,
        "result": event.result,
        "error_code": event.error_code,
        "occurred_at": event.occurred_at.isoformat(),
    }


def _review_task_response(
    task: PlaceReviewTask, revision: PlaceRevision | None = None
) -> dict[str, object]:
    response: dict[str, object] = {
        "review_task_id": task.review_task_id,
        "place_revision_id": task.place_revision_id,
        "status": task.status,
        "assigned_reviewer_id": task.assigned_reviewer_id,
        "version": task.version,
        "created_by": task.created_by,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }
    if revision is not None:
        response.update(
            {
                "place_id": revision.place_id,
                "revision_number": revision.revision_number,
                "canonical_name": revision.canonical_name,
                "admin_area": revision.admin_area,
                "place_kind": revision.place_kind,
                "category": revision.category,
            }
        )
    return response


def _revision_response(revision: PlaceRevision) -> dict[str, object]:
    return {
        "place_revision_id": revision.place_revision_id,
        "place_id": revision.place_id,
        "revision_number": revision.revision_number,
        "revision_version": revision.revision_version,
        "lifecycle_status": revision.lifecycle_status,
        "canonical_name": revision.canonical_name,
        "aliases": list(revision.aliases),
        "place_kind": revision.place_kind,
        "category": revision.category,
        "admin_area": revision.admin_area,
        "address": revision.address,
        "geometry_kind": revision.geometry_kind,
        "duration_min": revision.duration_min,
        "duration_recommended": revision.duration_recommended,
        "duration_max": revision.duration_max,
        "internal_travel_min": revision.internal_travel_min,
        "energy_level": revision.energy_level,
        "indoor_outdoor": revision.indoor_outdoor,
        "suitable_periods": list(revision.suitable_periods),
        "audience_tags": list(revision.audience_tags),
        "rain_suitability": revision.rain_suitability,
        "is_always_open": revision.is_always_open,
        "solver_eligible": revision.solver_eligible,
        "conflicts_resolved": revision.conflicts_resolved,
        "source_record_ids": list(revision.source_record_ids),
        "created_at": revision.created_at.isoformat(),
        "reviewed_at": revision.reviewed_at.isoformat() if revision.reviewed_at else None,
        "published_at": revision.published_at.isoformat() if revision.published_at else None,
        "review_flags": list(revision.review_flags),
        "relation_review_status": revision.relation_review_status,
    }


def _revision_evidence_response(evidence: PlaceRevisionEvidence) -> dict[str, object]:
    projection = evidence.projection
    valid_source_ids = {
        source.source_record_id
        for source in evidence.source_records
        if source.status == "active"
    }
    return {
        "revision": _revision_response(evidence.revision),
        "sources": [
            {
                "source_record_id": source.source_record_id,
                "source_id": source.source_id,
                "source_url": safe_source_url(source.source_url),
                "source_url_redacted": safe_source_url(source.source_url)
                != source.source_url,
                "collection_mode": source.collection_mode,
                "target_stage": source.target_stage,
                "source_decision": source.source_decision,
                "observed_at": source.observed_at.isoformat(),
                "status": source.status,
                "content_sha256": source.content_sha256,
                "attached_to_revision": (
                    source.source_record_id in evidence.revision.source_record_ids
                ),
            }
            for source in evidence.source_records
        ],
        "geometries": [
            {
                "geometry_id": geometry.geometry_id,
                "geometry_kind": geometry.geometry_kind,
                "geometry": geometry.geometry,
                "source_record_id": geometry.source_record_id,
                "source_record_valid": geometry.source_record_id in valid_source_ids,
                "review_status": geometry.review_status,
                "active": geometry.active,
                "created_at": geometry.created_at.isoformat(),
                "reviewed_at": (
                    geometry.reviewed_at.isoformat() if geometry.reviewed_at else None
                ),
            }
            for geometry in evidence.geometries
        ],
        "access_points": [
            {
                "access_point_id": point.access_point_id,
                "access_point_kind": point.access_point_kind,
                "name": point.name,
                "lat": float(point.lat),
                "lng": float(point.lng),
                "source_record_id": point.source_record_id,
                "source_record_valid": point.source_record_id in valid_source_ids,
                "review_status": point.review_status,
                "active": point.active,
                "fetched_at": point.fetched_at.isoformat() if point.fetched_at else None,
                "reviewed_at": point.reviewed_at.isoformat() if point.reviewed_at else None,
                "created_at": point.created_at.isoformat(),
            }
            for point in evidence.access_points
        ],
        "time_rules": [
            {
                "time_rule_id": rule.time_rule_id,
                "rule_kind": rule.rule_kind,
                "weekdays": list(rule.weekdays),
                "start_minute": rule.start_minute,
                "end_minute": rule.end_minute,
                "last_entry_minute": rule.last_entry_minute,
                "valid_from": rule.valid_from.isoformat() if rule.valid_from else None,
                "valid_to": rule.valid_to.isoformat() if rule.valid_to else None,
                "source_record_id": rule.source_record_id,
                "source_record_valid": rule.source_record_id in valid_source_ids,
                "review_status": rule.review_status,
                "active": rule.active,
                "created_at": rule.created_at.isoformat(),
                "reviewed_at": rule.reviewed_at.isoformat() if rule.reviewed_at else None,
            }
            for rule in evidence.time_rules
        ],
        "closures": [
            {
                "closure_id": closure.closure_id,
                "weekday": closure.weekday,
                "source_record_id": closure.source_record_id,
                "source_record_valid": closure.source_record_id in valid_source_ids,
                "review_status": closure.review_status,
                "active": closure.active,
                "created_at": closure.created_at.isoformat(),
                "reviewed_at": (
                    closure.reviewed_at.isoformat() if closure.reviewed_at else None
                ),
            }
            for closure in evidence.closures
        ],
        "date_exceptions": [
            {
                "date_exception_id": exception.date_exception_id,
                "service_date": exception.service_date.isoformat(),
                "exception_kind": exception.exception_kind,
                "start_minute": exception.start_minute,
                "end_minute": exception.end_minute,
                "last_entry_minute": exception.last_entry_minute,
                "source_record_id": exception.source_record_id,
                "source_record_valid": exception.source_record_id in valid_source_ids,
                "review_status": exception.review_status,
                "active": exception.active,
                "created_at": exception.created_at.isoformat(),
                "reviewed_at": (
                    exception.reviewed_at.isoformat()
                    if exception.reviewed_at
                    else None
                ),
            }
            for exception in evidence.date_exceptions
        ],
        "relations": [
            {
                "relation_id": relation.relation_id,
                "from_place_id": relation.from_place_id,
                "to_place_id": relation.to_place_id,
                "from_place_name": dict(evidence.relation_place_names).get(relation.from_place_id),
                "to_place_name": dict(evidence.relation_place_names).get(relation.to_place_id),
                "relation_summary": _relation_summary(
                    relation.relation_type,
                    dict(evidence.relation_place_names).get(relation.from_place_id),
                    dict(evidence.relation_place_names).get(relation.to_place_id),
                ),
                "relation_type": relation.relation_type,
                "source_record_id": relation.source_record_id,
                "source_record_valid": relation.source_record_id in valid_source_ids,
                "review_status": relation.review_status,
                "resolution_status": relation.resolution_status,
                "decision_note": relation.decision_note,
                "active": relation.active,
                "created_at": relation.created_at.isoformat(),
                "reviewed_at": relation.reviewed_at.isoformat() if relation.reviewed_at else None,
            }
            for relation in evidence.relations
        ],
        "projection": (
            {
                "projection_id": projection.projection_id,
                "projection_version": projection.projection_version,
                "data_snapshot_version": projection.data_snapshot_version,
                "solver_node_id": projection.solver_node_id,
                "place_kind": projection.place_kind,
                "geometry_kind": projection.geometry_kind,
                "arrival_access_point_id": projection.arrival_access_point_id,
                "departure_access_point_id": projection.departure_access_point_id,
                "status": projection.status,
                "projection_hash": projection.projection_hash,
                "gate_reason_codes": list(projection.gate_reason_codes),
                "created_at": projection.created_at.isoformat(),
                "published_at": (
                    projection.published_at.isoformat() if projection.published_at else None
                ),
            }
            if projection is not None
            else None
        ),
        "missing_source_record_ids": list(evidence.missing_source_record_ids),
    }


def _relation_summary(relation_type: str, from_name: str | None, to_name: str | None) -> str:
    left = from_name or "待补充地点名称"
    right = to_name or "待补充地点名称"
    meanings = {
        "contains": f"{left} 包含 {right}",
        "part_of": f"{left} 属于 {right}",
        "overlaps": f"{left} 与 {right} 范围重叠",
        "same_experience": f"{left} 与 {right} 属于同一体验",
    }
    return meanings.get(relation_type, f"{left} 与 {right} 存在待确认关系")


_SENSITIVE_SOURCE_QUERY_KEYS = {
    "accesskey",
    "accesstoken",
    "apikey",
    "auth",
    "authorization",
    "bearer",
    "clientsecret",
    "clienttoken",
    "credential",
    "credentials",
    "jwt",
    "key",
    "password",
    "passwd",
    "privatekey",
    "secret",
    "signature",
    "sig",
    "token",
    "xapikey",
}


def _is_sensitive_source_query_key(key: str) -> bool:
    """Recognize common credential query parameters after normalizing spelling."""

    normalized_key = "".join(character for character in key.lower() if character.isalnum())
    if normalized_key in _SENSITIVE_SOURCE_QUERY_KEYS:
        return True
    return normalized_key.endswith(
        ("key", "token", "secret", "password", "passwd", "signature", "sig")
    )


def safe_source_url(value: str) -> str:
    """Keep source links useful without reflecting credential-like URL parts."""

    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname or ""
        port = parsed.port
    except ValueError:
        return "[invalid source URL]"
    # urlsplit().hostname strips IPv6 brackets; restore them before
    # reconstructing a redacted URL so the result remains parseable.
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    if port is not None:
        hostname = f"{hostname}:{port}"
    netloc = hostname
    redacted = parsed.username is not None or parsed.password is not None
    query_pairs = []
    for key, query_value in parse_qsl(parsed.query, keep_blank_values=True):
        if _is_sensitive_source_query_key(key):
            query_value = "[REDACTED]"
            redacted = True
        query_pairs.append((key, query_value))
    fragment = parsed.fragment
    if fragment:
        fragment = "[REDACTED]"
        redacted = True
    if redacted:
        query = urlencode(query_pairs)
        return urlunsplit((parsed.scheme, netloc, parsed.path, query, fragment))
    return value


def _holiday_sync_job_response(job: HolidayCalendarSyncJob) -> dict[str, object]:
    return {
        "sync_job_id": job.job_id,
        "region_code": job.region_code,
        "year": job.year,
        "mode": job.mode,
        "status": job.status,
        "source_url": safe_source_url(job.source_url) if job.source_url else None,
        "source_title": job.source_title,
        "source_published_at": (
            job.source_published_at.isoformat() if job.source_published_at else None
        ),
        "source_content_sha256": job.source_content_sha256,
        "validation_result": job.validation_result,
        "calendar_id": job.calendar_id,
        "attempt_count": job.attempt_count,
        "next_retry_at": job.next_retry_at.isoformat() if job.next_retry_at else None,
        "created_by": job.created_by,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


def _holiday_calendar_version_response(
    calendar: HolidayCalendarVersion,
) -> dict[str, object]:
    return {
        "calendar_id": calendar.calendar_id,
        "region_code": calendar.region_code,
        "year": calendar.year,
        "version": calendar.version,
        "status": calendar.status,
        "display_name": calendar.display_name,
        "source_record_id": calendar.source_record_id,
        "source_content_sha256": calendar.source_content_sha256,
        "normalized_digest": calendar.normalized_digest,
        "supersedes_calendar_id": calendar.supersedes_calendar_id,
        "published_at": calendar.published_at.isoformat(),
        "periods": [
            {
                "holiday_name": item.name,
                "start_date": item.start.isoformat(),
                "end_date": item.end.isoformat(),
                "evidence_quote": item.evidence_quote,
                "display_order": item.display_order,
            }
            for item in calendar.periods
        ],
        "adjusted_workdays": [
            {
                "service_date": item.service_date.isoformat(),
                "holiday_name": item.holiday_name,
                "evidence_quote": item.evidence_quote,
            }
            for item in calendar.adjusted_workdays
        ],
    }


def _review_decision_response(decision: PlaceReviewDecision) -> dict[str, object]:
    return {
        "review_decision_id": decision.review_decision_id,
        "review_task_id": decision.review_task_id,
        "place_revision_id": decision.place_revision_id,
        "actor_id": decision.actor_id,
        "actor_role": decision.actor_role,
        "decision_kind": decision.decision_kind,
        "reason_code": decision.reason_code,
        "reason_text": decision.reason_text,
        "created_at": decision.created_at.isoformat(),
    }
