"""Production-oriented FastAPI composition root."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from fastapi import FastAPI

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
from travel_agent.infrastructure.provider_governance import (
    ProviderBlockCode,
    ProviderGovernancePolicy,
    ProviderRequestBlocked,
    build_provider_request_governor,
)
from travel_agent.infrastructure.sharing import HmacPlanShareTokenCodec
from travel_agent.infrastructure.solver import (
    DatabasePublishedSnapshotVersionProvider,
    DatabasePublishedSolverDataProvider,
    ProductionSolverGateway,
    PublishedSolverDataProvider,
)
from travel_agent.infrastructure.solver.gaode import (
    GaodeODSnapshotBuilder,
    GaodeRouteClient,
    GaodeSettings,
    RedisGaodeRouteCache,
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
        if (self.admin_bootstrap_login is None) != (self.admin_bootstrap_password is None):
            raise ValueError("admin bootstrap login and password must be configured together")

    @classmethod
    def from_env(cls) -> HttpSettings:
        secret = os.environ.get("TRAVEL_AGENT_PLAN_SHARE_TOKEN_SECRET", "")
        if len(secret.encode("utf-8")) < 32:
            raise ValueError("TRAVEL_AGENT_PLAN_SHARE_TOKEN_SECRET must contain at least 32 bytes")
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
    snapshots: DataSnapshotVersionProvider | None,
    published_data: PublishedSolverDataProvider | None = None,
    *,
    published_fallback: PublishedSolverDataProvider | None = None,
    published_city_id: str = "hangzhou",
    published_fallback_version: str = "hangzhou-local-v1",
) -> FastAPI:
    engine = build_engine(settings.database)
    sessions = build_session_factory(engine)
    if published_data is None:
        if published_fallback is None:
            raise ValueError("published fallback provider is required")
        published_data = DatabasePublishedSolverDataProvider(
            sessions,
            city_id=published_city_id,
            fallback=published_fallback,
            fallback_version=published_fallback_version,
        )
        snapshots = DatabasePublishedSnapshotVersionProvider(
            sessions,
            fallback_version=published_fallback_version,
        )
    ensure_builtin_holiday_calendar_seeds(sessions)
    if snapshots is None:
        raise ValueError("snapshot version provider is required")
    clock = SystemClock()
    ids = UuidIdGenerator()

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(sessions)

    od_builder = None
    od_source = os.environ.get("TRAVEL_AGENT_OD_SOURCE", "approximate")
    if od_source not in {"approximate", "gaode"}:
        raise ValueError("TRAVEL_AGENT_OD_SOURCE must be approximate or gaode")
    if od_source == "gaode":
        gaode_settings = GaodeSettings.from_env(load_dotenv_file=False)
        redis_url = os.environ.get("TRAVEL_AGENT_PROVIDER_REDIS_URL", "").strip()
        cache = RedisGaodeRouteCache.from_url(redis_url) if redis_url else None
        governor = build_provider_request_governor(
            ProviderGovernancePolicy(
                provider="gaode",
                daily_request_budget=int(
                    os.environ.get("TRAVEL_AGENT_GAODE_DAILY_REQUEST_BUDGET", "1000")
                ),
                minimum_interval_seconds=1.05,
                circuit_failure_codes=frozenset(
                    {"timeout", "http_error", "api_error", "invalid_response"}
                ),
            ),
            clock.now,
            json_path=Path("var/ops/provider-governance.json"),
            redis_url=redis_url,
        )

        def before_request() -> None:
            while True:
                try:
                    governor.before_request()
                    return
                except ProviderRequestBlocked as exc:
                    if exc.code is not ProviderBlockCode.RATE_WINDOW or exc.retry_at is None:
                        raise
                    time.sleep(max(0, (exc.retry_at - clock.now()).total_seconds()))

        od_builder = GaodeODSnapshotBuilder(
            gaode_settings,
            GaodeRouteClient(
                gaode_settings,
                clock.now,
                cache=cache,
                before_request=before_request,
                on_success=governor.record_success,
                on_failure=governor.record_failure,
            ),
        )
    gateway = ProductionSolverGateway(published_data, clock, od_builder=od_builder)
    execute = ExecuteGenerationHandler(uow_factory(), clock, ids, gateway)
    identity = AnonymousIdentityService(sessions, clock, ids)
    admin_identity = AdminIdentityService(lambda: SqlAlchemyAdminUnitOfWork(sessions), clock, ids)
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
        holiday_http = httpx.Client(headers={"User-Agent": "travel-agent-holiday-sync/1.0"})
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
    if settings.admin_bootstrap_login is not None and settings.admin_bootstrap_password is not None:
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
