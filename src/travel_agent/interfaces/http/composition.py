"""Production-oriented FastAPI composition root."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from travel_agent.application.admin import AdminIdentityService
from travel_agent.application.planning import ExecuteGenerationHandler
from travel_agent.application.planning.ports import DataSnapshotVersionProvider
from travel_agent.infrastructure.database import (
    AnonymousIdentityService,
    DatabaseReadiness,
    DatabaseSettings,
    SqlAlchemyAdminUnitOfWork,
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
    admin_bootstrap_login: str | None = None
    admin_bootstrap_password: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if (self.admin_bootstrap_login is None) != (
            self.admin_bootstrap_password is None
        ):
            raise ValueError(
                "admin bootstrap login and password must be configured together"
            )

    @classmethod
    def from_env(cls) -> HttpSettings:
        secret = os.environ.get("TRAVEL_AGENT_PLAN_SHARE_TOKEN_SECRET", "")
        if len(secret.encode("utf-8")) < 32:
            raise ValueError(
                "TRAVEL_AGENT_PLAN_SHARE_TOKEN_SECRET must contain at least 32 bytes"
            )
        login = os.environ.get("TRAVEL_AGENT_ADMIN_BOOTSTRAP_LOGIN", "").strip()
        password = os.environ.get("TRAVEL_AGENT_ADMIN_BOOTSTRAP_PASSWORD", "")
        return cls(
            DatabaseSettings.from_env(),
            secret,
            login or None,
            password or None,
        )


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
    admin_identity = AdminIdentityService(
        lambda: SqlAlchemyAdminUnitOfWork(sessions), clock, ids
    )
    if (
        settings.admin_bootstrap_login is not None
        and settings.admin_bootstrap_password is not None
    ):
        admin_identity.bootstrap_initial_admin(
            settings.admin_bootstrap_login,
            settings.admin_bootstrap_password,
        )
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
            admin_identity,
        )
    )
