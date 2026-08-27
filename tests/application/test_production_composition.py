"""A6-8.1 production published-snapshot composition tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI

from travel_agent.infrastructure.database import DatabaseSettings
from travel_agent.infrastructure.solver import published_snapshot_content_hash
from travel_agent.interfaces.http import (
    ProductionHttpSettings,
    PublishedSnapshotSettings,
    build_production_http_app,
)

VERSION = "hangzhou-published-composition-v1"


def test_production_settings_load_database_and_snapshot_selection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRAVEL_AGENT_DATABASE_URL", "sqlite:///./production-test.db")
    monkeypatch.setenv("TRAVEL_AGENT_PUBLISHED_SNAPSHOT_ROOT", str(tmp_path))
    monkeypatch.setenv("TRAVEL_AGENT_PUBLISHED_CITY_ID", "hangzhou")
    monkeypatch.setenv("TRAVEL_AGENT_PUBLISHED_SNAPSHOT_VERSION", VERSION)

    settings = ProductionHttpSettings.from_env(dotenv_path=tmp_path / "missing.env")

    assert settings.database.url == "sqlite:///./production-test.db"
    assert settings.published_snapshot.root == tmp_path.resolve()
    assert settings.published_snapshot.city_id == "hangzhou"
    assert settings.published_snapshot.version == VERSION


def test_production_settings_require_explicit_published_version(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRAVEL_AGENT_PUBLISHED_SNAPSHOT_ROOT", str(tmp_path))
    monkeypatch.setenv("TRAVEL_AGENT_PUBLISHED_CITY_ID", "hangzhou")
    monkeypatch.delenv("TRAVEL_AGENT_PUBLISHED_SNAPSHOT_VERSION", raising=False)

    with pytest.raises(ValueError, match="snapshot version is required"):
        PublishedSnapshotSettings.from_env(load_dotenv_file=False)


def test_relative_snapshot_root_resolves_from_dotenv_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "TRAVEL_AGENT_DATABASE_URL=sqlite:///./relative.db\n"
        "TRAVEL_AGENT_PUBLISHED_SNAPSHOT_ROOT=published\n"
        "TRAVEL_AGENT_PUBLISHED_CITY_ID=hangzhou\n"
        f"TRAVEL_AGENT_PUBLISHED_SNAPSHOT_VERSION={VERSION}\n",
        encoding="utf-8",
    )
    for name in (
        "TRAVEL_AGENT_DATABASE_URL",
        "TRAVEL_AGENT_PUBLISHED_SNAPSHOT_ROOT",
        "TRAVEL_AGENT_PUBLISHED_CITY_ID",
        "TRAVEL_AGENT_PUBLISHED_SNAPSHOT_VERSION",
    ):
        monkeypatch.delenv(name, raising=False)

    try:
        settings = ProductionHttpSettings.from_env(dotenv_path=dotenv)

        assert settings.published_snapshot.root == (tmp_path / "published").resolve()
    finally:
        # python-dotenv mutates os.environ outside monkeypatch's setenv tracking.
        # Remove those values before later Alembic tests inspect the environment.
        for name in (
            "TRAVEL_AGENT_DATABASE_URL",
            "TRAVEL_AGENT_PUBLISHED_SNAPSHOT_ROOT",
            "TRAVEL_AGENT_PUBLISHED_CITY_ID",
            "TRAVEL_AGENT_PUBLISHED_SNAPSHOT_VERSION",
        ):
            os.environ.pop(name, None)


def test_production_composition_loads_verified_published_snapshot(
    tmp_path: Path,
) -> None:
    _write_snapshot(tmp_path, _snapshot())

    app = build_production_http_app(_settings(tmp_path))

    assert isinstance(app, FastAPI)


def test_production_composition_rejects_candidate_snapshot(tmp_path: Path) -> None:
    _write_snapshot(tmp_path, _snapshot(status="candidate"))

    with pytest.raises(ValueError, match="invalid published solver snapshot"):
        build_production_http_app(_settings(tmp_path))


def test_production_composition_rejects_snapshot_city_mismatch(tmp_path: Path) -> None:
    _write_snapshot(tmp_path, _snapshot(city_id="shanghai"))

    with pytest.raises(ValueError, match="snapshot city mismatch"):
        build_production_http_app(_settings(tmp_path))


def _settings(root: Path) -> ProductionHttpSettings:
    return ProductionHttpSettings(
        DatabaseSettings(url="sqlite://"),
        PublishedSnapshotSettings(root, "hangzhou", VERSION),
    )


def _write_snapshot(root: Path, snapshot: dict[str, Any]) -> None:
    payload = {
        "schema_version": "published-solver-data-v1",
        "content_hash": published_snapshot_content_hash(snapshot),
        "snapshot": snapshot,
    }
    (root / f"{VERSION}.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def _snapshot(
    *,
    status: str = "published",
    city_id: str = "hangzhou",
) -> dict[str, Any]:
    attractions = [
        {
            "external_id": f"attr_{attraction_id}",
            "id": attraction_id,
            "name": name,
            "close_days": [],
            "open_on_dates": [],
            "closed_on_dates": [],
            "suggested_duration": 60,
            "time_rules": [],
            "is_always_open": True,
            "is_indoor": False,
            "energy_level": 1,
            "data_verified": True,
            "conflict": False,
            "active": True,
            "coordinate": {
                "lat": 30.25,
                "lng": lng,
                "gaode_poi_id": f"gaode-poi-{attraction_id}",
                "point_kind": "area_representative",
                "source": "gaode_web_service_v3",
                "fetched_at": "2026-08-26",
                "review_status": "human_verified",
            },
        }
        for attraction_id, name, lng in (
            (1, "湖滨公园", 120.158818),
            (2, "音乐喷泉", 120.160970),
        )
    ]
    od_pairs = [
        {
            "origin_id": origin,
            "destination_id": destination,
            "status": "available",
            "travel_min": travel_min,
            "travel_mode": "walking",
            "distance_m": distance,
            "basis": "gaode",
            "data_version": "gaode-composition-test-v1",
            "fetched_at": "2026-08-26T09:00:00+00:00",
            "fallback_reason": None,
        }
        for origin, destination, travel_min, distance in (
            (1, 2, 6, 386),
            (2, 1, 5, 324),
        )
    ]
    return {
        "version": VERSION,
        "status": status,
        "city_id": city_id,
        "od_version": "gaode-composition-test-v1",
        "od_basis": "gaode",
        "weather_basis": "forecast",
        "attractions": attractions,
        "weather": [
            {
                "date": "2026-09-01",
                "basis": "forecast",
                "severity": "normal",
                "condition": "sunny",
                "condition_code": "100",
                "source_ref": "qweather:101210101:weather-composition-test-v1:2026-09-01",
                "fetched_at": "2026-08-31T08:00:00+00:00",
            }
        ],
        "od_pairs": od_pairs,
    }
