"""Geometry, access point and time evidence repository boundary (S7-3)."""

from __future__ import annotations

from travel_agent.domain.place_catalog import (
    PlaceAccessPoint,
    PlaceGeometry,
    PlaceRevision,
    PlaceTimeRule,
)


class SqlAlchemyPlaceCatalogEvidenceRepository:
    def __init__(self, owner):
        self._owner = owner

    def create_geometry(
        self, value: PlaceGeometry, *, expected_revision_version: int
    ) -> PlaceRevision:
        return self._owner.create_geometry(
            value, expected_revision_version=expected_revision_version
        )

    def update_geometry(
        self, value: PlaceGeometry, *, expected_revision_version: int
    ) -> PlaceRevision:
        return self._owner.update_geometry(
            value, expected_revision_version=expected_revision_version
        )

    def retire_geometry(
        self, evidence_id: str, *, place_revision_id: str, expected_revision_version: int
    ) -> PlaceRevision:
        return self._owner.retire_geometry(
            evidence_id,
            place_revision_id=place_revision_id,
            expected_revision_version=expected_revision_version,
        )

    def create_access_point(
        self, value: PlaceAccessPoint, *, expected_revision_version: int
    ) -> PlaceRevision:
        return self._owner.create_access_point(
            value, expected_revision_version=expected_revision_version
        )

    def update_access_point(
        self, value: PlaceAccessPoint, *, expected_revision_version: int
    ) -> PlaceRevision:
        return self._owner.update_access_point(
            value, expected_revision_version=expected_revision_version
        )

    def retire_access_point(
        self, evidence_id: str, *, place_revision_id: str, expected_revision_version: int
    ) -> PlaceRevision:
        return self._owner.retire_access_point(
            evidence_id,
            place_revision_id=place_revision_id,
            expected_revision_version=expected_revision_version,
        )

    def create_time_rule(
        self, value: PlaceTimeRule, *, expected_revision_version: int
    ) -> PlaceRevision:
        return self._owner.create_time_rule(
            value, expected_revision_version=expected_revision_version
        )

    def update_time_rule(
        self, value: PlaceTimeRule, *, expected_revision_version: int
    ) -> PlaceRevision:
        return self._owner.update_time_rule(
            value, expected_revision_version=expected_revision_version
        )

    def delete_time_rule(
        self, evidence_id: str, *, place_revision_id: str, expected_revision_version: int
    ) -> PlaceRevision:
        return self._owner.delete_time_rule(
            evidence_id,
            place_revision_id=place_revision_id,
            expected_revision_version=expected_revision_version,
        )

    def retire_time_rule(
        self, evidence_id: str, *, place_revision_id: str, expected_revision_version: int
    ) -> PlaceRevision:
        return self._owner.retire_time_rule(
            evidence_id,
            place_revision_id=place_revision_id,
            expected_revision_version=expected_revision_version,
        )
