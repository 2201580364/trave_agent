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
    PublicationBatch,
    PublicationBatchItem,
    ResearchSnapshot,
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
    def create_time_rule(
        self,
        rule: PlaceTimeRule,
        *,
        expected_revision_version: int,
    ) -> PlaceRevision: ...
    def update_time_rule(
        self,
        rule: PlaceTimeRule,
        *,
        expected_revision_version: int,
    ) -> PlaceRevision: ...
    def retire_time_rule(
        self,
        time_rule_id: str,
        *,
        place_revision_id: str,
        expected_revision_version: int,
    ) -> PlaceRevision: ...
    def create_closure(
        self,
        closure: PlaceClosure,
        *,
        expected_revision_version: int,
    ) -> PlaceRevision: ...
    def update_closure(
        self,
        closure: PlaceClosure,
        *,
        expected_revision_version: int,
    ) -> PlaceRevision: ...
    def retire_closure(
        self,
        closure_id: str,
        *,
        place_revision_id: str,
        expected_revision_version: int,
    ) -> PlaceRevision: ...
    def create_date_exception(
        self,
        exception: PlaceDateException,
        *,
        expected_revision_version: int,
    ) -> PlaceRevision: ...
    def update_date_exception(
        self,
        exception: PlaceDateException,
        *,
        expected_revision_version: int,
    ) -> PlaceRevision: ...
    def retire_date_exception(
        self,
        date_exception_id: str,
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
        place_id: str | None = None,
    ) -> PlaceRevision: ...
    def add_time_rule(self, rule: PlaceTimeRule) -> None: ...
    def add_closure(self, closure: PlaceClosure) -> None: ...
    def add_date_exception(self, exception: PlaceDateException) -> None: ...
    def add_relation(self, relation: PlaceRelation) -> None: ...
    def update_relation(self, relation: PlaceRelation, *, revision_id: str, expected_revision_version: int) -> PlaceRevision: ...
    def add_publication_batch(self, batch: PublicationBatch) -> None: ...
    def add_publication_batch_item(self, item: PublicationBatchItem) -> None: ...
    def list_publication_batch_items(self, batch_id: str) -> tuple[PublicationBatchItem, ...]: ...
    def update_publication_batch_item(self, item: PublicationBatchItem) -> None: ...
    def update_publication_batch(self, batch: PublicationBatch) -> None: ...
    def add_research_snapshot(self, snapshot: ResearchSnapshot) -> None: ...
    def get_publication_batch(self, batch_id: str) -> PublicationBatch | None: ...
    def get_research_snapshot(self, snapshot_id: str) -> ResearchSnapshot | None: ...
    def list_research_snapshots(self, *, city_id: str | None = None, limit: int = 50, offset: int = 0) -> tuple[ResearchSnapshot, ...]: ...
    def add_exclusion_group(self, group: SelectionExclusionGroup) -> None: ...
    def add_exclusion_member(self, member: SelectionExclusionMember) -> None: ...
    def add_projection(self, projection: SolverPlaceProjection) -> None: ...
    def get_place(self, place_id: str) -> Place | None: ...
    def get_revision(self, place_revision_id: str) -> PlaceRevision | None: ...
    def get_projection(self, projection_id: str) -> SolverPlaceProjection | None: ...
    def get_projection_for_revision(
        self, place_revision_id: str
    ) -> SolverPlaceProjection | None: ...
    def next_solver_node_id(self, data_snapshot_version: str, *, minimum: int = 1) -> int: ...
    def load_revision_evidence(
        self, place_revision_id: str
    ) -> PlaceRevisionEvidence | None: ...
    def load_publication_context(
        self, projection_id: str
    ) -> ProjectionPublicationContext | None: ...
    def publish_projection(
        self, projection_id: str, *, published_at: datetime
    ) -> SolverPlaceProjection: ...
