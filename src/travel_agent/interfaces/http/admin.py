"""Independent administrator authentication and RBAC HTTP boundary."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from travel_agent.application.admin import (
    AdminAuthenticationError,
    AdminIdentityService,
    PlaceReviewWorkflowService,
)
from travel_agent.domain.admin import AdminActor, AdminAuditEvent, AdminPrincipal
from travel_agent.domain.place_catalog import PlaceReviewDecision, PlaceReviewTask, PlaceRevision


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


def build_admin_router(
    service: AdminIdentityService,
    review_workflow: PlaceReviewWorkflowService | None = None,
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

    @router.get("/admin-actors")
    def list_admin_actors(
        current: AdminPrincipal = principal_dependency,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> dict[str, object]:
        actors = service.list_actors(current, limit=limit, offset=offset)
        return {
            "items": [_actor_response(actor) for actor in actors],
            "limit": limit,
            "offset": offset,
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
        target_type: str | None = Query(default=None, max_length=64),
        target_id: str | None = Query(default=None, max_length=128),
        action: str | None = Query(default=None, max_length=80),
        result: str | None = Query(default=None, pattern="^(succeeded|rejected|failed)$"),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> dict[str, object]:
        events = service.list_audit_events(
            current,
            actor_id=actor_id,
            target_type=target_type,
            target_id=target_id,
            action=action,
            result=result,
            limit=limit,
            offset=offset,
        )
        return {
            "items": [_audit_response(event) for event in events],
            "limit": limit,
            "offset": offset,
        }

    if review_workflow is not None:

        @router.get("/candidates")
        def list_candidates(
            current: AdminPrincipal = principal_dependency,
            lifecycle_status: str | None = Query(default="candidate", max_length=24),
            limit: int = Query(default=50, ge=1, le=100),
            offset: int = Query(default=0, ge=0),
        ) -> dict[str, object]:
            revisions = review_workflow.list_revisions(
                current,
                lifecycle_status=lifecycle_status,
                limit=limit,
                offset=offset,
            )
            return {
                "items": [_revision_response(revision) for revision in revisions],
                "limit": limit,
                "offset": offset,
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
            limit: int = Query(default=50, ge=1, le=100),
            offset: int = Query(default=0, ge=0),
        ) -> dict[str, object]:
            tasks = review_workflow.list_tasks(
                current, status=review_status, limit=limit, offset=offset
            )
            return {
                "items": [_review_task_response(task) for task in tasks],
                "limit": limit,
                "offset": offset,
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


def _audit_response(event: AdminAuditEvent) -> dict[str, object]:
    return {
        "audit_event_id": event.audit_event_id,
        "actor_id": event.actor_id,
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


def _review_task_response(task: PlaceReviewTask) -> dict[str, object]:
    return {
        "review_task_id": task.review_task_id,
        "place_revision_id": task.place_revision_id,
        "status": task.status,
        "assigned_reviewer_id": task.assigned_reviewer_id,
        "version": task.version,
        "created_by": task.created_by,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


def _revision_response(revision: PlaceRevision) -> dict[str, object]:
    return {
        "place_revision_id": revision.place_revision_id,
        "place_id": revision.place_id,
        "revision_number": revision.revision_number,
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
