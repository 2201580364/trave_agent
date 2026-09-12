"""Source evidence repository boundary (S7-3)."""

from __future__ import annotations

from travel_agent.domain.place_catalog import PlaceRevision, PlaceSourceRecord


class SqlAlchemyPlaceCatalogSourceRepository:
    def __init__(self, owner):
        self._owner = owner

    def create_source_record(
        self, record: PlaceSourceRecord, *, revision_id: str, expected_revision_version: int
    ) -> PlaceRevision:
        return self._owner.create_source_record(
            record, revision_id=revision_id, expected_revision_version=expected_revision_version
        )

    def detach_source_record(
        self, source_record_id: str, *, revision_id: str, expected_revision_version: int
    ) -> PlaceRevision:
        return self._owner.detach_source_record(
            source_record_id,
            revision_id=revision_id,
            expected_revision_version=expected_revision_version,
        )

    def source_record_references(
        self, source_record_id: str, *, revision_id: str
    ) -> tuple[str, ...]:
        return self._owner.source_record_references(source_record_id, revision_id=revision_id)
