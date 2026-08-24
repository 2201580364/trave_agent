"""Production-oriented FastAPI composition root."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from travel_agent.application.planning import ExecuteGenerationHandler
from travel_agent.application.planning.ports import DataSnapshotVersionProvider
from travel_agent.infrastructure.database import (
    AnonymousIdentityService,
    SqlAlchemyUnitOfWork,
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
    database_url: str
    echo_sql: bool = False


def build_http_app(
    settings: HttpSettings,
    snapshots: DataSnapshotVersionProvider,
    published_data: PublishedSolverDataProvider,
):
    connect_args = (
        {"check_same_thread": False}
        if settings.database_url.startswith("sqlite")
        else {}
    )
    engine = create_engine(
        settings.database_url,
        echo=settings.echo_sql,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    sessions = sessionmaker[Session](engine, expire_on_commit=False)
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
        )
    )
