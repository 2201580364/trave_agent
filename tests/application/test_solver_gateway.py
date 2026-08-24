"""A6-4 production SolverGateway integration tests."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime

import pytest

from travel_agent.application.planning.ports import SolverExecutionError, SolverRequest
from travel_agent.domain.planning import CompletionKind
from travel_agent.infrastructure.solver import (
    InMemoryPublishedSolverDataProvider,
    PublishedAttraction,
    PublishedSolverData,
    ProductionSolverGateway,
)
from travel_agent.solver import (
    ApproximateTravelTimeProvider,
    Attraction,
    Coordinate,
    DailyWeather,
    WeatherBasis,
    WeatherSeverity,
)


TODAY = date(2026, 9, 1)
NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
VERSION = "hangzhou-2026-08-24-v1"


class FixedClock:
    def now(self) -> datetime:
        return NOW


def _published() -> PublishedSolverData:
    attractions = (
        PublishedAttraction(
            "attr_west_lake",
            Attraction(
                1, "西湖湖滨", suggested_duration=90,
                is_always_open=True, energy_level=2, data_verified=True,
            ),
            Coordinate(30.2590, 120.1650),
        ),
        PublishedAttraction(
            "attr_fountain",
            Attraction(
                2, "湖滨晚间表演", suggested_duration=30,
                is_always_open=True, energy_level=1, data_verified=True,
            ),
            Coordinate(30.2591, 120.1660),
        ),
    )
    coordinates = {
        item.attraction.id: item.coordinate
        for item in attractions
        if item.coordinate is not None
    }
    provider = ApproximateTravelTimeProvider(
        coordinates,
        data_version=VERSION,
        fetched_at=NOW,
    )
    weather = {
        TODAY: DailyWeather(
            TODAY, WeatherBasis.FORECAST, WeatherSeverity.NORMAL, "sunny"
        )
    }
    return PublishedSolverData(
        VERSION, "hangzhou", attractions, weather, provider,
        "approximate", "forecast",
    )


def _request(*, attraction_ids: list[str] | None = None) -> SolverRequest:
    snapshot = {
        "schema_version": "generation-input-v1",
        "city_id": "hangzhou",
        "travel_facts": {
            "start_date": TODAY.isoformat(),
            "end_date": TODAY.isoformat(),
            "arrival_at": "2026-09-01T09:00:00+08:00",
            "departure_at": "2026-09-01T21:00:00+08:00",
            "station_to_city_min": 0,
            "station_early_min": 0,
            "last_visit_to_station_min": 0,
            "travel_mode": "normal",
        },
        "selected_attraction_ids": attraction_ids or [
            "attr_west_lake", "attr_fountain"
        ],
        "visit_period_preferences": [
            {
                "attraction_id": "attr_fountain",
                "preferred_bucket": "evening",
                "acceptable_buckets": ["afternoon"],
            }
        ],
        "data_snapshot_version": VERSION,
    }
    serialized = json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    snapshot_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return SolverRequest(
        "solver_run_1", "intent_1", snapshot, snapshot_hash, VERSION, 7
    )


def _gateway() -> ProductionSolverGateway:
    provider = InMemoryPublishedSolverDataProvider((_published(),))
    return ProductionSolverGateway(provider, FixedClock())


def test_gateway_runs_frozen_solver_and_maps_stable_result() -> None:
    first = _gateway().solve(_request())
    second = _gateway().solve(_request())

    assert first.quality_gate_passed is True
    assert first.completion_kind is CompletionKind.COMPLETE_SUCCESS
    assert first.result_snapshot_hash == second.result_snapshot_hash
    assert first.result_snapshot["accounting"]["conserved"] is True
    nodes = first.result_snapshot["days"][0]["nodes"]
    assert {item["attraction_id"] for item in nodes} == {
        "attr_west_lake", "attr_fountain"
    }
    assert [item["node_id"] for item in nodes] == [
        item["node_id"] for item in second.result_snapshot["days"][0]["nodes"]
    ]
    assert first.audit_payload["solve_run_id"] == "solver_run_1"
    assert first.audit_payload["data_snapshot_version"] == VERSION


def test_missing_published_snapshot_is_retryable() -> None:
    gateway = ProductionSolverGateway(InMemoryPublishedSolverDataProvider(()), FixedClock())

    with pytest.raises(SolverExecutionError) as raised:
        gateway.solve(_request())

    assert raised.value.code == "data_snapshot_unavailable"
    assert raised.value.retryable is True


def test_unknown_selected_attraction_is_terminal_invalid_input() -> None:
    with pytest.raises(SolverExecutionError) as raised:
        _gateway().solve(_request(attraction_ids=["attr_missing"]))

    assert raised.value.code == "invalid_solver_input"
    assert raised.value.retryable is False


def test_mutated_input_snapshot_is_rejected_by_hash_integrity_check() -> None:
    request = _request()
    request.input_snapshot["city_id"] = "shanghai"

    with pytest.raises(SolverExecutionError) as raised:
        _gateway().solve(request)

    assert raised.value.code == "invalid_solver_input"
    assert raised.value.retryable is False
