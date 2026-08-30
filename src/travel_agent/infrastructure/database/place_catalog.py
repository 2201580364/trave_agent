"""SQLAlchemy persistence and publication boundary for the place catalog."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    or_,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from travel_agent.domain.place_catalog import (
    Place,
    PlaceAccessPoint,
    PlaceClosure,
    PlaceDateException,
    PlaceGeometry,
    PlaceRelation,
    PlaceRevision,
    PlaceRevisionEvidence,
    PlaceSourceRecord,
    PlaceTimeRule,
    ProjectionPublicationContext,
    ProjectionPublicationError,
    SelectionExclusionGroup,
    SelectionExclusionMember,
    SolverPlaceProjection,
    publish_projection,
)

from .planning import Base

MYSQL_TABLE_ARGS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


class PlaceRow(Base):
    __tablename__ = "places"

    place_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    city_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    merged_into_place_id: Mapped[str | None] = mapped_column(
        ForeignKey("places.place_id"), nullable=True
    )
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))


class PlaceSourceRecordRow(Base):
    __tablename__ = "place_source_records"

    source_record_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    place_id: Mapped[str] = mapped_column(ForeignKey("places.place_id"), index=True)
    source_id: Mapped[str] = mapped_column(String(80), index=True)
    registry_id: Mapped[str] = mapped_column(String(80))
    registry_sha256: Mapped[str] = mapped_column(String(64))
    field_dictionary_id: Mapped[str] = mapped_column(String(80))
    field_dictionary_sha256: Mapped[str] = mapped_column(String(64))
    source_url: Mapped[str] = mapped_column(String(1000))
    collection_mode: Mapped[str] = mapped_column(String(32))
    target_stage: Mapped[str] = mapped_column(String(20), index=True)
    source_decision: Mapped[str] = mapped_column(String(20))
    observed_at: Mapped[str] = mapped_column(String(40))
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    created_at: Mapped[str] = mapped_column(String(40))


class PlaceRevisionRow(Base):
    __tablename__ = "place_revisions"
    __table_args__ = (
        UniqueConstraint(
            "place_id", "revision_number", name="uq_place_revisions_place_number"
        ),
        MYSQL_TABLE_ARGS,
    )

    place_revision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    place_id: Mapped[str] = mapped_column(ForeignKey("places.place_id"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer)
    lifecycle_status: Mapped[str] = mapped_column(String(24), index=True)
    canonical_name: Mapped[str] = mapped_column(String(160), index=True)
    aliases: Mapped[list[str]] = mapped_column(JSON)
    place_kind: Mapped[str] = mapped_column(String(32), index=True)
    category: Mapped[str] = mapped_column(String(64))
    admin_area: Mapped[str] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    geometry_kind: Mapped[str] = mapped_column(String(20))
    duration_min: Mapped[int] = mapped_column(Integer)
    duration_recommended: Mapped[int] = mapped_column(Integer)
    duration_max: Mapped[int] = mapped_column(Integer)
    internal_travel_min: Mapped[int] = mapped_column(Integer)
    energy_level: Mapped[int] = mapped_column(Integer)
    indoor_outdoor: Mapped[str] = mapped_column(String(20))
    suitable_periods: Mapped[list[str]] = mapped_column(JSON)
    audience_tags: Mapped[list[str]] = mapped_column(JSON)
    rain_suitability: Mapped[str] = mapped_column(String(20))
    is_always_open: Mapped[bool] = mapped_column(Boolean)
    solver_eligible: Mapped[bool] = mapped_column(Boolean, index=True)
    conflicts_resolved: Mapped[bool] = mapped_column(Boolean)
    source_record_ids: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(40))
    reviewed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    published_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    review_flags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, default=list)


class PlaceGeometryRow(Base):
    __tablename__ = "place_geometries"

    geometry_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    place_revision_id: Mapped[str] = mapped_column(
        ForeignKey("place_revisions.place_revision_id"), index=True
    )
    geometry_kind: Mapped[str] = mapped_column(String(20))
    geometry: Mapped[dict[str, Any]] = mapped_column(JSON)
    source_record_id: Mapped[str] = mapped_column(
        ForeignKey("place_source_records.source_record_id"), index=True
    )
    review_status: Mapped[str] = mapped_column(String(24), index=True)
    active: Mapped[bool] = mapped_column(Boolean, index=True)
    created_at: Mapped[str] = mapped_column(String(40))
    reviewed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class PlaceAccessPointRow(Base):
    __tablename__ = "place_access_points"

    access_point_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    place_revision_id: Mapped[str] = mapped_column(
        ForeignKey("place_revisions.place_revision_id"), index=True
    )
    access_point_kind: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(160))
    lat: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    lng: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    source_record_id: Mapped[str] = mapped_column(
        ForeignKey("place_source_records.source_record_id"), index=True
    )
    review_status: Mapped[str] = mapped_column(String(24), index=True)
    active: Mapped[bool] = mapped_column(Boolean, index=True)
    fetched_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reviewed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40))


class PlaceTimeRuleRow(Base):
    __tablename__ = "place_time_rules"

    time_rule_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    place_revision_id: Mapped[str] = mapped_column(
        ForeignKey("place_revisions.place_revision_id"), index=True
    )
    rule_kind: Mapped[str] = mapped_column(String(24), index=True)
    weekdays: Mapped[list[int]] = mapped_column(JSON)
    start_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_entry_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_record_id: Mapped[str] = mapped_column(
        ForeignKey("place_source_records.source_record_id"), index=True
    )
    review_status: Mapped[str] = mapped_column(String(24), index=True)
    active: Mapped[bool] = mapped_column(Boolean, index=True)
    created_at: Mapped[str] = mapped_column(String(40))
    reviewed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class PlaceClosureRow(Base):
    __tablename__ = "place_closures"
    __table_args__ = (
        UniqueConstraint(
            "place_revision_id", "weekday", name="uq_place_closures_revision_weekday"
        ),
        MYSQL_TABLE_ARGS,
    )

    closure_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    place_revision_id: Mapped[str] = mapped_column(
        ForeignKey("place_revisions.place_revision_id"), index=True
    )
    weekday: Mapped[int] = mapped_column(Integer)
    source_record_id: Mapped[str] = mapped_column(
        ForeignKey("place_source_records.source_record_id"), index=True
    )
    review_status: Mapped[str] = mapped_column(String(24), index=True)
    active: Mapped[bool] = mapped_column(Boolean, index=True)
    created_at: Mapped[str] = mapped_column(String(40))
    reviewed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class PlaceDateExceptionRow(Base):
    __tablename__ = "place_date_exceptions"
    __table_args__ = (
        UniqueConstraint(
            "place_revision_id",
            "service_date",
            "exception_kind",
            name="uq_place_date_exceptions_revision_date_kind",
        ),
        MYSQL_TABLE_ARGS,
    )

    date_exception_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    place_revision_id: Mapped[str] = mapped_column(
        ForeignKey("place_revisions.place_revision_id"), index=True
    )
    service_date: Mapped[date] = mapped_column(Date, index=True)
    exception_kind: Mapped[str] = mapped_column(String(24))
    start_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_entry_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_record_id: Mapped[str] = mapped_column(
        ForeignKey("place_source_records.source_record_id"), index=True
    )
    review_status: Mapped[str] = mapped_column(String(24), index=True)
    active: Mapped[bool] = mapped_column(Boolean, index=True)
    created_at: Mapped[str] = mapped_column(String(40))
    reviewed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class PlaceRelationRow(Base):
    __tablename__ = "place_relations"
    __table_args__ = (
        UniqueConstraint(
            "from_place_id",
            "to_place_id",
            "relation_type",
            name="uq_place_relations_direction_type",
        ),
        MYSQL_TABLE_ARGS,
    )

    relation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    from_place_id: Mapped[str] = mapped_column(
        ForeignKey("places.place_id"), index=True
    )
    to_place_id: Mapped[str] = mapped_column(ForeignKey("places.place_id"), index=True)
    relation_type: Mapped[str] = mapped_column(String(24), index=True)
    source_record_id: Mapped[str] = mapped_column(
        ForeignKey("place_source_records.source_record_id"), index=True
    )
    review_status: Mapped[str] = mapped_column(String(24), index=True)
    resolution_status: Mapped[str] = mapped_column(String(24), index=True)
    decision_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, index=True)
    created_at: Mapped[str] = mapped_column(String(40))
    reviewed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class SelectionExclusionGroupRow(Base):
    __tablename__ = "selection_exclusion_groups"

    exclusion_group_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    city_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), index=True)
    review_status: Mapped[str] = mapped_column(String(24), index=True)
    decision_note: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[str] = mapped_column(String(40))
    reviewed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class SelectionExclusionMemberRow(Base):
    __tablename__ = "selection_exclusion_members"
    __table_args__ = (
        UniqueConstraint(
            "exclusion_group_id",
            "place_id",
            name="uq_selection_exclusion_members_group_place",
        ),
        MYSQL_TABLE_ARGS,
    )

    exclusion_group_id: Mapped[str] = mapped_column(
        ForeignKey("selection_exclusion_groups.exclusion_group_id"),
        primary_key=True,
    )
    place_id: Mapped[str] = mapped_column(
        ForeignKey("places.place_id"), primary_key=True, index=True
    )
    created_at: Mapped[str] = mapped_column(String(40))


class SolverPlaceProjectionRow(Base):
    __tablename__ = "solver_place_projections"
    __table_args__ = (
        UniqueConstraint(
            "data_snapshot_version",
            "solver_node_id",
            name="uq_solver_place_projections_snapshot_node",
        ),
        UniqueConstraint(
            "data_snapshot_version",
            "place_revision_id",
            name="uq_solver_place_projections_snapshot_revision",
        ),
        MYSQL_TABLE_ARGS,
    )

    projection_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    projection_version: Mapped[str] = mapped_column(String(64), index=True)
    data_snapshot_version: Mapped[str] = mapped_column(String(128), index=True)
    place_id: Mapped[str] = mapped_column(ForeignKey("places.place_id"), index=True)
    place_revision_id: Mapped[str] = mapped_column(
        ForeignKey("place_revisions.place_revision_id"), index=True
    )
    solver_node_id: Mapped[int] = mapped_column(Integer)
    place_kind: Mapped[str] = mapped_column(String(32))
    geometry_kind: Mapped[str] = mapped_column(String(20))
    arrival_access_point_id: Mapped[str] = mapped_column(
        ForeignKey("place_access_points.access_point_id")
    )
    departure_access_point_id: Mapped[str] = mapped_column(
        ForeignKey("place_access_points.access_point_id")
    )
    duration_min: Mapped[int] = mapped_column(Integer)
    duration_recommended: Mapped[int] = mapped_column(Integer)
    duration_max: Mapped[int] = mapped_column(Integer)
    internal_travel_min: Mapped[int] = mapped_column(Integer)
    solver_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    projection_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    gate_reason_codes: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(40))
    published_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class SqlAlchemyPlaceCatalogRepository:
    """Persist catalog facts and expose the only supported publication transition."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add_place(self, place: Place) -> None:
        self._add(PlaceRow(**_place_values(place)), "place already exists")

    def add_source_record(self, record: PlaceSourceRecord) -> None:
        self._add(
            PlaceSourceRecordRow(**_source_record_values(record)),
            "place source record already exists",
        )

    def add_revision(self, revision: PlaceRevision) -> None:
        if revision.lifecycle_status == "published":
            raise ValueError("published revisions must use the publication gate")
        self._add(
            PlaceRevisionRow(**_revision_values(revision)),
            "place revision already exists",
        )

    def add_geometry(self, geometry: PlaceGeometry) -> None:
        self._add(PlaceGeometryRow(**_geometry_values(geometry)), "geometry already exists")

    def add_access_point(self, access_point: PlaceAccessPoint) -> None:
        self._add(
            PlaceAccessPointRow(**_access_point_values(access_point)),
            "access point already exists",
        )

    def add_time_rule(self, rule: PlaceTimeRule) -> None:
        self._add(PlaceTimeRuleRow(**_time_rule_values(rule)), "time rule already exists")

    def add_closure(self, closure: PlaceClosure) -> None:
        self._add(PlaceClosureRow(**_closure_values(closure)), "closure already exists")

    def add_date_exception(self, exception: PlaceDateException) -> None:
        self._add(
            PlaceDateExceptionRow(**_date_exception_values(exception)),
            "date exception already exists",
        )

    def add_relation(self, relation: PlaceRelation) -> None:
        self._add(PlaceRelationRow(**_relation_values(relation)), "relation already exists")

    def add_exclusion_group(self, group: SelectionExclusionGroup) -> None:
        self._add(
            SelectionExclusionGroupRow(**_exclusion_group_values(group)),
            "selection exclusion group already exists",
        )

    def add_exclusion_member(self, member: SelectionExclusionMember) -> None:
        self._add(
            SelectionExclusionMemberRow(**_exclusion_member_values(member)),
            "selection exclusion member already exists",
        )

    def add_projection(self, projection: SolverPlaceProjection) -> None:
        if projection.status == "published":
            raise ValueError("published projections must use the publication gate")
        self._add(
            SolverPlaceProjectionRow(**_projection_values(projection)),
            "solver projection already exists",
        )

    def get_place(self, place_id: str) -> Place | None:
        row = self._session.get(PlaceRow, place_id)
        return _place_from_row(row) if row is not None else None

    def get_revision(self, place_revision_id: str) -> PlaceRevision | None:
        row = self._session.get(PlaceRevisionRow, place_revision_id)
        return _revision_from_row(row) if row is not None else None

    def get_projection(self, projection_id: str) -> SolverPlaceProjection | None:
        row = self._session.get(SolverPlaceProjectionRow, projection_id)
        return _projection_from_row(row) if row is not None else None

    def get_projection_for_revision(
        self, place_revision_id: str
    ) -> SolverPlaceProjection | None:
        row = self._session.scalar(
            select(SolverPlaceProjectionRow)
            .join(
                PlaceRevisionRow,
                PlaceRevisionRow.place_revision_id
                == SolverPlaceProjectionRow.place_revision_id,
            )
            .where(SolverPlaceProjectionRow.place_revision_id == place_revision_id)
            .where(
                SolverPlaceProjectionRow.place_id == PlaceRevisionRow.place_id
            )
            .order_by(
                SolverPlaceProjectionRow.created_at.desc(),
                SolverPlaceProjectionRow.projection_id.desc(),
            )
            .limit(1)
        )
        return _projection_from_row(row) if row is not None else None

    def load_revision_evidence(
        self, place_revision_id: str
    ) -> PlaceRevisionEvidence | None:
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
        referenced_source_ids = tuple(
            dict.fromkeys(
                (
                    *revision.source_record_ids,
                    *(geometry.source_record_id for geometry in geometries),
                    *(point.source_record_id for point in access_points),
                )
            )
        )
        source_rows = (
            tuple(
                self._session.scalars(
                    select(PlaceSourceRecordRow)
                    .where(
                        PlaceSourceRecordRow.place_id == revision_row.place_id,
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
        source_by_id = {
            row.source_record_id: _source_record_from_row(row) for row in source_rows
        }
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
            projection=self.get_projection_for_revision(place_revision_id),
            missing_source_record_ids=tuple(
                source_id
                for source_id in referenced_source_ids
                if source_id not in source_by_id
            ),
        )

    def load_publication_context(
        self, projection_id: str
    ) -> ProjectionPublicationContext | None:
        projection_row = self._session.get(SolverPlaceProjectionRow, projection_id)
        if projection_row is None:
            return None
        revision_row = self._session.get(
            PlaceRevisionRow, projection_row.place_revision_id
        )
        place_row = self._session.get(PlaceRow, projection_row.place_id)
        if revision_row is None or place_row is None:
            return None

        # Materialize every projection dependency before loading sources.  A
        # source record is globally keyed, so loading only the revision's
        # source IDs would miss a source referenced by a geometry, access
        # point, or time rule.  The source query intentionally does not filter
        # by place: the domain publication gate must distinguish a missing
        # source from an existing source belonging to another Place and emit
        # the stable SOURCE_RECORD_PLACE_MISMATCH reason.
        geometry_rows = tuple(
            self._session.scalars(
                select(PlaceGeometryRow).where(
                    PlaceGeometryRow.place_revision_id
                    == revision_row.place_revision_id
                )
            )
        )
        access_rows = tuple(
            self._session.scalars(
                select(PlaceAccessPointRow).where(
                    PlaceAccessPointRow.place_revision_id
                    == revision_row.place_revision_id
                )
            )
        )
        time_rule_rows = tuple(
            self._session.scalars(
                select(PlaceTimeRuleRow).where(
                    PlaceTimeRuleRow.place_revision_id
                    == revision_row.place_revision_id
                )
            )
        )
        relation_rows = tuple(
            self._session.scalars(
                select(PlaceRelationRow).where(
                    or_(
                        PlaceRelationRow.from_place_id == place_row.place_id,
                        PlaceRelationRow.to_place_id == place_row.place_id,
                    )
                )
            )
        )
        referenced_source_ids = tuple(
            dict.fromkeys(
                (
                    *revision_row.source_record_ids,
                    *(row.source_record_id for row in geometry_rows),
                    *(row.source_record_id for row in access_rows),
                    *(row.source_record_id for row in time_rule_rows),
                )
            )
        )
        source_rows = (
            tuple(
                self._session.scalars(
                    select(PlaceSourceRecordRow)
                    .where(
                        PlaceSourceRecordRow.source_record_id.in_(
                            referenced_source_ids
                        )
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
        return ProjectionPublicationContext(
            place=_place_from_row(place_row),
            revision=_revision_from_row(revision_row),
            source_records=tuple(_source_record_from_row(row) for row in source_rows),
            geometries=tuple(_geometry_from_row(row) for row in geometry_rows),
            access_points=tuple(_access_point_from_row(row) for row in access_rows),
            time_rules=tuple(_time_rule_from_row(row) for row in time_rule_rows),
            relations=tuple(_relation_from_row(row) for row in relation_rows),
            projection=_projection_from_row(projection_row),
        )

    def publish_projection(
        self, projection_id: str, *, published_at: datetime
    ) -> SolverPlaceProjection:
        context = self.load_publication_context(projection_id)
        if context is None:
            raise ValueError("solver projection does not exist")
        if context.projection.status == "published":
            return context.projection
        revision, projection = publish_projection(context, published_at=published_at)
        revision_row = self._session.get(PlaceRevisionRow, revision.place_revision_id)
        projection_row = self._session.get(SolverPlaceProjectionRow, projection.projection_id)
        if revision_row is None or projection_row is None:
            raise ProjectionPublicationError(("PROJECTION_DEPENDENCY_MISSING",))
        if revision.published_at is None or projection.published_at is None:
            raise ProjectionPublicationError(("PROJECTION_PUBLICATION_TIME_MISSING",))
        revision_row.lifecycle_status = revision.lifecycle_status
        revision_row.published_at = revision.published_at.isoformat()
        projection_row.status = projection.status
        projection_row.gate_reason_codes = []
        projection_row.published_at = projection.published_at.isoformat()
        self._session.flush()
        return projection

    def _add(self, row: Base, message: str) -> None:
        self._session.add(row)
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise ValueError(message) from exc


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _place_values(value: Place) -> dict[str, Any]:
    return {
        "place_id": value.place_id,
        "city_id": value.city_id,
        "status": value.status,
        "merged_into_place_id": value.merged_into_place_id,
        "created_at": value.created_at.isoformat(),
        "updated_at": value.updated_at.isoformat(),
    }


def _place_from_row(row: PlaceRow) -> Place:
    return Place(
        row.place_id,
        row.city_id,
        row.status,
        datetime.fromisoformat(row.created_at),
        datetime.fromisoformat(row.updated_at),
        row.merged_into_place_id,
    )


def _source_record_values(value: PlaceSourceRecord) -> dict[str, Any]:
    return {
        "source_record_id": value.source_record_id,
        "place_id": value.place_id,
        "source_id": value.source_id,
        "registry_id": value.registry_id,
        "registry_sha256": value.registry_sha256,
        "field_dictionary_id": value.field_dictionary_id,
        "field_dictionary_sha256": value.field_dictionary_sha256,
        "source_url": value.source_url,
        "collection_mode": value.collection_mode,
        "target_stage": value.target_stage,
        "source_decision": value.source_decision,
        "observed_at": value.observed_at.isoformat(),
        "content_sha256": value.content_sha256,
        "status": value.status,
        "created_at": value.created_at.isoformat(),
    }


def _source_record_from_row(row: PlaceSourceRecordRow) -> PlaceSourceRecord:
    return PlaceSourceRecord(
        row.source_record_id,
        row.place_id,
        row.source_id,
        row.registry_id,
        row.registry_sha256,
        row.field_dictionary_id,
        row.field_dictionary_sha256,
        row.source_url,
        row.collection_mode,
        row.target_stage,
        row.source_decision,
        datetime.fromisoformat(row.observed_at),
        row.content_sha256,
        row.status,
        datetime.fromisoformat(row.created_at),
    )


def _revision_values(value: PlaceRevision) -> dict[str, Any]:
    return {
        "place_revision_id": value.place_revision_id,
        "place_id": value.place_id,
        "revision_number": value.revision_number,
        "lifecycle_status": value.lifecycle_status,
        "canonical_name": value.canonical_name,
        "aliases": list(value.aliases),
        "place_kind": value.place_kind,
        "category": value.category,
        "admin_area": value.admin_area,
        "address": value.address,
        "geometry_kind": value.geometry_kind,
        "duration_min": value.duration_min,
        "duration_recommended": value.duration_recommended,
        "duration_max": value.duration_max,
        "internal_travel_min": value.internal_travel_min,
        "energy_level": value.energy_level,
        "indoor_outdoor": value.indoor_outdoor,
        "suitable_periods": list(value.suitable_periods),
        "audience_tags": list(value.audience_tags),
        "rain_suitability": value.rain_suitability,
        "is_always_open": value.is_always_open,
        "solver_eligible": value.solver_eligible,
        "conflicts_resolved": value.conflicts_resolved,
        "source_record_ids": list(value.source_record_ids),
        "created_at": value.created_at.isoformat(),
        "reviewed_at": _iso(value.reviewed_at),
        "published_at": _iso(value.published_at),
        "review_flags": list(value.review_flags),
    }


def _revision_from_row(row: PlaceRevisionRow) -> PlaceRevision:
    return PlaceRevision(
        row.place_revision_id,
        row.place_id,
        row.revision_number,
        row.lifecycle_status,
        row.canonical_name,
        tuple(row.aliases),
        row.place_kind,
        row.category,
        row.admin_area,
        row.address,
        row.geometry_kind,
        row.duration_min,
        row.duration_recommended,
        row.duration_max,
        row.internal_travel_min,
        row.energy_level,
        row.indoor_outdoor,
        tuple(row.suitable_periods),
        tuple(row.audience_tags),
        row.rain_suitability,
        row.is_always_open,
        row.solver_eligible,
        row.conflicts_resolved,
        tuple(row.source_record_ids),
        datetime.fromisoformat(row.created_at),
        datetime.fromisoformat(row.reviewed_at) if row.reviewed_at else None,
        datetime.fromisoformat(row.published_at) if row.published_at else None,
        tuple(row.review_flags or ()),
    )


def _geometry_values(value: PlaceGeometry) -> dict[str, Any]:
    return {
        "geometry_id": value.geometry_id,
        "place_revision_id": value.place_revision_id,
        "geometry_kind": value.geometry_kind,
        "geometry": value.geometry,
        "source_record_id": value.source_record_id,
        "review_status": value.review_status,
        "active": value.active,
        "created_at": value.created_at.isoformat(),
        "reviewed_at": _iso(value.reviewed_at),
    }


def _geometry_from_row(row: PlaceGeometryRow) -> PlaceGeometry:
    return PlaceGeometry(
        row.geometry_id,
        row.place_revision_id,
        row.geometry_kind,
        row.geometry,
        row.source_record_id,
        row.review_status,
        row.active,
        datetime.fromisoformat(row.created_at),
        datetime.fromisoformat(row.reviewed_at) if row.reviewed_at else None,
    )


def _access_point_values(value: PlaceAccessPoint) -> dict[str, Any]:
    return {
        "access_point_id": value.access_point_id,
        "place_revision_id": value.place_revision_id,
        "access_point_kind": value.access_point_kind,
        "name": value.name,
        "lat": value.lat,
        "lng": value.lng,
        "source_record_id": value.source_record_id,
        "review_status": value.review_status,
        "active": value.active,
        "fetched_at": _iso(value.fetched_at),
        "reviewed_at": _iso(value.reviewed_at),
        "created_at": value.created_at.isoformat(),
    }


def _access_point_from_row(row: PlaceAccessPointRow) -> PlaceAccessPoint:
    return PlaceAccessPoint(
        row.access_point_id,
        row.place_revision_id,
        row.access_point_kind,
        row.name,
        row.lat,
        row.lng,
        row.source_record_id,
        row.review_status,
        row.active,
        datetime.fromisoformat(row.fetched_at) if row.fetched_at else None,
        datetime.fromisoformat(row.reviewed_at) if row.reviewed_at else None,
        datetime.fromisoformat(row.created_at),
    )


def _time_rule_values(value: PlaceTimeRule) -> dict[str, Any]:
    return {
        "time_rule_id": value.time_rule_id,
        "place_revision_id": value.place_revision_id,
        "rule_kind": value.rule_kind,
        "weekdays": list(value.weekdays),
        "start_minute": value.start_minute,
        "end_minute": value.end_minute,
        "last_entry_minute": value.last_entry_minute,
        "valid_from": value.valid_from,
        "valid_to": value.valid_to,
        "source_record_id": value.source_record_id,
        "review_status": value.review_status,
        "active": value.active,
        "created_at": value.created_at.isoformat(),
        "reviewed_at": _iso(value.reviewed_at),
    }


def _time_rule_from_row(row: PlaceTimeRuleRow) -> PlaceTimeRule:
    return PlaceTimeRule(
        row.time_rule_id,
        row.place_revision_id,
        row.rule_kind,
        tuple(row.weekdays),
        row.start_minute,
        row.end_minute,
        row.last_entry_minute,
        row.valid_from,
        row.valid_to,
        row.source_record_id,
        row.review_status,
        row.active,
        datetime.fromisoformat(row.created_at),
        datetime.fromisoformat(row.reviewed_at) if row.reviewed_at else None,
    )


def _closure_values(value: PlaceClosure) -> dict[str, Any]:
    return {
        "closure_id": value.closure_id,
        "place_revision_id": value.place_revision_id,
        "weekday": value.weekday,
        "source_record_id": value.source_record_id,
        "review_status": value.review_status,
        "active": value.active,
        "created_at": value.created_at.isoformat(),
        "reviewed_at": _iso(value.reviewed_at),
    }


def _date_exception_values(value: PlaceDateException) -> dict[str, Any]:
    return {
        "date_exception_id": value.date_exception_id,
        "place_revision_id": value.place_revision_id,
        "service_date": value.service_date,
        "exception_kind": value.exception_kind,
        "start_minute": value.start_minute,
        "end_minute": value.end_minute,
        "last_entry_minute": value.last_entry_minute,
        "source_record_id": value.source_record_id,
        "review_status": value.review_status,
        "active": value.active,
        "created_at": value.created_at.isoformat(),
        "reviewed_at": _iso(value.reviewed_at),
    }


def _relation_values(value: PlaceRelation) -> dict[str, Any]:
    return {
        "relation_id": value.relation_id,
        "from_place_id": value.from_place_id,
        "to_place_id": value.to_place_id,
        "relation_type": value.relation_type,
        "source_record_id": value.source_record_id,
        "review_status": value.review_status,
        "resolution_status": value.resolution_status,
        "decision_note": value.decision_note,
        "active": value.active,
        "created_at": value.created_at.isoformat(),
        "reviewed_at": _iso(value.reviewed_at),
    }


def _relation_from_row(row: PlaceRelationRow) -> PlaceRelation:
    return PlaceRelation(
        row.relation_id,
        row.from_place_id,
        row.to_place_id,
        row.relation_type,
        row.source_record_id,
        row.review_status,
        row.resolution_status,
        row.decision_note,
        row.active,
        datetime.fromisoformat(row.created_at),
        datetime.fromisoformat(row.reviewed_at) if row.reviewed_at else None,
    )


def _exclusion_group_values(value: SelectionExclusionGroup) -> dict[str, Any]:
    return {
        "exclusion_group_id": value.exclusion_group_id,
        "city_id": value.city_id,
        "name": value.name,
        "status": value.status,
        "review_status": value.review_status,
        "decision_note": value.decision_note,
        "created_at": value.created_at.isoformat(),
        "reviewed_at": _iso(value.reviewed_at),
    }


def _exclusion_member_values(value: SelectionExclusionMember) -> dict[str, Any]:
    return {
        "exclusion_group_id": value.exclusion_group_id,
        "place_id": value.place_id,
        "created_at": value.created_at.isoformat(),
    }


def _projection_values(value: SolverPlaceProjection) -> dict[str, Any]:
    return {
        "projection_id": value.projection_id,
        "projection_version": value.projection_version,
        "data_snapshot_version": value.data_snapshot_version,
        "place_id": value.place_id,
        "place_revision_id": value.place_revision_id,
        "solver_node_id": value.solver_node_id,
        "place_kind": value.place_kind,
        "geometry_kind": value.geometry_kind,
        "arrival_access_point_id": value.arrival_access_point_id,
        "departure_access_point_id": value.departure_access_point_id,
        "duration_min": value.duration_min,
        "duration_recommended": value.duration_recommended,
        "duration_max": value.duration_max,
        "internal_travel_min": value.internal_travel_min,
        "solver_payload": value.solver_payload,
        "projection_hash": value.projection_hash,
        "status": value.status,
        "gate_reason_codes": list(value.gate_reason_codes),
        "created_at": value.created_at.isoformat(),
        "published_at": _iso(value.published_at),
    }


def _projection_from_row(row: SolverPlaceProjectionRow) -> SolverPlaceProjection:
    return SolverPlaceProjection(
        row.projection_id,
        row.projection_version,
        row.data_snapshot_version,
        row.place_id,
        row.place_revision_id,
        row.solver_node_id,
        row.place_kind,
        row.geometry_kind,
        row.arrival_access_point_id,
        row.departure_access_point_id,
        row.duration_min,
        row.duration_recommended,
        row.duration_max,
        row.internal_travel_min,
        row.solver_payload,
        row.projection_hash,
        row.status,
        tuple(row.gate_reason_codes),
        datetime.fromisoformat(row.created_at),
        datetime.fromisoformat(row.published_at) if row.published_at else None,
    )
