"""Review evidence and relation repository boundary (S7-3)."""

from __future__ import annotations

from datetime import datetime

from travel_agent.domain.place_catalog import PlaceRevision


class SqlAlchemyPlaceCatalogReviewRepository:
    def __init__(self, owner):
        self._owner = owner

    def review_evidence(
        self,
        *,
        revision_id: str,
        evidence_kind: str,
        evidence_id: str,
        review_status: str,
        reviewed_at: datetime,
        place_id: str | None = None,
    ) -> PlaceRevision:
        return self._owner.review_evidence(
            revision_id=revision_id,
            evidence_kind=evidence_kind,
            evidence_id=evidence_id,
            review_status=review_status,
            reviewed_at=reviewed_at,
            place_id=place_id,
        )

    def update_relation(
        self, relation, *, revision_id: str, expected_revision_version: int
    ) -> PlaceRevision:
        return self._owner.update_relation(
            relation, revision_id=revision_id, expected_revision_version=expected_revision_version
        )
