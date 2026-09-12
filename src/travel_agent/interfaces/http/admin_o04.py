"""O04 geometry and access-point routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from travel_agent.domain.admin import AdminPrincipal

from . import admin_responses as responses
from .admin import (
    PlaceAccessPointInput,
    PlaceGeometryInput,
    RetirePlaceEvidenceInput,
    _revision_response,
)


def register_o04_routes(router: APIRouter, review_workflow, principal_dependency) -> None:
    @router.post(
        "/place-revisions/{revision_id}/geometries",
        response_model=responses.PlaceRevision,
        response_model_exclude_unset=True,
    )
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

    @router.patch(
        "/place-revisions/{revision_id}/geometries/{geometry_id}",
        response_model=responses.PlaceRevision,
        response_model_exclude_unset=True,
    )
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

    @router.delete(
        "/place-revisions/{revision_id}/geometries/{geometry_id}",
        response_model=responses.PlaceRevision,
        response_model_exclude_unset=True,
    )
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

    @router.post(
        "/place-revisions/{revision_id}/access-points",
        response_model=responses.PlaceRevision,
        response_model_exclude_unset=True,
    )
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

    @router.patch(
        "/place-revisions/{revision_id}/access-points/{access_point_id}",
        response_model=responses.PlaceRevision,
        response_model_exclude_unset=True,
    )
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
        "/place-revisions/{revision_id}/access-points/{access_point_id}",
        response_model=responses.PlaceRevision,
        response_model_exclude_unset=True,
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
