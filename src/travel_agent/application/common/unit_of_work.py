"""Application transaction boundary."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from travel_agent.domain.planning.repositories import (
    GenerationIntentRepository,
    SolverRunRepository,
    TripDraftRepository,
    TripRepository,
    TripRevisionRepository,
)
from travel_agent.domain.sharing import PlanShareRepository


class UnitOfWork(Protocol):
    drafts: TripDraftRepository
    generation_intents: GenerationIntentRepository
    trips: TripRepository
    trip_revisions: TripRevisionRepository
    solver_runs: SolverRunRepository
    plan_shares: PlanShareRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
