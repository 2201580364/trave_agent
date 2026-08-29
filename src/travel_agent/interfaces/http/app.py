"""FastAPI routes for the first anonymous planning vertical slice."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, datetime
from enum import Enum
from typing import Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from travel_agent.application.admin import AdminIdentityService
from travel_agent.application.common.clock import Clock
from travel_agent.application.common.errors import ApplicationError, ResourceNotFoundError
from travel_agent.application.common.unit_of_work import UnitOfWork
from travel_agent.application.feedback import (
    SubmitNodeFeedback,
    SubmitNodeFeedbackHandler,
    SubmitTripFeedback,
    SubmitTripFeedbackHandler,
)
from travel_agent.application.planning import (
    CreateDraft,
    CreateDraftHandler,
    ReplaceAttractionSelection,
    ReplaceAttractionSelectionHandler,
    ReplaceTripAttraction,
    ReplaceTripAttractionHandler,
    SubmitGeneration,
    SubmitGenerationHandler,
    UpdateTravelFacts,
    UpdateTravelFactsHandler,
)
from travel_agent.application.planning.ports import (
    DataSnapshotVersionProvider,
    GenerationExecutor,
    IdGenerator,
)
from travel_agent.application.sharing import (
    CopyPlanShareToDraft,
    CopyPlanShareToDraftHandler,
    CreatePlanShare,
    CreatePlanShareHandler,
    GetPublishedPlanShareHandler,
)
from travel_agent.application.sharing.ports import PlanShareTokenCodec
from travel_agent.domain.planning import (
    ConfirmationStatus,
    CrowdType,
    TransportType,
    TravelFacts,
    TravelMode,
    VisitPeriodPreferenceInput,
)
from travel_agent.infrastructure.database.identity import AnonymousIdentityService
from travel_agent.infrastructure.solver import PublishedSolverDataProvider

from .admin import build_admin_router


@dataclass(frozen=True, slots=True)
class HttpContainer:
    uow_factory: Callable[[], UnitOfWork]
    clock: Clock
    ids: IdGenerator
    snapshots: DataSnapshotVersionProvider
    executor: GenerationExecutor
    identity: AnonymousIdentityService
    catalog: PublishedSolverDataProvider | None = None
    readiness: Callable[[], dict[str, object]] | None = None
    share_tokens: PlanShareTokenCodec | None = None
    admin_identity: AdminIdentityService | None = None


class AnonymousSessionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_installation_id: str | None = Field(default=None, max_length=128)


class CreateDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    city_id: str = Field(min_length=1, max_length=64)


class ArrivalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transport_type: TransportType
    confirmation: ConfirmationStatus
    arrives_at: datetime
    station_to_city_min: int = Field(ge=0)
    station_to_city_source: str = Field(min_length=1, max_length=64)


class DepartureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transport_type: TransportType
    confirmation: ConfirmationStatus
    departs_at: datetime
    station_early_min: int = Field(ge=0)
    station_early_source: str = Field(min_length=1, max_length=64)
    last_visit_to_station_min: int = Field(ge=0)
    last_visit_to_station_source: str = Field(min_length=1, max_length=64)


class TravelFactsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_draft_version: int = Field(gt=0)
    start_date: date
    end_date: date
    arrival: ArrivalInput
    departure: DepartureInput
    travel_mode: TravelMode = TravelMode.NORMAL
    crowd_type: CrowdType = CrowdType.UNSPECIFIED


class VisitPeriodInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attraction_id: str = Field(min_length=1, max_length=64)
    preferred_bucket: str
    acceptable_buckets: tuple[str, ...] = ()


class AttractionSelectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_draft_version: int = Field(gt=0)
    attraction_ids: tuple[str, ...]
    visit_period_preferences: tuple[VisitPeriodInput, ...] = ()


class SubmitGenerationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    generation_intent_id: str = Field(min_length=1, max_length=64)
    draft_id: str = Field(min_length=1, max_length=64)
    draft_version: int = Field(gt=0)


class ReplaceTripAttractionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    generation_intent_id: str = Field(min_length=1, max_length=64)
    old_attraction_id: str = Field(min_length=1, max_length=64)
    new_attraction_id: str = Field(min_length=1, max_length=64)


class CreatePlanShareInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_share_intent_id: str = Field(min_length=1, max_length=64)
    revision_id: str = Field(min_length=1, max_length=64)
    template: Literal["simple"] = "simple"


class SubmitTripFeedbackInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feedback_intent_id: str = Field(min_length=1, max_length=64)
    revision_id: str = Field(min_length=1, max_length=64)
    rating: Literal["reasonable", "neutral", "unreasonable"]
    problem_types: tuple[
        Literal[
            "route_too_long",
            "time_unreasonable",
            "pace_mismatch",
            "missing_attraction",
            "attraction_data_error",
            "explanation_unclear",
        ],
        ...,
    ] = ()
    comment: str | None = Field(default=None, max_length=500)


class SubmitNodeFeedbackInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feedback_intent_id: str = Field(min_length=1, max_length=64)
    rating: Literal["like", "dislike"]
    reason_code: Literal[
        "arrangement_good",
        "time_too_tight",
        "travel_too_far",
        "time_period_wrong",
        "duration_wrong",
        "attraction_data_error",
    ] | None = None
    comment: str | None = Field(default=None, max_length=500)


def create_app(container: HttpContainer) -> FastAPI:
    app = FastAPI(title="Travel Agent API", version="1.0.0")

    if container.admin_identity is not None:
        app.include_router(build_admin_router(container.admin_identity))

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        supplied = request.headers.get("X-Request-ID", "")
        request_id = supplied if _valid_request_id(supplied) else f"req_{uuid4().hex}"
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(ApplicationError)
    async def application_error_handler(request: Request, exc: ApplicationError):
        return JSONResponse(
            status_code=_status_for(exc),
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "request_id": request.state.request_id,
                    "retryable": exc.retryable,
                    "field_errors": [],
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException):
        code = "authentication_required" if exc.status_code == 401 else "http_error"
        return _error_response(
            request,
            exc.status_code,
            code,
            str(exc.detail),
            retryable=False,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        fields = [
            {
                "field": ".".join(str(item) for item in error["loc"] if item != "body"),
                "code": error["type"],
                "message": error["msg"],
            }
            for error in exc.errors()
        ]
        return _error_response(
            request,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "request_validation_failed",
            "请求字段无效。",
            retryable=False,
            field_errors=fields,
        )

    @app.exception_handler(ValueError)
    async def domain_validation_error_handler(request: Request, exc: ValueError):
        return _error_response(
            request,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "domain_validation_failed",
            str(exc),
            retryable=False,
        )

    def principal_id(authorization: str | None = Header(default=None)) -> str:
        if authorization is None or not authorization.startswith("Bearer "):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
        token = authorization.removeprefix("Bearer ").strip()
        principal = container.identity.authenticate(token) if token else None
        if principal is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token")
        return principal

    @app.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def health_ready() -> JSONResponse:
        details = (
            container.readiness()
            if container.readiness is not None
            else {"ready": container.identity.ready(), "database": True}
        )
        ready = bool(details["ready"])
        return JSONResponse(
            status_code=200 if ready else 503,
            content={"status": "ready" if ready else "not_ready", **details},
        )

    @app.post("/api/v1/anonymous-sessions", status_code=status.HTTP_201_CREATED)
    def create_anonymous_session(payload: AnonymousSessionInput) -> dict[str, object]:
        session = container.identity.create(payload.device_installation_id)
        return {
            "principal_id": session.principal_id,
            "access_token": session.access_token,
            "expires_at": session.expires_at.isoformat(),
        }

    @app.post("/api/v1/trip-drafts", status_code=status.HTTP_201_CREATED)
    def create_draft(
        payload: CreateDraftInput,
        principal: str = Depends(principal_id),
    ) -> dict[str, object]:
        result = CreateDraftHandler(
            container.uow_factory(), container.clock, container.ids
        ).handle(CreateDraft(principal, payload.city_id))
        return _draft_response(result.draft)

    @app.get("/api/v1/trip-drafts/{draft_id}")
    def get_draft(
        draft_id: str, principal: str = Depends(principal_id)
    ) -> dict[str, object]:
        with container.uow_factory() as uow:
            draft = uow.drafts.get(draft_id)
            if draft is None or draft.principal_id != principal:
                raise ResourceNotFoundError
            return _draft_response(draft)

    @app.patch("/api/v1/trip-drafts/{draft_id}/travel-facts")
    def update_travel_facts(
        draft_id: str,
        payload: TravelFactsInput,
        principal: str = Depends(principal_id),
    ) -> dict[str, object]:
        facts = TravelFacts(
            payload.start_date,
            payload.end_date,
            payload.arrival.transport_type,
            payload.arrival.confirmation,
            payload.arrival.arrives_at,
            payload.arrival.station_to_city_min,
            payload.arrival.station_to_city_source,
            payload.departure.transport_type,
            payload.departure.confirmation,
            payload.departure.departs_at,
            payload.departure.station_early_min,
            payload.departure.station_early_source,
            payload.departure.last_visit_to_station_min,
            payload.departure.last_visit_to_station_source,
            payload.travel_mode,
            payload.crowd_type,
        )
        result = UpdateTravelFactsHandler(container.uow_factory(), container.clock).handle(
            UpdateTravelFacts(principal, draft_id, payload.expected_draft_version, facts)
        )
        return _draft_response(result.draft)

    @app.put("/api/v1/trip-drafts/{draft_id}/attraction-selection")
    def replace_selection(
        draft_id: str,
        payload: AttractionSelectionInput,
        principal: str = Depends(principal_id),
    ) -> dict[str, object]:
        preferences = tuple(
            VisitPeriodPreferenceInput(
                item.attraction_id,
                item.preferred_bucket,
                item.acceptable_buckets,
            )
            for item in payload.visit_period_preferences
        )
        result = ReplaceAttractionSelectionHandler(
            container.uow_factory(), container.clock
        ).handle(
            ReplaceAttractionSelection(
                principal,
                draft_id,
                payload.expected_draft_version,
                payload.attraction_ids,
                preferences,
            )
        )
        return _draft_response(result.draft)

    @app.get("/api/v1/trip-drafts/{draft_id}/review")
    def review_draft(
        draft_id: str, principal: str = Depends(principal_id)
    ) -> dict[str, object]:
        with container.uow_factory() as uow:
            draft = uow.drafts.get(draft_id)
            if draft is None or draft.principal_id != principal:
                raise ResourceNotFoundError
            issues = _readiness_issues(draft)
            return {
                "draft_id": draft.draft_id,
                "draft_version": draft.draft_version,
                "ready_for_generation": not issues,
                "issues": issues,
                "summary": _draft_response(draft),
            }

    @app.get("/api/v1/attractions")
    def list_attractions(
        city_id: str = "hangzhou",
        principal: str = Depends(principal_id),
    ) -> dict[str, object]:
        del principal
        snapshot = _published_snapshot(container, city_id)
        return {
            "city_id": city_id,
            "data_snapshot_version": snapshot.version,
            "items": [_attraction_response(item) for item in snapshot.attractions],
        }

    @app.get("/api/v1/attractions/{attraction_id}")
    def get_attraction(
        attraction_id: str,
        city_id: str = "hangzhou",
        principal: str = Depends(principal_id),
    ) -> dict[str, object]:
        del principal
        snapshot = _published_snapshot(container, city_id)
        item = next(
            (item for item in snapshot.attractions if item.external_id == attraction_id),
            None,
        )
        if item is None:
            raise ResourceNotFoundError
        return _attraction_response(item)

    @app.post("/api/v1/generation-intents", status_code=status.HTTP_202_ACCEPTED)
    def submit_generation(
        payload: SubmitGenerationInput,
        principal: str = Depends(principal_id),
    ) -> dict[str, object]:
        SubmitGenerationHandler(
            container.uow_factory(),
            container.clock,
            container.snapshots,
            container.executor,
        ).handle(
            SubmitGeneration(
                principal,
                payload.generation_intent_id,
                payload.draft_id,
                payload.draft_version,
            )
        )
        return _owned_intent(container, payload.generation_intent_id, principal)

    @app.get("/api/v1/generation-intents/{intent_id}")
    def get_generation_intent(
        intent_id: str, principal: str = Depends(principal_id)
    ) -> dict[str, object]:
        return _owned_intent(container, intent_id, principal)

    @app.get("/api/v1/trips")
    def list_trips(
        limit: int = Query(default=20, ge=1, le=50),
        offset: int = Query(default=0, ge=0),
        principal: str = Depends(principal_id),
    ) -> dict[str, object]:
        with container.uow_factory() as uow:
            trips = uow.trips.list_by_principal(
                principal,
                limit=limit + 1,
                offset=offset,
            )
            visible = trips[:limit]
            items = []
            for trip in visible:
                revision = uow.trip_revisions.get(trip.current_revision_id)
                if revision is None or revision.trip_id != trip.trip_id:
                    raise RuntimeError("trip current revision invariant is broken")
                revision_count = len(uow.trip_revisions.list_by_trip(trip.trip_id))
                items.append(_trip_summary_response(trip, revision, revision_count))
        return {
            "items": items,
            "limit": limit,
            "offset": offset,
            "has_more": len(trips) > limit,
        }

    @app.get("/api/v1/trips/{trip_id}")
    def get_trip(
        trip_id: str, principal: str = Depends(principal_id)
    ) -> dict[str, object]:
        with container.uow_factory() as uow:
            trip = uow.trips.get(trip_id)
            if trip is None or trip.principal_id != principal:
                raise ResourceNotFoundError
            revision = uow.trip_revisions.get(trip.current_revision_id)
            if revision is None or revision.trip_id != trip.trip_id:
                raise RuntimeError("trip current revision invariant is broken")
            response = _trip_summary_response(
                trip,
                revision,
                len(uow.trip_revisions.list_by_trip(trip.trip_id)),
            )
            response["created_at"] = trip.created_at.isoformat()
            return response

    @app.get("/api/v1/trips/{trip_id}/revisions")
    def list_revisions(
        trip_id: str,
        principal: str = Depends(principal_id),
    ) -> dict[str, object]:
        with container.uow_factory() as uow:
            trip = uow.trips.get(trip_id)
            if trip is None or trip.principal_id != principal:
                raise ResourceNotFoundError
            revisions = uow.trip_revisions.list_by_trip(trip_id)
            return {
                "trip_id": trip.trip_id,
                "current_revision_id": trip.current_revision_id,
                "items": [
                    _revision_summary_response(
                        revision,
                        current_revision_id=trip.current_revision_id,
                    )
                    for revision in revisions
                ],
            }

    @app.get("/api/v1/trips/{trip_id}/revisions/{revision_id}")
    def get_revision(
        trip_id: str,
        revision_id: str,
        principal: str = Depends(principal_id),
    ) -> dict[str, object]:
        with container.uow_factory() as uow:
            trip = uow.trips.get(trip_id)
            revision = uow.trip_revisions.get(revision_id)
            if (
                trip is None
                or trip.principal_id != principal
                or revision is None
                or revision.trip_id != trip_id
            ):
                raise ResourceNotFoundError
            return _jsonable(revision)

    @app.post(
        "/api/v1/trips/{trip_id}/revisions/{revision_id}/attraction-replacements",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def replace_trip_attraction(
        trip_id: str,
        revision_id: str,
        payload: ReplaceTripAttractionInput,
        principal: str = Depends(principal_id),
    ) -> dict[str, object]:
        if payload.old_attraction_id == payload.new_attraction_id:
            raise ValueError("replacement attraction must be different")
        with container.uow_factory() as uow:
            trip = uow.trips.get(trip_id)
            if trip is None or trip.principal_id != principal:
                raise ResourceNotFoundError
            snapshot = _published_snapshot(container, trip.city_id)
        published_ids = {item.external_id for item in snapshot.attractions}
        if payload.new_attraction_id not in published_ids:
            raise ResourceNotFoundError

        result = ReplaceTripAttractionHandler(
            container.uow_factory(),
            container.clock,
            container.ids,
            container.snapshots,
            container.executor,
        ).handle(
            ReplaceTripAttraction(
                principal,
                payload.generation_intent_id,
                trip_id,
                revision_id,
                payload.old_attraction_id,
                payload.new_attraction_id,
            )
        )
        response = _owned_intent(container, payload.generation_intent_id, principal)
        response["replacement_draft_id"] = result.draft.draft_id
        response["replacement_draft_version"] = result.draft.draft_version
        return response

    @app.post(
        "/api/v1/trips/{trip_id}/feedback",
        status_code=status.HTTP_201_CREATED,
    )
    def submit_trip_feedback(
        trip_id: str,
        payload: SubmitTripFeedbackInput,
        principal: str = Depends(principal_id),
    ) -> dict[str, object]:
        result = SubmitTripFeedbackHandler(
            container.uow_factory(),
            container.clock,
            container.ids,
        ).handle(
            SubmitTripFeedback(
                principal,
                payload.feedback_intent_id,
                trip_id,
                payload.revision_id,
                payload.rating,
                payload.problem_types,
                payload.comment,
            )
        )
        return _feedback_response(result)

    @app.post(
        "/api/v1/trips/{trip_id}/revisions/{revision_id}/nodes/{node_id}/feedback",
        status_code=status.HTTP_201_CREATED,
    )
    def submit_node_feedback(
        trip_id: str,
        revision_id: str,
        node_id: str,
        payload: SubmitNodeFeedbackInput,
        principal: str = Depends(principal_id),
    ) -> dict[str, object]:
        result = SubmitNodeFeedbackHandler(
            container.uow_factory(),
            container.clock,
            container.ids,
        ).handle(
            SubmitNodeFeedback(
                principal,
                payload.feedback_intent_id,
                trip_id,
                revision_id,
                node_id,
                payload.rating,
                payload.reason_code,
                payload.comment,
            )
        )
        return _feedback_response(result)

    @app.post(
        "/api/v1/trips/{trip_id}/plan-shares",
        status_code=status.HTTP_201_CREATED,
    )
    def create_plan_share(
        trip_id: str,
        payload: CreatePlanShareInput,
        principal: str = Depends(principal_id),
    ) -> dict[str, object]:
        share_tokens = _share_tokens(container)
        result = CreatePlanShareHandler(
            container.uow_factory(),
            container.clock,
            container.ids,
            share_tokens,
        ).handle(
            CreatePlanShare(
                principal,
                payload.plan_share_intent_id,
                trip_id,
                payload.revision_id,
                payload.template,
            )
        )
        return {
            "plan_share_id": result.share.plan_share_id,
            "status": result.share.status,
            "template": result.share.template,
            "revision_id": result.share.revision_id,
            "share_schema_version": result.share.share_schema_version,
            "share_token": result.public_token,
            "share_path": (
                "/pages/plan-share-view/index?token=" f"{result.public_token}"
            ),
            "published_at": result.share.published_at.isoformat(),
            "reused": result.reused,
            "content": result.share.share_snapshot,
        }

    @app.get("/api/v1/plan-shares/{public_token}")
    def get_plan_share(public_token: str) -> JSONResponse:
        published = GetPublishedPlanShareHandler(
            container.uow_factory(),
            _share_tokens(container),
        ).handle(public_token)
        return JSONResponse(
            content={
                "plan_share_id": published.plan_share_id,
                "status": "published",
                "template": published.template,
                "published_at": published.published_at.isoformat(),
                "content": published.share_snapshot,
            },
            headers={"Cache-Control": "no-store"},
        )

    @app.post(
        "/api/v1/plan-shares/{public_token}/draft-copies",
        status_code=status.HTTP_201_CREATED,
    )
    def copy_plan_share_to_draft(
        public_token: str,
        principal: str = Depends(principal_id),
    ) -> dict[str, object]:
        result = CopyPlanShareToDraftHandler(
            container.uow_factory(),
            container.clock,
            container.ids,
            _share_tokens(container),
        ).handle(CopyPlanShareToDraft(principal, public_token))
        return _draft_response(result.draft)

    return app


def _owned_intent(container: HttpContainer, intent_id: str, principal: str):
    with container.uow_factory() as uow:
        intent = uow.generation_intents.get(intent_id)
        if intent is None or intent.principal_id != principal:
            raise ResourceNotFoundError
        return _jsonable(intent)


def _draft_response(draft) -> dict[str, object]:
    facts = draft.travel_facts
    travel_facts = None
    if facts is not None:
        travel_facts = {
            "start_date": facts.start_date.isoformat(),
            "end_date": facts.end_date.isoformat(),
            "arrival": {
                "transport_type": facts.arrival_transport_type.value,
                "confirmation": facts.arrival_confirmation.value,
                "arrives_at": facts.arrival_at.isoformat(),
                "station_to_city_min": facts.station_to_city_min,
                "station_to_city_source": facts.station_to_city_source,
            },
            "departure": {
                "transport_type": facts.departure_transport_type.value,
                "confirmation": facts.departure_confirmation.value,
                "departs_at": facts.departure_at.isoformat(),
                "station_early_min": facts.station_early_min,
                "station_early_source": facts.station_early_source,
                "last_visit_to_station_min": facts.last_visit_to_station_min,
                "last_visit_to_station_source": facts.last_visit_to_station_source,
            },
            "travel_mode": facts.travel_mode.value,
            "crowd_type": facts.crowd_type.value,
        }
    return {
        "draft_id": draft.draft_id,
        "draft_version": draft.draft_version,
        "status": draft.status,
        "city": {
            "city_id": draft.city_id,
            "name": "杭州" if draft.city_id == "hangzhou" else draft.city_id,
            "timezone": "Asia/Shanghai",
        },
        "travel_facts": travel_facts,
        "selected_attraction_ids": list(draft.selected_attraction_ids),
        "visit_period_preferences": _jsonable(draft.visit_period_preferences),
        "last_saved_at": draft.updated_at.isoformat(),
    }


def _feedback_response(result) -> dict[str, object]:
    feedback = result.feedback
    return {
        "feedback_id": feedback.feedback_id,
        "feedback_intent_id": feedback.feedback_intent_id,
        "trip_id": feedback.trip_id,
        "revision_id": feedback.revision_id,
        "feedback_scope": feedback.feedback_scope,
        "node_id": feedback.node_id,
        "rating": feedback.rating,
        "reason_codes": list(feedback.reason_codes),
        "comment": feedback.comment,
        "created_at": feedback.created_at.isoformat(),
        "reused": result.reused,
        "deduplicated": result.deduplicated,
    }


def _trip_summary_response(trip, revision, revision_count: int) -> dict[str, object]:
    snapshot = _snapshot_overview(revision.result_snapshot)
    return {
        "trip_id": trip.trip_id,
        "city_id": trip.city_id,
        "city_name": "杭州" if trip.city_id == "hangzhou" else trip.city_id,
        "current_revision_id": trip.current_revision_id,
        "current_revision_number": revision.revision_number,
        "completion_kind": revision.completion_kind.value,
        "has_soft_degradation": revision.has_soft_degradation,
        "start_date": snapshot["start_date"],
        "end_date": snapshot["end_date"],
        "scheduled_count": snapshot["scheduled_count"],
        "unplaced_count": snapshot["unplaced_count"],
        "updated_at": trip.updated_at.isoformat(),
        "revision_count": revision_count,
    }


def _revision_summary_response(
    revision,
    *,
    current_revision_id: str,
) -> dict[str, object]:
    snapshot = _snapshot_overview(revision.result_snapshot)
    return {
        "trip_revision_id": revision.trip_revision_id,
        "revision_number": revision.revision_number,
        "is_current": revision.trip_revision_id == current_revision_id,
        "completion_kind": revision.completion_kind.value,
        "has_soft_degradation": revision.has_soft_degradation,
        "start_date": snapshot["start_date"],
        "end_date": snapshot["end_date"],
        "scheduled_count": snapshot["scheduled_count"],
        "unplaced_count": snapshot["unplaced_count"],
        "created_at": revision.created_at.isoformat(),
    }


def _snapshot_overview(snapshot: dict[str, object]) -> dict[str, object]:
    raw_days = snapshot.get("days")
    days = (
        [item for item in raw_days if isinstance(item, dict)]
        if isinstance(raw_days, list)
        else []
    )
    dates = [
        item["date"]
        for item in days
        if isinstance(item.get("date"), str)
    ]
    raw_summary = snapshot.get("summary")
    summary = raw_summary if isinstance(raw_summary, dict) else {}
    raw_scheduled = summary.get("scheduled_count")
    scheduled_count = (
        raw_scheduled
        if isinstance(raw_scheduled, int) and not isinstance(raw_scheduled, bool)
        else sum(
            len(nodes)
            for day in days
            if isinstance((nodes := day.get("nodes")), list)
        )
    )
    raw_unplaced = snapshot.get("unplaced")
    unplaced_count = len(raw_unplaced) if isinstance(raw_unplaced, list) else 0
    return {
        "start_date": min(dates) if dates else None,
        "end_date": max(dates) if dates else None,
        "scheduled_count": scheduled_count,
        "unplaced_count": unplaced_count,
    }


def _readiness_issues(draft) -> list[str]:
    issues = []
    if draft.travel_facts is None:
        issues.append("travel_facts_missing")
    elif not draft.travel_facts.ready_for_generation:
        issues.append("transport_confirmation_missing")
    if not draft.selected_attraction_ids:
        issues.append("attraction_selection_empty")
    return issues


def _jsonable(value):
    if hasattr(value, "__dataclass_fields__"):
        return _jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _status_for(exc: ApplicationError) -> int:
    return {
        "resource_not_found": status.HTTP_404_NOT_FOUND,
        "draft_version_conflict": status.HTTP_409_CONFLICT,
        "generation_intent_conflict": status.HTTP_409_CONFLICT,
        "draft_not_ready": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "invalid_state_transition": status.HTTP_409_CONFLICT,
        "trip_revision_conflict": status.HTTP_409_CONFLICT,
        "invalid_attraction_replacement": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "plan_share_intent_conflict": status.HTTP_409_CONFLICT,
        "feedback_intent_conflict": status.HTTP_409_CONFLICT,
        "admin_authentication_required": status.HTTP_401_UNAUTHORIZED,
        "admin_permission_denied": status.HTTP_403_FORBIDDEN,
        "admin_actor_version_conflict": status.HTTP_409_CONFLICT,
        "admin_operation_intent_conflict": status.HTTP_409_CONFLICT,
        "admin_login_name_conflict": status.HTTP_409_CONFLICT,
        "admin_role_safety_violation": status.HTTP_409_CONFLICT,
    }.get(exc.code, status.HTTP_400_BAD_REQUEST)


def _share_tokens(container: HttpContainer) -> PlanShareTokenCodec:
    if container.share_tokens is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "plan sharing unavailable",
        )
    return container.share_tokens


def _valid_request_id(value: str) -> bool:
    return bool(value) and len(value) <= 100 and value.isascii() and value.isprintable()


def _published_snapshot(container: HttpContainer, city_id: str):
    if container.catalog is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "catalog unavailable")
    version = container.snapshots.current_version(city_id)
    try:
        return container.catalog.load(version)
    except LookupError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "catalog snapshot unavailable"
        ) from exc


def _attraction_response(item) -> dict[str, object]:
    attraction = item.attraction
    return {
        "attraction_id": item.external_id,
        "name": attraction.name,
        "suggested_duration_min": attraction.suggested_duration,
        "is_always_open": attraction.is_always_open,
        "is_indoor": attraction.is_indoor,
        "energy_level": attraction.energy_level,
        "close_days": sorted(attraction.close_days),
        "coordinate": (
            {"lat": item.coordinate.lat, "lng": item.coordinate.lng}
            if item.coordinate is not None
            else None
        ),
    }


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    *,
    retryable: bool,
    field_errors: list[dict[str, object]] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request.state.request_id,
                "retryable": retryable,
                "field_errors": field_errors or [],
                "details": {},
            }
        },
    )
