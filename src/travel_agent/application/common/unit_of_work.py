"""Application transaction boundary."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from travel_agent.domain.feedback import FeedbackRepository
from travel_agent.domain.planning.repositories import (
    GenerationIntentRepository,
    SolverRunRepository,
    TripDraftRepository,
    TripRepository,
    TripRevisionRepository,
)
from travel_agent.domain.sharing import PlanShareRepository


class UnitOfWork(Protocol):
    @property
    def drafts(self) -> TripDraftRepository: ...
    @property
    def generation_intents(self) -> GenerationIntentRepository: ...
    @property
    def trips(self) -> TripRepository: ...
    @property
    def trip_revisions(self) -> TripRevisionRepository: ...
    @property
    def solver_runs(self) -> SolverRunRepository: ...
    @property
    def plan_shares(self) -> PlanShareRepository: ...
    @property
    def feedbacks(self) -> FeedbackRepository: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
