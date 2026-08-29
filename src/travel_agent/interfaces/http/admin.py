"""Independent administrator authentication and RBAC HTTP boundary."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from travel_agent.application.admin import (
    AdminAuthenticationError,
    AdminIdentityService,
)
from travel_agent.domain.admin import AdminActor, AdminAuditEvent, AdminPrincipal


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


def build_admin_router(service: AdminIdentityService) -> APIRouter:
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
