"""Read-only catalog queries sharing the caller transaction (H3/S7-3)."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from travel_agent.domain.place_catalog import (
    Place,
    PlaceRevision,
    PlaceRevisionEvidence,
    PublicationBatch,
    ResearchSnapshot,
    SolverPlaceProjection,
)

from .place_catalog import (
    PlaceAccessPointRow,
    PlaceClosureRow,
    PlaceDateExceptionRow,
    PlaceGeometryRow,
    PlaceRelationRow,
    PlaceRevisionRow,
    PlaceRow,
    PlaceSourceRecordRow,
    PlaceTimeRuleRow,
    PublicationBatchRow,
    ResearchSnapshotRow,
    SolverPlaceProjectionRow,
    _access_point_from_row,
    _closure_from_row,
    _date_exception_from_row,
    _geometry_from_row,
    _place_from_row,
    _projection_from_row,
    _publication_batch_from_row,
    _relation_from_row,
    _research_snapshot_from_row,
    _revision_from_row,
    _source_record_from_row,
    _time_rule_from_row,
)


class SqlAlchemyPlaceCatalogReadRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_publication_batch(self, batch_id: str) -> PublicationBatch | None:
        row = self._session.get(PublicationBatchRow, batch_id)
        return _publication_batch_from_row(row) if row is not None else None

    def get_research_snapshot(self, snapshot_id: str) -> ResearchSnapshot | None:
        row = self._session.get(ResearchSnapshotRow, snapshot_id)
        return _research_snapshot_from_row(row) if row is not None else None

    def list_research_snapshots(
        self, *, city_id: str | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[ResearchSnapshot, ...]:
        statement = select(ResearchSnapshotRow)
        if city_id is not None:
            statement = statement.where(ResearchSnapshotRow.city_id == city_id)
        rows = self._session.scalars(
            statement.order_by(
                ResearchSnapshotRow.created_at.desc(), ResearchSnapshotRow.snapshot_id.asc()
            )
            .limit(limit)
            .offset(offset)
        )
        return tuple(_research_snapshot_from_row(row) for row in rows)

    def get_place(self, place_id: str) -> Place | None:
        row = self._session.get(PlaceRow, place_id)
        return _place_from_row(row) if row is not None else None

    def get_revision(self, place_revision_id: str) -> PlaceRevision | None:
        row = self._session.get(PlaceRevisionRow, place_revision_id)
        return _revision_from_row(row) if row is not None else None

    def get_projection(self, projection_id: str) -> SolverPlaceProjection | None:
        row = self._session.get(SolverPlaceProjectionRow, projection_id)
        return _projection_from_row(row) if row is not None else None

    def get_projection_for_revision(self, place_revision_id: str) -> SolverPlaceProjection | None:
        row = self._session.scalar(
            select(SolverPlaceProjectionRow)
            .join(
                PlaceRevisionRow,
                PlaceRevisionRow.place_revision_id == SolverPlaceProjectionRow.place_revision_id,
            )
            .where(SolverPlaceProjectionRow.place_revision_id == place_revision_id)
            .where(SolverPlaceProjectionRow.place_id == PlaceRevisionRow.place_id)
            .order_by(
                SolverPlaceProjectionRow.created_at.desc(),
                SolverPlaceProjectionRow.projection_id.desc(),
            )
            .limit(1)
        )
        return _projection_from_row(row) if row is not None else None

    def load_revision_evidence(self, place_revision_id: str) -> PlaceRevisionEvidence | None:
        """Load O04 evidence without requiring a prepared Projection."""

        revision_row = self._session.get(PlaceRevisionRow, place_revision_id)
        if revision_row is None:
            return None
        revision = _revision_from_row(revision_row)

        geometry_rows = self._session.scalars(
            select(PlaceGeometryRow)
            .where(PlaceGeometryRow.place_revision_id == place_revision_id)
            .order_by(PlaceGeometryRow.created_at, PlaceGeometryRow.geometry_id)
        )
        access_point_rows = self._session.scalars(
            select(PlaceAccessPointRow)
            .where(PlaceAccessPointRow.place_revision_id == place_revision_id)
            .order_by(PlaceAccessPointRow.created_at, PlaceAccessPointRow.access_point_id)
        )
        geometries = tuple(_geometry_from_row(row) for row in geometry_rows)
        access_points = tuple(_access_point_from_row(row) for row in access_point_rows)
        time_rules = tuple(
            _time_rule_from_row(row)
            for row in self._session.scalars(
                select(PlaceTimeRuleRow)
                .where(PlaceTimeRuleRow.place_revision_id == place_revision_id)
                .order_by(PlaceTimeRuleRow.created_at, PlaceTimeRuleRow.time_rule_id)
            )
        )
        closures = tuple(
            _closure_from_row(row)
            for row in self._session.scalars(
                select(PlaceClosureRow)
                .where(PlaceClosureRow.place_revision_id == place_revision_id)
                .order_by(PlaceClosureRow.weekday, PlaceClosureRow.closure_id)
            )
        )
        date_exceptions = tuple(
            _date_exception_from_row(row)
            for row in self._session.scalars(
                select(PlaceDateExceptionRow)
                .where(PlaceDateExceptionRow.place_revision_id == place_revision_id)
                .order_by(
                    PlaceDateExceptionRow.service_date,
                    PlaceDateExceptionRow.date_exception_id,
                )
            )
        )
        relations = tuple(
            _relation_from_row(row)
            for row in self._session.scalars(
                select(PlaceRelationRow)
                .where(
                    or_(
                        PlaceRelationRow.from_place_id == revision.place_id,
                        PlaceRelationRow.to_place_id == revision.place_id,
                    )
                )
                .order_by(PlaceRelationRow.created_at, PlaceRelationRow.relation_id)
            )
        )
        relation_place_ids = tuple(
            dict.fromkeys(
                place_id
                for relation in relations
                for place_id in (relation.from_place_id, relation.to_place_id)
            )
        )
        relation_place_names: dict[str, str] = {}
        for relation_place_id in relation_place_ids:
            # Resolve each endpoint independently. This supports both canonical
            # place IDs and legacy revision IDs used by early relation imports.
            row = self._session.scalar(
                select(PlaceRevisionRow)
                .where(
                    or_(
                        PlaceRevisionRow.place_id == relation_place_id,
                        PlaceRevisionRow.place_revision_id == relation_place_id,
                    )
                )
                .order_by(PlaceRevisionRow.revision_number.desc())
                .limit(1)
            )
            if row is not None:
                relation_place_names[relation_place_id] = row.canonical_name
                relation_place_names.setdefault(row.place_id, row.canonical_name)
                relation_place_names.setdefault(row.place_revision_id, row.canonical_name)
        referenced_source_ids = tuple(
            dict.fromkeys(
                (
                    *revision.source_record_ids,
                    *(geometry.source_record_id for geometry in geometries),
                    *(point.source_record_id for point in access_points),
                    *(rule.source_record_id for rule in time_rules),
                    *(closure.source_record_id for closure in closures),
                    *(exception.source_record_id for exception in date_exceptions),
                    *(relation.source_record_id for relation in relations),
                )
            )
        )
        source_owner_place_ids = tuple(dict.fromkeys((revision.place_id, *relation_place_ids)))
        source_rows = (
            tuple(
                self._session.scalars(
                    select(PlaceSourceRecordRow)
                    .where(
                        PlaceSourceRecordRow.place_id.in_(source_owner_place_ids),
                        PlaceSourceRecordRow.source_record_id.in_(referenced_source_ids),
                    )
                    .order_by(
                        PlaceSourceRecordRow.created_at,
                        PlaceSourceRecordRow.source_record_id,
                    )
                )
            )
            if referenced_source_ids
            else ()
        )
        source_by_id = {row.source_record_id: _source_record_from_row(row) for row in source_rows}
        source_records = tuple(
            source_by_id[source_id]
            for source_id in referenced_source_ids
            if source_id in source_by_id
        )
        return PlaceRevisionEvidence(
            revision=revision,
            source_records=source_records,
            geometries=geometries,
            access_points=access_points,
            time_rules=time_rules,
            closures=closures,
            date_exceptions=date_exceptions,
            relations=relations,
            relation_place_names=tuple(sorted(relation_place_names.items())),
            projection=self.get_projection_for_revision(place_revision_id),
            missing_source_record_ids=tuple(
                source_id for source_id in referenced_source_ids if source_id not in source_by_id
            ),
        )
