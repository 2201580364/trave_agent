"""Repository contracts owned by the planning domain."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from .entities import GenerationIntent, SolverRun, Trip, TripDraft, TripRevision


class TripDraftRepository(Protocol):
    def get(self, draft_id: str) -> TripDraft | None: ...

    def save(self, draft: TripDraft, *, expected_version: int | None = None) -> None: ...


class GenerationIntentRepository(Protocol):
    def get(self, generation_intent_id: str) -> GenerationIntent | None: ...

    def add(self, intent: GenerationIntent) -> None: ...

    def save(
        self, intent: GenerationIntent, *, expected_status: str,
        expected_updated_at: datetime | None = None,
    ) -> None: ...

    def list_queued(self, *, limit: int) -> tuple[GenerationIntent, ...]: ...

    def recover_stale_running(self, *, before: datetime) -> int: ...


class TripRepository(Protocol):
    def get(self, trip_id: str) -> Trip | None: ...
    def list_by_principal(
        self,
        principal_id: str,
        *,
        limit: int,
        offset: int,
    ) -> tuple[Trip, ...]: ...
    def add(self, trip: Trip) -> None: ...
    def save(
        self,
        trip: Trip,
        *,
        expected_revision_id: str | None = None,
    ) -> None: ...


class TripRevisionRepository(Protocol):
    def get(self, trip_revision_id: str) -> TripRevision | None: ...
    def list_by_trip(self, trip_id: str) -> tuple[TripRevision, ...]: ...
    def count_by_trip_ids(self, trip_ids: tuple[str, ...]) -> dict[str, int]: ...
    def add(self, revision: TripRevision) -> None: ...


class SolverRunRepository(Protocol):
    def get(self, solver_run_id: str) -> SolverRun | None: ...
    def add(self, run: SolverRun) -> None: ...
