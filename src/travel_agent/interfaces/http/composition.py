"""Production-oriented FastAPI composition root."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from travel_agent.application.admin import (
    AdminIdentityService,
    GovernedSourceCatalog,
    PlaceReviewWorkflowService,
)
from travel_agent.application.admin.holiday_calendar_sync import (
    ChinaHolidayCalendarSyncService,
)
from travel_agent.application.planning import ExecuteGenerationHandler
from travel_agent.application.planning.ports import DataSnapshotVersionProvider
from travel_agent.infrastructure.database import (
    AnonymousIdentityService,
    DatabaseReadiness,
    DatabaseSettings,
    SqlAlchemyAdminUnitOfWork,
    SqlAlchemyHolidayCalendarUnitOfWork,
    SqlAlchemyPublishedHolidayCalendarCatalog,
    SqlAlchemyUnitOfWork,
    build_engine,
    build_session_factory,
    ensure_builtin_holiday_calendar_seeds,
)
from travel_agent.infrastructure.execution import InlineGenerationExecutor
from travel_agent.infrastructure.holiday_sync import (
    AiHolidayAnnouncementExtractor,
    GovCnAnnouncementDiscoverer,
    GovCnAnnouncementFetcher,
    HolidaySyncSettings,
    OpenAiCompatibleStructuredHolidayModel,
)
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
    holiday_sync: HolidaySyncSettings = field(default_factory=HolidaySyncSettings)

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
            HolidaySyncSettings.from_env(load_dotenv_file=False),
        )


def build_http_app(
    settings: HttpSettings,
    snapshots: DataSnapshotVersionProvider,
    published_data: PublishedSolverDataProvider,
):
    engine = build_engine(settings.database)
    sessions = build_session_factory(engine)
    ensure_builtin_holiday_calendar_seeds(sessions)
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
    review_workflow = PlaceReviewWorkflowService(
        lambda: SqlAlchemyAdminUnitOfWork(sessions),
        clock,
        ids,
        GovernedSourceCatalog.from_files(
            Path(__file__).resolve().parents[4]
            / "data/governance/hangzhou-source-registry-v1.json",
            Path(__file__).resolve().parents[4]
            / "data/governance/place-collection-field-dictionary-v1.json",
        ),
        SqlAlchemyPublishedHolidayCalendarCatalog(sessions),
    )
    holiday_settings = settings.holiday_sync
    discoverer = fetcher = extractor = None
    if holiday_settings.configured:
        holiday_http = httpx.Client(
            headers={"User-Agent": "travel-agent-holiday-sync/1.0"}
        )
        discoverer = GovCnAnnouncementDiscoverer(holiday_http)
        fetcher = GovCnAnnouncementFetcher(holiday_http)
        extractor = AiHolidayAnnouncementExtractor(
            OpenAiCompatibleStructuredHolidayModel(
                holiday_http,
                base_url=holiday_settings.model_base_url,
                api_key=holiday_settings.model_api_key,
                model=holiday_settings.model_name,
                timeout_seconds=holiday_settings.timeout_seconds,
            )
        )
    holiday_calendar_sync = ChinaHolidayCalendarSyncService(
        lambda: SqlAlchemyHolidayCalendarUnitOfWork(sessions),
        clock,
        ids,
        discoverer,
        fetcher,
        extractor,
        worker_available=holiday_settings.configured,
        job_submission_available=holiday_settings.configured,
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
            review_workflow,
            holiday_calendar_sync,
        )
    )
