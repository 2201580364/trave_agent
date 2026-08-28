"""Production-oriented FastAPI composition root."""

from __future__ import annotations

import os
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
from travel_agent.infrastructure.sharing import HmacPlanShareTokenCodec
from travel_agent.infrastructure.solver import (
    ProductionSolverGateway,
    PublishedSolverDataProvider,
)

from .app import HttpContainer, create_app


@dataclass(frozen=True, slots=True)
class HttpSettings:
    database: DatabaseSettings
    plan_share_token_secret: str

    @classmethod
    def from_env(cls) -> HttpSettings:
        secret = os.environ.get("TRAVEL_AGENT_PLAN_SHARE_TOKEN_SECRET", "")
        if len(secret.encode("utf-8")) < 32:
            raise ValueError(
                "TRAVEL_AGENT_PLAN_SHARE_TOKEN_SECRET must contain at least 32 bytes"
            )
        return cls(DatabaseSettings.from_env(), secret)


def build_http_app(
    settings: HttpSettings,
    snapshots: DataSnapshotVersionProvider,
    published_data: PublishedSolverDataProvider,
):
    engine = build_engine(settings.database)
    sessions = build_session_factory(engine)
    clock = SystemClock()
    ids = UuidIdGenerator()

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(sessions)

    gateway = ProductionSolverGateway(published_data, clock)
    execute = ExecuteGenerationHandler(uow_factory(), clock, ids, gateway)
    identity = AnonymousIdentityService(sessions, clock, ids)
    share_tokens = HmacPlanShareTokenCodec(settings.plan_share_token_secret)
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
            share_tokens,
        )
    )
