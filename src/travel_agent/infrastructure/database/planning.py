"""Explicit SQLAlchemy mapping for the M1 planning aggregates."""

from __future__ import annotations

from datetime import date, datetime
from types import TracebackType
from typing import Any, Self

from sqlalchemy import JSON, Boolean, Integer, String, UniqueConstraint, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    declared_attr,
    mapped_column,
    sessionmaker,
)

from travel_agent.application.common.errors import (
    DraftVersionConflictError,
    GenerationIntentConflictError,
    TripRevisionConflictError,
)
from travel_agent.domain.planning import (
    CompletionKind,
    ConfirmationStatus,
    CrowdType,
    GenerationIntent,
    GenerationStatus,
    SolverRun,
    TransportType,
    TravelFacts,
    TravelMode,
    Trip,
    TripDraft,
    TripRevision,
    VisitPeriodPreferenceInput,
)


class Base(DeclarativeBase):
    @declared_attr.directive
    def __table_args__(cls) -> dict[str, str]:
        return {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_0900_ai_ci",
        }


class TripDraftRow(Base):
    __tablename__ = "trip_drafts"

    draft_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    principal_id: Mapped[str] = mapped_column(String(64), index=True)
    city_id: Mapped[str] = mapped_column(String(64), index=True)
    draft_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32))
    travel_facts: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    selected_attraction_ids: Mapped[list[str]] = mapped_column(JSON)
    visit_period_preferences: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))


class GenerationIntentRow(Base):
    __tablename__ = "generation_intents"

    generation_intent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    principal_id: Mapped[str] = mapped_column(String(64), index=True)
    draft_id: Mapped[str] = mapped_column(String(64), index=True)
    draft_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), index=True)
    input_schema_version: Mapped[str] = mapped_column(String(64))
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    input_snapshot_hash: Mapped[str] = mapped_column(String(64))
    data_snapshot_version: Mapped[str] = mapped_column(String(128))
    random_seed: Mapped[int] = mapped_column(Integer)
    submitted_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))
    trip_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trip_revision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_trip_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    base_revision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class TripRow(Base):
    __tablename__ = "trips"

    trip_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    principal_id: Mapped[str] = mapped_column(String(64), index=True)
    city_id: Mapped[str] = mapped_column(String(64), index=True)
    source_draft_id: Mapped[str] = mapped_column(String(64), index=True)
    current_revision_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))


class TripRevisionRow(Base):
    __tablename__ = "trip_revisions"
    __table_args__ = (
        UniqueConstraint(
            "trip_id", "revision_number", name="uq_trip_revisions_trip_number"
        ),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_0900_ai_ci",
        },
    )

    trip_revision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trip_id: Mapped[str] = mapped_column(String(64), index=True)
    revision_number: Mapped[int] = mapped_column(Integer)
    generation_intent_id: Mapped[str] = mapped_column(String(64), unique=True)
    completion_kind: Mapped[str] = mapped_column(String(32))
    has_soft_degradation: Mapped[bool] = mapped_column(Boolean)
    result_schema_version: Mapped[str] = mapped_column(String(64))
    result_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    result_snapshot_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String(40))


class SolverRunRow(Base):
    __tablename__ = "solver_runs"

    solver_run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    generation_intent_id: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(32))
    quality_gate_passed: Mapped[bool] = mapped_column(Boolean)
    solver_version: Mapped[str] = mapped_column(String(64))
    constraint_version: Mapped[str] = mapped_column(String(64))
    parameter_version: Mapped[str] = mapped_column(String(64))
    audit_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(40))


def create_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)


class SqlAlchemyTripDraftRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, draft_id: str) -> TripDraft | None:
        row = self._session.get(TripDraftRow, draft_id)
        return _draft_from_row(row) if row is not None else None

    def save(self, draft: TripDraft, *, expected_version: int | None = None) -> None:
        values = _draft_values(draft)
        if expected_version is None:
            self._session.add(TripDraftRow(**values))
            try:
                self._session.flush()
            except IntegrityError as exc:
                raise ValueError("draft already exists") from exc
            return
        statement = (
            update(TripDraftRow)
            .where(
                TripDraftRow.draft_id == draft.draft_id,
                TripDraftRow.draft_version == expected_version,
            )
            .values(**values)
        )
        if self._session.execute(statement).rowcount != 1:
            current = self._session.scalar(
                select(TripDraftRow.draft_version).where(
                    TripDraftRow.draft_id == draft.draft_id
                )
            )
            raise DraftVersionConflictError(
                expected_version=expected_version,
                current_version=current or 0,
            )


class SqlAlchemyGenerationIntentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, generation_intent_id: str) -> GenerationIntent | None:
        row = self._session.get(GenerationIntentRow, generation_intent_id)
        return _intent_from_row(row) if row is not None else None

    def add(self, intent: GenerationIntent) -> None:
        self._session.add(GenerationIntentRow(**_intent_values(intent)))
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise GenerationIntentConflictError from exc

    def save(self, intent: GenerationIntent, *, expected_status: str) -> None:
        statement = (
            update(GenerationIntentRow)
            .where(
                GenerationIntentRow.generation_intent_id
                == intent.generation_intent_id,
                GenerationIntentRow.status == expected_status,
            )
            .values(**_intent_values(intent))
        )
        if self._session.execute(statement).rowcount != 1:
            raise ValueError("generation intent status conflict")


class SqlAlchemyTripRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, trip_id: str) -> Trip | None:
        row = self._session.get(TripRow, trip_id)
        return _trip_from_row(row) if row is not None else None

    def add(self, trip: Trip) -> None:
        self._session.add(TripRow(**_trip_values(trip)))
        self._session.flush()

    def save(
        self,
        trip: Trip,
        *,
        expected_revision_id: str | None = None,
    ) -> None:
        statement = update(TripRow).where(TripRow.trip_id == trip.trip_id)
        if expected_revision_id is not None:
            statement = statement.where(
                TripRow.current_revision_id == expected_revision_id
            )
        if self._session.execute(statement.values(**_trip_values(trip))).rowcount != 1:
            if expected_revision_id is not None:
                raise TripRevisionConflictError
            raise ValueError("trip_id does not exist")


class _SqlAlchemyRepository:
    def __init__(self, session: Session, row_type, entity_from_row, values) -> None:
        self._session = session
        self._row_type = row_type
        self._entity_from_row = entity_from_row
        self._values = values

    def get(self, record_id: str):
        row = self._session.get(self._row_type, record_id)
        return self._entity_from_row(row) if row is not None else None

    def add(self, entity) -> None:
        self._session.add(self._row_type(**self._values(entity)))
        self._session.flush()

    def save(self, entity) -> None:
        identity = self._row_type.__mapper__.primary_key[0].key
        record_id = getattr(entity, identity)
        row = self._session.get(self._row_type, record_id)
        if row is None:
            raise ValueError(f"{identity} does not exist")
        for key, value in self._values(entity).items():
            setattr(row, key, value)
        self._session.flush()


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    def __enter__(self) -> Self:
        self._session = self._session_factory()
        self.drafts = SqlAlchemyTripDraftRepository(self._session)
        self.generation_intents = SqlAlchemyGenerationIntentRepository(self._session)
        self.trips = SqlAlchemyTripRepository(self._session)
        self.trip_revisions = _SqlAlchemyRepository(
            self._session, TripRevisionRow, _revision_from_row, _revision_values
        )
        self.solver_runs = _SqlAlchemyRepository(
            self._session, SolverRunRow, _run_from_row, _run_values
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if self._session is not None:
            if exc_type is not None:
                self._session.rollback()
            self._session.close()
            self._session = None
        return None

    def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("unit of work is not active")
        self._session.commit()

    def rollback(self) -> None:
        if self._session is not None:
            self._session.rollback()


def _draft_values(draft: TripDraft) -> dict[str, Any]:
    return {
        "draft_id": draft.draft_id,
        "principal_id": draft.principal_id,
        "city_id": draft.city_id,
        "draft_version": draft.draft_version,
        "status": draft.status,
        "travel_facts": _facts_to_dict(draft.travel_facts),
        "selected_attraction_ids": list(draft.selected_attraction_ids),
        "visit_period_preferences": [
            {
                "attraction_id": item.attraction_id,
                "preferred_bucket": item.preferred_bucket,
                "acceptable_buckets": list(item.acceptable_buckets),
            }
            for item in draft.visit_period_preferences
        ],
        "created_at": draft.created_at.isoformat(),
        "updated_at": draft.updated_at.isoformat(),
    }


def _draft_from_row(row: TripDraftRow) -> TripDraft:
    return TripDraft(
        row.draft_id,
        row.principal_id,
        row.city_id,
        row.draft_version,
        row.status,
        _facts_from_dict(row.travel_facts),
        tuple(row.selected_attraction_ids),
        tuple(
            VisitPeriodPreferenceInput(
                item["attraction_id"],
                item["preferred_bucket"],
                tuple(item["acceptable_buckets"]),
            )
            for item in row.visit_period_preferences
        ),
        datetime.fromisoformat(row.created_at),
        datetime.fromisoformat(row.updated_at),
    )


def _intent_values(intent: GenerationIntent) -> dict[str, Any]:
    return {
        "generation_intent_id": intent.generation_intent_id,
        "principal_id": intent.principal_id,
        "draft_id": intent.draft_id,
        "draft_version": intent.draft_version,
        "status": intent.status.value,
        "input_schema_version": intent.input_schema_version,
        "input_snapshot": intent.input_snapshot,
        "input_snapshot_hash": intent.input_snapshot_hash,
        "data_snapshot_version": intent.data_snapshot_version,
        "random_seed": intent.random_seed,
        "submitted_at": intent.submitted_at.isoformat(),
        "updated_at": intent.updated_at.isoformat(),
        "trip_id": intent.trip_id,
        "trip_revision_id": intent.trip_revision_id,
        "failure_code": intent.failure_code,
        "target_trip_id": intent.target_trip_id,
        "base_revision_id": intent.base_revision_id,
    }


def _intent_from_row(row: GenerationIntentRow) -> GenerationIntent:
    return GenerationIntent(
        row.generation_intent_id,
        row.principal_id,
        row.draft_id,
        row.draft_version,
        GenerationStatus(row.status),
        row.input_schema_version,
        row.input_snapshot,
        row.input_snapshot_hash,
        row.data_snapshot_version,
        row.random_seed,
        datetime.fromisoformat(row.submitted_at),
        datetime.fromisoformat(row.updated_at),
        row.trip_id,
        row.trip_revision_id,
        row.failure_code,
        row.target_trip_id,
        row.base_revision_id,
    )


def _trip_values(trip: Trip) -> dict[str, Any]:
    return {
        "trip_id": trip.trip_id,
        "principal_id": trip.principal_id,
        "city_id": trip.city_id,
        "source_draft_id": trip.source_draft_id,
        "current_revision_id": trip.current_revision_id,
        "created_at": trip.created_at.isoformat(),
        "updated_at": trip.updated_at.isoformat(),
    }


def _trip_from_row(row: TripRow) -> Trip:
    return Trip(
        row.trip_id, row.principal_id, row.city_id, row.source_draft_id,
        row.current_revision_id, datetime.fromisoformat(row.created_at),
        datetime.fromisoformat(row.updated_at),
    )


def _revision_values(revision: TripRevision) -> dict[str, Any]:
    return {
        "trip_revision_id": revision.trip_revision_id,
        "trip_id": revision.trip_id,
        "revision_number": revision.revision_number,
        "generation_intent_id": revision.generation_intent_id,
        "completion_kind": revision.completion_kind.value,
        "has_soft_degradation": revision.has_soft_degradation,
        "result_schema_version": revision.result_schema_version,
        "result_snapshot": revision.result_snapshot,
        "result_snapshot_hash": revision.result_snapshot_hash,
        "created_at": revision.created_at.isoformat(),
    }


def _revision_from_row(row: TripRevisionRow) -> TripRevision:
    return TripRevision(
        row.trip_revision_id, row.trip_id, row.revision_number,
        row.generation_intent_id, CompletionKind(row.completion_kind),
        row.has_soft_degradation, row.result_schema_version, row.result_snapshot,
        row.result_snapshot_hash, datetime.fromisoformat(row.created_at),
    )


def _run_values(run: SolverRun) -> dict[str, Any]:
    return {
        "solver_run_id": run.solver_run_id,
        "generation_intent_id": run.generation_intent_id,
        "status": run.status,
        "quality_gate_passed": run.quality_gate_passed,
        "solver_version": run.solver_version,
        "constraint_version": run.constraint_version,
        "parameter_version": run.parameter_version,
        "audit_payload": run.audit_payload,
        "created_at": run.created_at.isoformat(),
    }


def _run_from_row(row: SolverRunRow) -> SolverRun:
    return SolverRun(
        row.solver_run_id, row.generation_intent_id, row.status,
        row.quality_gate_passed, row.solver_version, row.constraint_version,
        row.parameter_version, row.audit_payload, datetime.fromisoformat(row.created_at),
    )


def _facts_to_dict(facts: TravelFacts | None) -> dict[str, Any] | None:
    if facts is None:
        return None
    return {
        "start_date": facts.start_date.isoformat(),
        "end_date": facts.end_date.isoformat(),
        "arrival_transport_type": facts.arrival_transport_type.value,
        "arrival_confirmation": facts.arrival_confirmation.value,
        "arrival_at": facts.arrival_at.isoformat(),
        "station_to_city_min": facts.station_to_city_min,
        "station_to_city_source": facts.station_to_city_source,
        "departure_transport_type": facts.departure_transport_type.value,
        "departure_confirmation": facts.departure_confirmation.value,
        "departure_at": facts.departure_at.isoformat(),
        "station_early_min": facts.station_early_min,
        "station_early_source": facts.station_early_source,
        "last_visit_to_station_min": facts.last_visit_to_station_min,
        "last_visit_to_station_source": facts.last_visit_to_station_source,
        "travel_mode": facts.travel_mode.value,
        "crowd_type": facts.crowd_type.value,
    }


def _facts_from_dict(raw: dict[str, Any] | None) -> TravelFacts | None:
    if raw is None:
        return None
    return TravelFacts(
        date.fromisoformat(raw["start_date"]),
        date.fromisoformat(raw["end_date"]),
        TransportType(raw["arrival_transport_type"]),
        ConfirmationStatus(raw["arrival_confirmation"]),
        datetime.fromisoformat(raw["arrival_at"]),
        raw["station_to_city_min"],
        raw["station_to_city_source"],
        TransportType(raw["departure_transport_type"]),
        ConfirmationStatus(raw["departure_confirmation"]),
        datetime.fromisoformat(raw["departure_at"]),
        raw["station_early_min"],
        raw["station_early_source"],
        raw["last_visit_to_station_min"],
        raw["last_visit_to_station_source"],
        TravelMode(raw["travel_mode"]),
        CrowdType(raw["crowd_type"]),
    )
