"""Local A6 browser-slice composition with deterministic Hangzhou data.

This module is deliberately separate from the production composition root. It
uses the production database, HTTP, application and solver adapters, while the
published catalog remains an explicit local fixture until the real publication
tables are implemented. Traceability: H3, A6-7, C1, C2, C5, C6.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from typing import cast

from fastapi import FastAPI

from travel_agent.infrastructure.database import (
    DatabaseSettings,
    build_engine,
    build_session_factory,
)
from travel_agent.infrastructure.holiday_sync import HolidaySyncSettings
from travel_agent.infrastructure.memory import FixedDataSnapshotVersionProvider
from travel_agent.infrastructure.solver import (
    InMemoryPublishedSolverDataProvider,
    DatabasePublishedSnapshotVersionProvider,
    DatabasePublishedSolverDataProvider,
    PublishedAttraction,
    PublishedSolverData,
)
from travel_agent.interfaces.http import HttpSettings, build_http_app
from travel_agent.solver import (
    ApproximateTravelTimeProvider,
    Attraction,
    Coordinate,
    DailyWeather,
    TimeRule,
    WeatherBasis,
    WeatherSeverity,
)

LOCAL_SNAPSHOT_VERSION = "hangzhou-local-v1"
DEFAULT_LOCAL_DATABASE_URL = "sqlite:///./.local/travel_agent.db"


def build_local_dev_app(
    *,
    database_url: str | None = None,
    reference_date: date | None = None,
) -> FastAPI:
    """Build the real A6 HTTP stack with local-only published input data."""

    _, fallback_catalog = build_local_hangzhou_catalog(reference_date=reference_date)
    resolved_url = database_url or os.environ.get(
        "TRAVEL_AGENT_DATABASE_URL", DEFAULT_LOCAL_DATABASE_URL
    )
    engine = build_engine(DatabaseSettings(url=resolved_url))
    sessions = build_session_factory(engine)
    snapshots = DatabasePublishedSnapshotVersionProvider(
        sessions, fallback_version=LOCAL_SNAPSHOT_VERSION
    )
    catalog = DatabasePublishedSolverDataProvider(
        sessions,
        city_id="hangzhou",
        fallback=fallback_catalog,
    )
    return cast(
        FastAPI,
        build_http_app(
            HttpSettings(
                DatabaseSettings(url=resolved_url),
                "local-only-plan-share-secret-2026-08-28-do-not-use-production",
                os.environ.get("TRAVEL_AGENT_ADMIN_BOOTSTRAP_LOGIN") or None,
                os.environ.get("TRAVEL_AGENT_ADMIN_BOOTSTRAP_PASSWORD") or None,
                HolidaySyncSettings.from_env(load_dotenv_file=False),
            ),
            snapshots,
            catalog,
        ),
    )


def build_local_hangzhou_catalog(
    *, reference_date: date | None = None
) -> tuple[FixedDataSnapshotVersionProvider, InMemoryPublishedSolverDataProvider]:
    """Return a deterministic, clearly labelled local Hangzhou publication."""

    today = reference_date or date.today()
    coordinates = {
        1: Coordinate(30.2590, 120.1650),
        2: Coordinate(30.2409, 120.1022),
        3: Coordinate(30.2417, 120.1040),
        4: Coordinate(30.2525, 120.1495),
        5: Coordinate(30.2301, 120.1484),
        6: Coordinate(30.2420, 120.1690),
        7: Coordinate(30.2592, 120.1662),
    }
    attractions = (
        _published(
            "attr_west_lake",
            1,
            "西湖湖滨",
            coordinates[1],
            duration=150,
            energy=3,
            always_open=True,
        ),
        _published(
            "attr_lingyin_temple",
            2,
            "灵隐寺",
            coordinates[2],
            duration=180,
            energy=4,
            rules=_rule("07:00", "17:30", "16:30"),
        ),
        _published(
            "attr_feilai_peak",
            3,
            "飞来峰",
            coordinates[3],
            duration=120,
            energy=4,
            rules=_rule("07:00", "17:30", "16:30"),
        ),
        _published(
            "attr_zhejiang_museum",
            4,
            "浙江省博物馆",
            coordinates[4],
            duration=120,
            energy=2,
            indoor=True,
            close_days=frozenset({1}),
            rules=_rule("09:00", "17:00", "16:30"),
        ),
        _published(
            "attr_leifeng_pagoda",
            5,
            "雷峰塔",
            coordinates[5],
            duration=90,
            energy=3,
            rules=_rule("08:00", "19:00", "18:30"),
        ),
        _published(
            "attr_hefang_street",
            6,
            "河坊街",
            coordinates[6],
            duration=120,
            energy=2,
            rules=_rule("09:00", "22:00"),
        ),
        _published(
            "attr_fountain_show",
            7,
            "湖滨喷泉灯光秀",
            coordinates[7],
            duration=30,
            energy=1,
            rules=_rule("18:30", "19:00"),
        ),
    )
    weather = {
        day: DailyWeather(
            day,
            WeatherBasis.FORECAST,
            WeatherSeverity.NORMAL,
            "local deterministic normal weather",
        )
        for day in (today + timedelta(days=offset) for offset in range(-30, 401))
    }
    published = PublishedSolverData(
        version=LOCAL_SNAPSHOT_VERSION,
        city_id="hangzhou",
        attractions=attractions,
        weather_by_date=weather,
        travel_time_provider=ApproximateTravelTimeProvider(
            coordinates,
            speed_kmh=18,
            detour_ratio=1.6,
            minimum_travel_min=5,
            data_version="hangzhou-local-approx-od-v1",
            fetched_at=datetime.combine(today, datetime.min.time(), tzinfo=UTC),
        ),
        od_basis="approximate_local_fixture",
        weather_basis="deterministic_local_fixture",
    )
    return (
        FixedDataSnapshotVersionProvider({"hangzhou": LOCAL_SNAPSHOT_VERSION}),
        InMemoryPublishedSolverDataProvider((published,)),
    )


def _rule(
    open_time: str, close_time: str, last_entry: str | None = None
) -> tuple[TimeRule, ...]:
    return (
        TimeRule.from_strings(
            ("01-01", "12-31"), open_time, close_time, last_entry
        ),
    )


def _published(
    external_id: str,
    attraction_id: int,
    name: str,
    coordinate: Coordinate,
    *,
    duration: int,
    energy: int,
    rules: tuple[TimeRule, ...] = (),
    always_open: bool = False,
    indoor: bool = False,
    close_days: frozenset[int] = frozenset(),
) -> PublishedAttraction:
    return PublishedAttraction(
        external_id=external_id,
        attraction=Attraction(
            attraction_id,
            name,
            close_days=close_days,
            suggested_duration=duration,
            time_rules=rules,
            is_always_open=always_open,
            is_indoor=indoor,
            energy_level=energy,
            data_verified=True,
        ),
        coordinate=coordinate,
    )


app = build_local_dev_app()
