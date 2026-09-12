"""Publication, snapshot and projection repository boundary (S7-3)."""

from __future__ import annotations


class SqlAlchemyPlaceCatalogPublicationRepository:
    def __init__(self, owner):
        self._owner = owner

    def add_publication_batch(self, value):
        return self._owner.add_publication_batch(value)

    def update_publication_batch(self, value):
        return self._owner.update_publication_batch(value)

    def add_publication_batch_item(self, value):
        return self._owner.add_publication_batch_item(value)

    def list_publication_batch_items(self, batch_id):
        return self._owner.list_publication_batch_items(batch_id)

    def update_publication_batch_item(self, value):
        return self._owner.update_publication_batch_item(value)

    def add_research_snapshot(self, value):
        return self._owner.add_research_snapshot(value)

    def load_publication_context(self, projection_id):
        return self._owner.load_publication_context(projection_id)

    def publish_projection(self, projection_id, *, published_at):
        return self._owner.publish_projection(projection_id, published_at=published_at)
