"""Geometry and access-point review use cases (H3/S7-1)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from decimal import Decimal

from travel_agent.application.common.clock import Clock
from travel_agent.application.common.errors import ResourceNotFoundError
from travel_agent.application.planning.ports import IdGenerator
from travel_agent.domain.admin import AdminPrincipal
from travel_agent.domain.place_catalog import (
    PlaceAccessPoint,
    PlaceGeometry,
    PlaceRevision,
)

from .review_evidence import EvidenceMutationSupport
from .review_ports import GeometryReviewUnitOfWork as ReviewUnitOfWork


class ReviewGeometryService(EvidenceMutationSupport[ReviewUnitOfWork]):
    def __init__(
        self, uow_factory: Callable[[], ReviewUnitOfWork], clock: Clock, ids: IdGenerator
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._ids = ids

    def create_geometry(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        expected_revision_version: int,
        geometry_kind: str,
        geometry: dict[str, object],
        source_record_id: str,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        geometry_id = self._ids.new_id("geometry")
        payload = {
            "revision_id": revision_id,
            "expected_revision_version": expected_revision_version,
            "geometry_kind": geometry_kind,
            "geometry": geometry,
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
            action="PLACE_GEOMETRY_CREATED",
            target_id=geometry_id,
            payload=payload,
            mutate=lambda uow, revision: (
                uow.catalog.create_geometry(
                    PlaceGeometry(
                        geometry_id,
                        revision_id,
                        geometry_kind,
                        geometry,
                        source_record_id,
                        "candidate",
                        True,
                        self._clock.now(),
                    ),
                    expected_revision_version=expected_revision_version,
                ),
                geometry_id,
            ),
        )

    def update_geometry(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        geometry_id: str,
        expected_revision_version: int,
        geometry_kind: str,
        geometry: dict[str, object],
        source_record_id: str,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        payload = {
            "revision_id": revision_id,
            "geometry_id": geometry_id,
            "expected_revision_version": expected_revision_version,
            "geometry_kind": geometry_kind,
            "geometry": geometry,
            "source_record_id": source_record_id,
        }

        def mutate(uow: ReviewUnitOfWork, revision: PlaceRevision) -> tuple[PlaceRevision, str]:
            evidence = uow.catalog.load_revision_evidence(revision_id)
            if evidence is None:
                raise ResourceNotFoundError
            current = next(
                (item for item in evidence.geometries if item.geometry_id == geometry_id),
                None,
            )
            if current is None:
                raise ResourceNotFoundError
            updated = replace(
                current,
                geometry_kind=geometry_kind,
                geometry=geometry,
                source_record_id=source_record_id,
                review_status="candidate",
                active=True,
                reviewed_at=None,
            )
            return (
                uow.catalog.update_geometry(
                    updated,
                    expected_revision_version=expected_revision_version,
                ),
                geometry_id,
            )

        return self._mutate_evidence(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
            action="PLACE_GEOMETRY_UPDATED",
            target_id=geometry_id,
            payload=payload,
            mutate=mutate,
        )

    def retire_geometry(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        geometry_id: str,
        expected_revision_version: int,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        payload = {
            "revision_id": revision_id,
            "geometry_id": geometry_id,
            "expected_revision_version": expected_revision_version,
        }
        return self._mutate_evidence(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
            action="PLACE_GEOMETRY_RETIRED",
            target_id=geometry_id,
            payload=payload,
            mutate=lambda uow, _revision: (
                uow.catalog.retire_geometry(
                    geometry_id,
                    place_revision_id=revision_id,
                    expected_revision_version=expected_revision_version,
                ),
                geometry_id,
            ),
        )

    def create_access_point(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        expected_revision_version: int,
        access_point_kind: str,
        name: str,
        lat: Decimal,
        lng: Decimal,
        source_record_id: str,
        fetched_at: datetime | None,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        access_point_id = self._ids.new_id("access_point")
        payload = {
            "revision_id": revision_id,
            "expected_revision_version": expected_revision_version,
            "access_point_kind": access_point_kind,
            "name": name,
            "lat": str(lat),
            "lng": str(lng),
            "source_record_id": source_record_id,
            "fetched_at": fetched_at.isoformat() if fetched_at else None,
        }
        return self._mutate_evidence(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
            action="PLACE_ACCESS_POINT_CREATED",
            target_id=access_point_id,
            payload=payload,
            mutate=lambda uow, _revision: (
                uow.catalog.create_access_point(
                    PlaceAccessPoint(
                        access_point_id,
                        revision_id,
                        access_point_kind,
                        name,
                        lat,
                        lng,
                        source_record_id,
                        "candidate",
                        True,
                        fetched_at,
                        None,
                        self._clock.now(),
                    ),
                    expected_revision_version=expected_revision_version,
                ),
                access_point_id,
            ),
        )

    def update_access_point(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        access_point_id: str,
        expected_revision_version: int,
        access_point_kind: str,
        name: str,
        lat: Decimal,
        lng: Decimal,
        source_record_id: str,
        fetched_at: datetime | None,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        payload = {
            "revision_id": revision_id,
            "access_point_id": access_point_id,
            "expected_revision_version": expected_revision_version,
            "access_point_kind": access_point_kind,
            "name": name,
            "lat": str(lat),
            "lng": str(lng),
            "source_record_id": source_record_id,
            "fetched_at": fetched_at.isoformat() if fetched_at else None,
        }

        def mutate(uow: ReviewUnitOfWork, _revision: PlaceRevision) -> tuple[PlaceRevision, str]:
            evidence = uow.catalog.load_revision_evidence(revision_id)
            if evidence is None:
                raise ResourceNotFoundError
            current = next(
                (
                    item
                    for item in evidence.access_points
                    if item.access_point_id == access_point_id
                ),
                None,
            )
            if current is None:
                raise ResourceNotFoundError
            updated = replace(
                current,
                access_point_kind=access_point_kind,
                name=name,
                lat=lat,
                lng=lng,
                source_record_id=source_record_id,
                review_status="candidate",
                active=True,
                fetched_at=fetched_at,
                reviewed_at=None,
            )
            return (
                uow.catalog.update_access_point(
                    updated,
                    expected_revision_version=expected_revision_version,
                ),
                access_point_id,
            )

        return self._mutate_evidence(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
            action="PLACE_ACCESS_POINT_UPDATED",
            target_id=access_point_id,
            payload=payload,
            mutate=mutate,
        )

    def retire_access_point(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        access_point_id: str,
        expected_revision_version: int,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        payload = {
            "revision_id": revision_id,
            "access_point_id": access_point_id,
            "expected_revision_version": expected_revision_version,
        }
        return self._mutate_evidence(
            principal,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
            operation_intent_id=operation_intent_id,
            reason_code=reason_code,
            reason_text=reason_text,
            request_id=request_id,
            action="PLACE_ACCESS_POINT_RETIRED",
            target_id=access_point_id,
            payload=payload,
            mutate=lambda uow, _revision: (
                uow.catalog.retire_access_point(
                    access_point_id,
                    place_revision_id=revision_id,
                    expected_revision_version=expected_revision_version,
                ),
                access_point_id,
            ),
        )
