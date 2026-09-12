"""Narrow infrastructure ports for place catalog read operations (S7-3)."""

from __future__ import annotations

from typing import Protocol

from travel_agent.domain.place_catalog import (
    Place,
    PlaceRevision,
    PlaceRevisionEvidence,
    PublicationBatch,
    ResearchSnapshot,
    SolverPlaceProjection,
)


class PlaceCatalogReadPort(Protocol):
    def get_place(self, place_id: str) -> Place | None: ...
    def get_revision(self, place_revision_id: str) -> PlaceRevision | None: ...
    def get_projection(self, projection_id: str) -> SolverPlaceProjection | None: ...
    def get_projection_for_revision(
        self, place_revision_id: str
    ) -> SolverPlaceProjection | None: ...
    def load_revision_evidence(self, place_revision_id: str) -> PlaceRevisionEvidence | None: ...
    def get_publication_batch(self, batch_id: str) -> PublicationBatch | None: ...
    def get_research_snapshot(self, snapshot_id: str) -> ResearchSnapshot | None: ...
    def list_research_snapshots(
        self, *, city_id: str | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[ResearchSnapshot, ...]: ...
