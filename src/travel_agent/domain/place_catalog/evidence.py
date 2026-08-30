"""Read-only evidence assembled for an administrator's Revision review."""

from __future__ import annotations

from dataclasses import dataclass

from .entities import (
    PlaceAccessPoint,
    PlaceGeometry,
    PlaceRevision,
    PlaceSourceRecord,
    SolverPlaceProjection,
)


@dataclass(frozen=True, slots=True)
class PlaceRevisionEvidence:
    """All O04 evidence attached to one immutable Revision.

    A projection is optional because candidate Revisions can be inspected before
    a solver projection has been prepared. Child records remain scoped by the
    Revision ID and are never inferred from another Revision.
    """

    revision: PlaceRevision
    source_records: tuple[PlaceSourceRecord, ...]
    geometries: tuple[PlaceGeometry, ...]
    access_points: tuple[PlaceAccessPoint, ...]
    projection: SolverPlaceProjection | None
    missing_source_record_ids: tuple[str, ...] = ()
