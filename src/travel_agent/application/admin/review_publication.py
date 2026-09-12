"""Publication and research snapshot service (H3/S7-1)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from travel_agent.application.common.clock import Clock
from travel_agent.application.common.errors import ResourceNotFoundError
from travel_agent.application.planning.ports import IdGenerator
from travel_agent.domain.admin import AdminPrincipal
from travel_agent.domain.place_catalog import (
    PlaceRevision,
    ProjectionPublicationContext,
    ProjectionPublicationError,
    PublicationBatch,
    PublicationBatchItem,
    ResearchSnapshot,
    SolverPlaceProjection,
    evaluate_projection_publication,
)
from travel_agent.domain.place_catalog.session_payload import build_fixed_session_payload

from .errors import (
    AdminOperationIntentConflictError,
    ProjectionPreparationRejectedError,
    PublicationGateRejectedError,
    ReviewRevisionNotApprovableError,
)
from .review_ports import PublicationUnitOfWork as ReviewUnitOfWork
from .review_support import ReviewSupport, _digest, _revision_digest


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


class PublicationService(ReviewSupport):
    def __init__(
        self, uow_factory: Callable[[], ReviewUnitOfWork], clock: Clock, ids: IdGenerator
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._ids = ids

    def publication_check(self, principal: AdminPrincipal, *, revision_id: str) -> tuple[str, ...]:
        self._require(principal, "place:publication:check")
        with self._uow_factory() as uow:
            revision = uow.reviews.get_revision(revision_id)
            if revision is None:
                raise ResourceNotFoundError
            projection = uow.catalog.get_projection_for_revision(revision_id)
            if projection is None:
                return ("PROJECTION_NOT_FOUND",)
            context = uow.catalog.load_publication_context(projection.projection_id)
            if context is None:
                return ("PROJECTION_DEPENDENCY_MISSING",)
            return evaluate_projection_publication(context)

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
        """Create an auditable candidate projection from a verified revision."""
        self._require(principal, "place:publication:write")
        reason_text = self._validate_reason(reason_code, reason_text)
        digest = _digest(
            {
                "revision_id": revision_id,
                "data_snapshot_version": data_snapshot_version,
                "solver_node_id": solver_node_id,
                "reason_code": reason_code,
                "reason_text": reason_text,
            }
        )
        with self._uow_factory() as uow:
            existing = self._replay(uow, operation_intent_id, digest)
            if existing is not None:
                projection = uow.catalog.get_projection(existing.target_id)
                if projection is None:
                    raise ResourceNotFoundError
                return projection
            actor = self._actor(uow, principal)
            revision = uow.reviews.get_revision(revision_id)
            evidence = uow.catalog.load_revision_evidence(revision_id)
            place = uow.catalog.get_place(revision.place_id) if revision else None
            if revision is None or evidence is None or place is None:
                raise ResourceNotFoundError
            if revision.lifecycle_status != "human_verified":
                raise ReviewRevisionNotApprovableError(not_candidate=True)
            if solver_node_id is None:
                solver_node_id = uow.catalog.next_solver_node_id(data_snapshot_version)
            elif solver_node_id <= 0:
                raise ValueError("solver node id must be positive")
            if uow.catalog.get_projection_for_revision(revision_id) is not None:
                raise ProjectionPreparationRejectedError(("PROJECTION_ALREADY_EXISTS",))
            access_points = tuple(
                item
                for item in evidence.access_points
                if item.active and item.review_status == "human_verified"
            )
            if not access_points:
                raise ProjectionPreparationRejectedError(("MISSING_VERIFIED_ACCESS_POINT",))
            arrival = min(
                access_points,
                key=lambda item: (
                    _access_rank(item.access_point_kind, False),
                    item.access_point_id,
                ),
            )
            departure = min(
                access_points,
                key=lambda item: (_access_rank(item.access_point_kind, True), item.access_point_id),
            )
            payload = {
                "attraction_id": revision.place_id,
                "name": revision.canonical_name,
                "suggested_duration": revision.duration_recommended,
                "close_days": sorted({item.weekday for item in evidence.closures if item.active}),
                "is_always_open": revision.is_always_open,
                "is_indoor": revision.indoor_outdoor == "indoor",
                "energy_level": revision.energy_level,
                "data_verified": False,
            }
            if revision.place_kind == "show":
                payload["fixed_sessions"] = build_fixed_session_payload(evidence)
            projection = SolverPlaceProjection(
                self._ids.new_id("solver_projection"),
                "solver-place-projection-v1",
                data_snapshot_version,
                revision.place_id,
                revision_id,
                solver_node_id,
                revision.place_kind,
                revision.geometry_kind,
                arrival.access_point_id,
                departure.access_point_id,
                revision.duration_min,
                revision.duration_recommended,
                revision.duration_max,
                revision.internal_travel_min,
                payload,
                "0" * 64,
                "candidate",
                (),
                self._clock.now(),
            )
            from travel_agent.domain.place_catalog import canonical_projection_sha256

            projection = replace(
                projection, projection_hash=canonical_projection_sha256(projection)
            )
            context = ProjectionPublicationContext(
                place,
                revision,
                evidence.source_records,
                evidence.geometries,
                evidence.access_points,
                evidence.time_rules,
                evidence.relations,
                projection,
            )
            reasons = evaluate_projection_publication(context)
            if not reasons:
                payload["data_verified"] = True
                projection = replace(
                    projection,
                    solver_payload=payload,
                    projection_hash=canonical_projection_sha256(
                        replace(projection, solver_payload=payload)
                    ),
                )
            projection = replace(projection, gate_reason_codes=reasons)
            uow.catalog.add_projection(projection)
            uow.audits.add(
                self._event(
                    actor,
                    action="SOLVER_PROJECTION_PREPARED",
                    target_type="solver_projection",
                    target_id=projection.projection_id,
                    target_revision=str(revision.revision_number),
                    before_digest=None,
                    after_digest=_digest(
                        {"revision_id": revision_id, "gate_reason_codes": reasons}
                    ),
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=digest,
                )
            )
            uow.commit()
            return projection

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
        self._require(principal, "place:publication:write")
        reason_text = self._validate_reason(reason_code, reason_text)
        now = self._clock.now()
        with self._uow_factory() as uow:
            actor = self._actor(uow, principal)
            revision = uow.reviews.get_revision(revision_id)
            projection = uow.catalog.get_projection_for_revision(revision_id)
            if revision is None or projection is None:
                raise ResourceNotFoundError
            operation_digest = _digest(
                {
                    "revision_id": revision_id,
                    "projection_id": projection.projection_id,
                    "reason_code": reason_code,
                    "reason_text": reason_text,
                }
            )
            existing = self._replay(uow, operation_intent_id, operation_digest)
            if existing is not None:
                return projection
            context = uow.catalog.load_publication_context(projection.projection_id)
            if context is None:
                raise PublicationGateRejectedError(("PROJECTION_DEPENDENCY_MISSING",))
            reasons = evaluate_projection_publication(context)
            if reasons:
                raise PublicationGateRejectedError(reasons)
            before_digest = _revision_digest(revision)
            try:
                published = uow.catalog.publish_projection(
                    projection.projection_id, published_at=now
                )
            except ProjectionPublicationError as exc:
                raise PublicationGateRejectedError(exc.reason_codes) from exc
            uow.audits.add(
                self._event(
                    actor,
                    action="PLACE_REVISION_PUBLISHED",
                    target_type="place_revision",
                    target_id=revision_id,
                    target_revision=str(revision.revision_number),
                    before_digest=before_digest,
                    after_digest=_digest(
                        {"projection_id": published.projection_id, "status": published.status}
                    ),
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=operation_digest,
                )
            )
            uow.commit()
            return published

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
        """Create an auditable, non-mutating publication batch preview."""
        self._require(principal, "place:publication:write")
        reason_text = self._validate_reason(reason_code, reason_text)
        normalized_ids = tuple(dict.fromkeys(revision_ids))
        if not normalized_ids or len(normalized_ids) > 500:
            raise ValueError("publication batch must contain 1 to 500 revisions")
        operation_digest = _digest(
            {
                "city_id": city_id,
                "revision_ids": normalized_ids,
                "reason_code": reason_code,
                "reason_text": reason_text,
            }
        )
        with self._uow_factory() as uow:
            existing = uow.audits.get_by_operation_intent(operation_intent_id)
            if existing is not None:
                if existing.operation_digest != operation_digest:
                    raise AdminOperationIntentConflictError
                batch = uow.catalog.get_publication_batch(existing.target_id)
                if batch is None:
                    raise ResourceNotFoundError
                return self._publication_batch_response(uow, batch)
            actor = self._actor(uow, principal)
            batch = PublicationBatch(
                self._ids.new_id("publication_batch"),
                city_id,
                operation_intent_id,
                actor.admin_actor_id,
                self._clock.now(),
                "preview",
            )
            uow.catalog.add_publication_batch(batch)
            for revision_id in normalized_ids:
                revision = uow.reviews.get_revision(revision_id)
                status = "blocked"
                reasons: tuple[str, ...]
                projection_id: str | None = None
                if revision is None:
                    reasons = ("REVISION_NOT_FOUND",)
                elif (
                    revision.place_id
                    and (place := uow.catalog.get_place(revision.place_id)) is not None
                    and place.city_id != city_id
                ):
                    reasons = ("REVISION_CITY_MISMATCH",)
                else:
                    projection = uow.catalog.get_projection_for_revision(revision_id)
                    projection_id = projection.projection_id if projection else None
                    if projection is None:
                        reasons = ("PROJECTION_NOT_FOUND",)
                    else:
                        context = uow.catalog.load_publication_context(projection.projection_id)
                        reasons = (
                            ("PROJECTION_DEPENDENCY_MISSING",)
                            if context is None
                            else evaluate_projection_publication(context)
                        )
                        status = "publishable" if not reasons else "blocked"
                uow.catalog.add_publication_batch_item(
                    PublicationBatchItem(
                        self._ids.new_id("publication_batch_item"),
                        batch.batch_id,
                        revision_id,
                        status,
                        tuple(reasons),
                        projection_id,
                    )
                )
            uow.audits.add(
                self._event(
                    actor,
                    action="PUBLICATION_BATCH_PREVIEWED",
                    target_type="publication_batch",
                    target_id=batch.batch_id,
                    target_revision=None,
                    before_digest=None,
                    after_digest=_digest(
                        {"batch_id": batch.batch_id, "revision_ids": normalized_ids}
                    ),
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=operation_digest,
                )
            )
            uow.commit()
            return self._publication_batch_response(uow, batch)

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
        self._require(principal, "place:publication:write")
        reason_text = self._validate_reason(reason_code, reason_text)
        with self._uow_factory() as uow:
            batch = uow.catalog.get_publication_batch(batch_id)
            if batch is None:
                raise ResourceNotFoundError
            items = uow.catalog.list_publication_batch_items(batch_id)
            if batch.snapshot_id:
                snapshot = uow.catalog.get_research_snapshot(batch.snapshot_id)
                return {
                    "batch": self._publication_batch_response(uow, batch),
                    "snapshot": _snapshot_response(snapshot),
                    "reused": True,
                }
            operation_digest = _digest(
                {
                    "batch_id": batch_id,
                    "item_ids": tuple(item.batch_item_id for item in items),
                    "reason_code": reason_code,
                    "reason_text": reason_text,
                }
            )
            existing = uow.audits.get_by_operation_intent(operation_intent_id)
            if existing is not None:
                if existing.operation_digest != operation_digest:
                    raise AdminOperationIntentConflictError
                if batch.snapshot_id:
                    snapshot = uow.catalog.get_research_snapshot(batch.snapshot_id)
                    if snapshot is not None:
                        return {
                            "batch": self._publication_batch_response(uow, batch),
                            "snapshot": _snapshot_response(snapshot),
                            "reused": True,
                        }
                return {
                    "batch": self._publication_batch_response(uow, batch),
                    "snapshot": None,
                    "reused": True,
                }
            actor = self._actor(uow, principal)
            published: list[SolverPlaceProjection] = []
            for item in items:
                if item.status not in {"publishable", "pending"}:
                    continue
                revision = uow.reviews.get_revision(item.place_revision_id)
                projection = uow.catalog.get_projection_for_revision(item.place_revision_id)
                if revision is None or projection is None:
                    updated = replace(item, status="failed", reason_codes=("PROJECTION_NOT_FOUND",))
                    uow.catalog.update_publication_batch_item(updated)
                    continue
                context = uow.catalog.load_publication_context(projection.projection_id)
                reasons = (
                    ("PROJECTION_DEPENDENCY_MISSING",)
                    if context is None
                    else evaluate_projection_publication(context)
                )
                if reasons:
                    uow.catalog.update_publication_batch_item(
                        replace(
                            item,
                            status="blocked",
                            reason_codes=reasons,
                            projection_id=projection.projection_id,
                        )
                    )
                    continue
                try:
                    result = uow.catalog.publish_projection(
                        projection.projection_id, published_at=self._clock.now()
                    )
                except ProjectionPublicationError as exc:
                    uow.catalog.update_publication_batch_item(
                        replace(
                            item,
                            status="failed",
                            reason_codes=exc.reason_codes,
                            projection_id=projection.projection_id,
                        )
                    )
                    continue
                uow.catalog.update_publication_batch_item(
                    replace(
                        item,
                        status="published",
                        reason_codes=(),
                        projection_id=result.projection_id,
                        published_at=result.published_at,
                    )
                )
                published.append(result)
            if published:
                payload = {
                    "schema_version": "research_snapshot.v1",
                    "city_id": batch.city_id,
                    "items": [
                        _projection_snapshot_payload(item)
                        for item in sorted(
                            published,
                            key=lambda value: (
                                value.place_id,
                                value.place_revision_id,
                                value.projection_id,
                            ),
                        )
                    ],
                }
                content_sha256 = _digest(payload)
                snapshot = ResearchSnapshot(
                    self._ids.new_id("research_snapshot"),
                    f"research-{batch.city_id}-{content_sha256[:16]}",
                    batch.city_id,
                    content_sha256,
                    batch.batch_id,
                    payload,
                    self._clock.now(),
                    "published",
                )
                uow.catalog.add_research_snapshot(snapshot)
                batch = replace(
                    batch,
                    status="published"
                    if all(
                        item.status == "published"
                        for item in uow.catalog.list_publication_batch_items(batch_id)
                    )
                    else "partial_failed",
                    snapshot_id=snapshot.snapshot_id,
                )
            else:
                snapshot = None
                batch = replace(batch, status="failed")
            uow.catalog.update_publication_batch(batch)
            uow.audits.add(
                self._event(
                    actor,
                    action="PUBLICATION_BATCH_EXECUTED",
                    target_type="publication_batch",
                    target_id=batch.batch_id,
                    target_revision=None,
                    before_digest=None,
                    after_digest=_digest(
                        {"status": batch.status, "snapshot_id": batch.snapshot_id}
                    ),
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=operation_digest,
                )
            )
            uow.commit()
            return {
                "batch": self._publication_batch_response(uow, batch),
                "snapshot": _snapshot_response(snapshot) if snapshot else None,
                "reused": False,
            }

    def list_research_snapshots(
        self, principal: AdminPrincipal, *, city_id: str | None, limit: int, offset: int
    ) -> tuple[ResearchSnapshot, ...]:
        self._require(principal, "place:candidate:read")
        with self._uow_factory() as uow:
            return uow.catalog.list_research_snapshots(city_id=city_id, limit=limit, offset=offset)

    def get_research_snapshot(
        self, principal: AdminPrincipal, *, snapshot_id: str
    ) -> ResearchSnapshot:
        self._require(principal, "place:candidate:read")
        with self._uow_factory() as uow:
            snapshot = uow.catalog.get_research_snapshot(snapshot_id)
            if snapshot is None:
                raise ResourceNotFoundError
            return snapshot

    @staticmethod
    def _publication_batch_response(
        uow: ReviewUnitOfWork, batch: PublicationBatch
    ) -> dict[str, object]:
        items = uow.catalog.list_publication_batch_items(batch.batch_id)
        return {
            "batch_id": batch.batch_id,
            "city_id": batch.city_id,
            "operation_intent_id": batch.operation_intent_id,
            "status": batch.status,
            "snapshot_id": batch.snapshot_id,
            "created_at": batch.created_at.isoformat(),
            "items": [
                _batch_item_response(item, uow.reviews.get_revision(item.place_revision_id))
                for item in items
            ],
        }


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
