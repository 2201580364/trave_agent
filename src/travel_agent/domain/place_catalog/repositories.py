"""Repository contract for the versioned place catalog."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from .entities import (
    Place,
    PlaceAccessPoint,
    PlaceClosure,
    PlaceDateException,
    PlaceGeometry,
    PlaceRelation,
    PlaceRevision,
    PlaceSourceRecord,
    PlaceTimeRule,
    SelectionExclusionGroup,
    SelectionExclusionMember,
    SolverPlaceProjection,
)
from .evidence import PlaceRevisionEvidence
from .projection import ProjectionPublicationContext


class PlaceCatalogRepository(Protocol):
    def add_place(self, place: Place) -> None: ...
    def add_source_record(self, record: PlaceSourceRecord) -> None: ...
    def add_revision(self, revision: PlaceRevision) -> None: ...
    def add_geometry(self, geometry: PlaceGeometry) -> None: ...
    def add_access_point(self, access_point: PlaceAccessPoint) -> None: ...
    def create_geometry(
        self,
        geometry: PlaceGeometry,
        *,
        expected_revision_version: int,
    ) -> PlaceRevision: ...
    def create_access_point(
        self,
        access_point: PlaceAccessPoint,
        *,
        expected_revision_version: int,
    ) -> PlaceRevision: ...
    def update_geometry(
        self,
        geometry: PlaceGeometry,
        *,
        expected_revision_version: int,
    ) -> PlaceRevision: ...
    def update_access_point(
        self,
        access_point: PlaceAccessPoint,
        *,
        expected_revision_version: int,
    ) -> PlaceRevision: ...
    def retire_geometry(
        self,
        geometry_id: str,
        *,
        place_revision_id: str,
        expected_revision_version: int,
    ) -> PlaceRevision: ...
    def retire_access_point(
        self,
        access_point_id: str,
        *,
        place_revision_id: str,
        expected_revision_version: int,
    ) -> PlaceRevision: ...
    def review_evidence(
        self,
        *,
        revision_id: str,
        evidence_kind: str,
        evidence_id: str,
        review_status: str,
        reviewed_at: datetime,
    ) -> PlaceRevision: ...
    def add_time_rule(self, rule: PlaceTimeRule) -> None: ...
    def add_closure(self, closure: PlaceClosure) -> None: ...
    def add_date_exception(self, exception: PlaceDateException) -> None: ...
    def add_relation(self, relation: PlaceRelation) -> None: ...
    def add_exclusion_group(self, group: SelectionExclusionGroup) -> None: ...
    def add_exclusion_member(self, member: SelectionExclusionMember) -> None: ...
    def add_projection(self, projection: SolverPlaceProjection) -> None: ...
    def get_place(self, place_id: str) -> Place | None: ...
    def get_revision(self, place_revision_id: str) -> PlaceRevision | None: ...
    def get_projection(self, projection_id: str) -> SolverPlaceProjection | None: ...
    def get_projection_for_revision(
        self, place_revision_id: str
    ) -> SolverPlaceProjection | None: ...
    def load_revision_evidence(
        self, place_revision_id: str
    ) -> PlaceRevisionEvidence | None: ...
    def load_publication_context(
        self, projection_id: str
    ) -> ProjectionPublicationContext | None: ...
    def publish_projection(
        self, projection_id: str, *, published_at: datetime
    ) -> SolverPlaceProjection: ...
