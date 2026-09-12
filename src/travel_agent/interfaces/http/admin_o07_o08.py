"""O07/O08 relation, evidence and review task routes."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from travel_agent.domain.admin import AdminPrincipal

from . import admin_responses as responses
from .admin import (
    ConfirmNoRelationsInput,
    ResolveRelationInput,
    ResolveSourceConflictsInput,
    ReviewPlaceEvidenceInput,
    _revision_response,
    safe_source_url,
)


def register_o07_o08_routes(router: APIRouter, review_workflow, principal_dependency) -> None:
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

    @router.post(
        "/place-revisions/{revision_id}/source-conflicts/resolve",
        response_model=responses.PlaceRevision,
        response_model_exclude_unset=True,
    )
    def resolve_place_source_conflicts(
        revision_id: str,
        payload: ResolveSourceConflictsInput,
        request: Request,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        revision = review_workflow.resolve_source_conflicts(
            current,
            revision_id=revision_id,
            expected_revision_number=payload.expected_revision_number,
            expected_revision_version=payload.expected_revision_version,
            resolved=payload.resolved,
            operation_intent_id=payload.operation_intent_id,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            request_id=request.state.request_id,
        )
        return _revision_response(revision)

    @router.post(
        "/place-revisions/{revision_id}/relations/{relation_id}/resolve",
        response_model=responses.PlaceRevision,
        response_model_exclude_unset=True,
    )
    def resolve_place_relation(
        revision_id: str,
        relation_id: str,
        payload: ResolveRelationInput,
        request: Request,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        revision = review_workflow.resolve_relation(
            current,
            revision_id=revision_id,
            relation_id=relation_id,
            expected_revision_version=payload.expected_revision_version,
            resolution_status=payload.resolution_status,
            decision_note=payload.decision_note,
            operation_intent_id=payload.operation_intent_id,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            request_id=request.state.request_id,
        )
        return _revision_response(revision)

    @router.post(
        "/place-revisions/{revision_id}/relations/confirm-none",
        response_model=responses.PlaceRevision,
        response_model_exclude_unset=True,
    )
    def confirm_no_place_relations(
        revision_id: str,
        payload: ConfirmNoRelationsInput,
        request: Request,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        revision = review_workflow.confirm_no_relations(
            current,
            revision_id=revision_id,
            expected_revision_number=payload.expected_revision_number,
            expected_revision_version=payload.expected_revision_version,
            operation_intent_id=payload.operation_intent_id,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            request_id=request.state.request_id,
        )
        return _revision_response(revision)

    @router.get(
        "/place-revisions/{revision_id}/time-preview",
        response_model=responses.PlaceTimePreview,
        response_model_exclude_unset=True,
    )
    def preview_place_revision_time(
        revision_id: str,
        service_date: date = Query(...),
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        return review_workflow.preview_time(
            current, revision_id=revision_id, service_date=service_date
        )

    @router.post(
        "/place-revisions/{revision_id}/evidence/{evidence_kind}/{evidence_id}/review",
        response_model=responses.PlaceRevision,
        response_model_exclude_unset=True,
    )
    def review_place_evidence(
        revision_id: str,
        evidence_kind: Annotated[
            str,
            Path(pattern=("^(geometry|access_point|time_rule|closure|date_exception|relation)$")),
        ],
        evidence_id: str,
        payload: ReviewPlaceEvidenceInput,
        request: Request,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        revision = review_workflow.review_evidence(
            current,
            revision_id=revision_id,
            evidence_kind=evidence_kind,
            evidence_id=evidence_id,
            review_status=payload.review_status,
            operation_intent_id=payload.operation_intent_id,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            request_id=request.state.request_id,
        )
        return _revision_response(revision)
