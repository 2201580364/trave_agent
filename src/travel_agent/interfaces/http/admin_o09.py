"""O09 publication and research snapshot routes."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request, status

from travel_agent.domain.admin import AdminPrincipal

from .admin import (
    ExecutePublicationBatchInput,
    PrepareProjectionInput,
    PreviewPublicationBatchInput,
    PublishPlaceRevisionInput,
    _snapshot_api_response,
)


def register_o09_routes(router: APIRouter, review_workflow, principal_dependency) -> None:
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
                projection.published_at.isoformat() if projection.published_at else None
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
        snapshots = review_workflow.list_research_snapshots(
            current, city_id=city_id, limit=limit, offset=offset
        )
        return {
            "items": [_snapshot_api_response(item, include_payload=False) for item in snapshots],
            "limit": limit,
            "offset": offset,
        }

    @router.get("/research-snapshots/{snapshot_id}")
    def get_research_snapshot(
        snapshot_id: str,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        return _snapshot_api_response(
            review_workflow.get_research_snapshot(current, snapshot_id=snapshot_id),
            include_payload=True,
        )
