"""Production-oriented FastAPI composition root."""

from __future__ import annotations

from dataclasses import dataclass

from travel_agent.application.planning import ExecuteGenerationHandler
from travel_agent.application.planning.ports import DataSnapshotVersionProvider
from travel_agent.infrastructure.database import (
    AnonymousIdentityService,
    DatabaseReadiness,
    DatabaseSettings,
    SqlAlchemyUnitOfWork,
    build_engine,
    build_session_factory,
)
from travel_agent.infrastructure.execution import InlineGenerationExecutor
from travel_agent.infrastructure.ids import UuidIdGenerator
from travel_agent.infrastructure.memory import SystemClock
from travel_agent.infrastructure.solver import (
    ProductionSolverGateway,
    PublishedSolverDataProvider,
)

from .app import HttpContainer, create_app


@dataclass(frozen=True, slots=True)
class HttpSettings:
    database: DatabaseSettings

    @classmethod
    def from_env(cls) -> HttpSettings:
        return cls(DatabaseSettings.from_env())


def build_http_app(
    settings: HttpSettings,
    snapshots: DataSnapshotVersionProvider,
    published_data: PublishedSolverDataProvider,
):
    engine = build_engine(settings.database)
    sessions = build_session_factory(engine)
    clock = SystemClock()
    ids = UuidIdGenerator()
    uow_factory = lambda: SqlAlchemyUnitOfWork(sessions)
    gateway = ProductionSolverGateway(published_data, clock)
    execute = ExecuteGenerationHandler(uow_factory(), clock, ids, gateway)
    identity = AnonymousIdentityService(sessions, clock, ids)
    return create_app(
        HttpContainer(
            uow_factory,
            clock,
            ids,
            snapshots,
            InlineGenerationExecutor(execute),
            identity,
            published_data,
            DatabaseReadiness(sessions).check,
        )
    )
