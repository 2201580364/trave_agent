"""Publication, snapshot and projection repository boundary (S7-3)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from travel_agent.domain.place_catalog import (
    ProjectionPublicationContext,
    PublicationBatch,
    PublicationBatchItem,
    ResearchSnapshot,
    SolverPlaceProjection,
)

if TYPE_CHECKING:
    from .place_catalog import SqlAlchemyPlaceCatalogRepository


class SqlAlchemyPlaceCatalogPublicationRepository:
    def __init__(self, owner: SqlAlchemyPlaceCatalogRepository) -> None:
        self._owner = owner

    def add_publication_batch(self, value: PublicationBatch) -> None:
        return self._owner.add_publication_batch(value)

    def update_publication_batch(self, value: PublicationBatch) -> None:
        return self._owner.update_publication_batch(value)

    def add_publication_batch_item(self, value: PublicationBatchItem) -> None:
        return self._owner.add_publication_batch_item(value)

    def list_publication_batch_items(self, batch_id: str) -> tuple[PublicationBatchItem, ...]:
        return self._owner.list_publication_batch_items(batch_id)

    def update_publication_batch_item(self, value: PublicationBatchItem) -> None:
        return self._owner.update_publication_batch_item(value)

    def add_research_snapshot(self, value: ResearchSnapshot) -> None:
        return self._owner.add_research_snapshot(value)

    def load_publication_context(self, projection_id: str) -> ProjectionPublicationContext | None:
        return self._owner.load_publication_context(projection_id)

    def publish_projection(
        self, projection_id: str, *, published_at: datetime
    ) -> SolverPlaceProjection:
        return self._owner.publish_projection(projection_id, published_at=published_at)
