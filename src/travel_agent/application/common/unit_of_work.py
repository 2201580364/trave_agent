"""Application transaction boundary."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from travel_agent.domain.planning.repositories import (
    GenerationIntentRepository,
    SolverRunRepository,
    TripRepository,
    TripDraftRepository,
    TripRevisionRepository,
)


class UnitOfWork(Protocol):
    drafts: TripDraftRepository
    generation_intents: GenerationIntentRepository
    trips: TripRepository
    trip_revisions: TripRevisionRepository
    solver_runs: SolverRunRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
