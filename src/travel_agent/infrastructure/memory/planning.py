"""Transactional in-memory planning adapters.

These adapters are application-test tools, not production persistence.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from typing import Self

from travel_agent.application.common.errors import (
    DraftVersionConflictError,
    GenerationIntentConflictError,
    TripRevisionConflictError,
)
from travel_agent.domain.planning import (
    GenerationIntent,
    SolverRun,
    Trip,
    TripDraft,
    TripRevision,
)


@dataclass(slots=True)
class InMemoryPlanningStore:
    drafts: dict[str, TripDraft] = field(default_factory=dict)
    generation_intents: dict[str, GenerationIntent] = field(default_factory=dict)
    trips: dict[str, Trip] = field(default_factory=dict)
    trip_revisions: dict[str, TripRevision] = field(default_factory=dict)
    solver_runs: dict[str, SolverRun] = field(default_factory=dict)


class InMemoryTripDraftRepository:
    def __init__(self, records: dict[str, TripDraft]) -> None:
        self._records = records

    def get(self, draft_id: str) -> TripDraft | None:
        return self._records.get(draft_id)

    def save(self, draft: TripDraft, *, expected_version: int | None = None) -> None:
        current = self._records.get(draft.draft_id)
        if expected_version is None:
            if current is not None:
                raise ValueError("draft already exists")
        elif current is None or current.draft_version != expected_version:
            raise DraftVersionConflictError(
                expected_version=expected_version,
                current_version=current.draft_version if current is not None else 0,
            )
        self._records[draft.draft_id] = draft


class InMemoryGenerationIntentRepository:
    def __init__(self, records: dict[str, GenerationIntent]) -> None:
        self._records = records

    def get(self, generation_intent_id: str) -> GenerationIntent | None:
        return self._records.get(generation_intent_id)

    def add(self, intent: GenerationIntent) -> None:
        if intent.generation_intent_id in self._records:
            raise GenerationIntentConflictError
        self._records[intent.generation_intent_id] = intent

    def save(self, intent: GenerationIntent, *, expected_status: str) -> None:
        current = self._records.get(intent.generation_intent_id)
        if current is None or current.status.value != expected_status:
            raise ValueError("generation intent status conflict")
        self._records[intent.generation_intent_id] = intent


class _InMemoryAddRepository:
    def __init__(self, records: dict[str, object], id_field: str) -> None:
        self._records = records
        self._id_field = id_field

    def get(self, record_id: str) -> object | None:
        return self._records.get(record_id)

    def add(self, record: object) -> None:
        record_id = str(getattr(record, self._id_field))
        if record_id in self._records:
            raise ValueError(f"{self._id_field} already exists")
        self._records[record_id] = record

    def save(self, record: object) -> None:
        record_id = str(getattr(record, self._id_field))
        if record_id not in self._records:
            raise ValueError(f"{self._id_field} does not exist")
        self._records[record_id] = record


class InMemoryTripRepository(_InMemoryAddRepository):
    def __init__(self, records: dict[str, Trip]) -> None:
        super().__init__(records, "trip_id")
        self._trip_records = records

    def list_by_principal(
        self,
        principal_id: str,
        *,
        limit: int,
        offset: int,
    ) -> tuple[Trip, ...]:
        matching = sorted(
            (
                trip
                for trip in self._trip_records.values()
                if trip.principal_id == principal_id
            ),
            key=lambda trip: (-trip.updated_at.timestamp(), trip.trip_id),
        )
        return tuple(matching[offset : offset + limit])

    def save(
        self,
        record: Trip,
        *,
        expected_revision_id: str | None = None,
    ) -> None:
        current = self._trip_records.get(record.trip_id)
        if current is None:
            raise ValueError("trip_id does not exist")
        if (
            expected_revision_id is not None
            and current.current_revision_id != expected_revision_id
        ):
            raise TripRevisionConflictError
        self._trip_records[record.trip_id] = record


class InMemoryTripRevisionRepository(_InMemoryAddRepository):
    def __init__(self, records: dict[str, TripRevision]) -> None:
        super().__init__(records, "trip_revision_id")
        self._revision_records = records

    def list_by_trip(self, trip_id: str) -> tuple[TripRevision, ...]:
        return tuple(
            sorted(
                (
                    revision
                    for revision in self._revision_records.values()
                    if revision.trip_id == trip_id
                ),
                key=lambda revision: (
                    -revision.revision_number,
                    revision.trip_revision_id,
                ),
            )
        )


class InMemoryUnitOfWork:
    def __init__(self, store: InMemoryPlanningStore) -> None:
        self._store = store
        self._working: InMemoryPlanningStore | None = None
        self._committed = False
        self.drafts = InMemoryTripDraftRepository({})
        self.generation_intents = InMemoryGenerationIntentRepository({})
        self.trips = InMemoryTripRepository({})
        self.trip_revisions = InMemoryTripRevisionRepository({})
        self.solver_runs = _InMemoryAddRepository({}, "solver_run_id")

    def __enter__(self) -> Self:
        self._working = deepcopy(self._store)
        self.drafts = InMemoryTripDraftRepository(self._working.drafts)
        self.generation_intents = InMemoryGenerationIntentRepository(
            self._working.generation_intents
        )
        self.trips = InMemoryTripRepository(self._working.trips)
        self.trip_revisions = InMemoryTripRevisionRepository(
            self._working.trip_revisions
        )
        self.solver_runs = _InMemoryAddRepository(
            self._working.solver_runs, "solver_run_id"
        )
        self._committed = False
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if exc_type is not None or not self._committed:
            self.rollback()
        self._working = None
        return None

    def commit(self) -> None:
        if self._working is None:
            raise RuntimeError("unit of work is not active")
        self._store.drafts = deepcopy(self._working.drafts)
        self._store.generation_intents = deepcopy(self._working.generation_intents)
        self._store.trips = deepcopy(self._working.trips)
        self._store.trip_revisions = deepcopy(self._working.trip_revisions)
        self._store.solver_runs = deepcopy(self._working.solver_runs)
        self._committed = True

    def rollback(self) -> None:
        self._committed = False


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class SequenceIdGenerator:
    def __init__(self) -> None:
        self._next = 1

    def new_id(self, prefix: str) -> str:
        value = f"{prefix}_{self._next:06d}"
        self._next += 1
        return value


class FixedDataSnapshotVersionProvider:
    def __init__(self, versions: dict[str, str]) -> None:
        self._versions = versions

    def current_version(self, city_id: str) -> str:
        try:
            return self._versions[city_id]
        except KeyError as exc:
            raise ValueError(f"no published data snapshot for city {city_id}") from exc


class InMemoryGenerationExecutor:
    def __init__(self) -> None:
        self.submitted: list[str] = []

    def submit(self, generation_intent_id: str) -> None:
        self.submitted.append(generation_intent_id)
