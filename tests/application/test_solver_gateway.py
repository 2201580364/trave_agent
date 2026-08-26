"""A6-4 production SolverGateway integration tests."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta

import pytest

from travel_agent.application.planning.ports import SolverExecutionError, SolverRequest
from travel_agent.domain.planning import CompletionKind
from travel_agent.infrastructure.solver import (
    InMemoryPublishedSolverDataProvider,
    ProductionSolverGateway,
    PublishedAttraction,
    PublishedSolverData,
)
from travel_agent.solver import (
    ApproximateTravelTimeProvider,
    Attraction,
    Coordinate,
    DailyWeather,
    InMemoryTravelTimeProvider,
    ODBasis,
    ODTravelMode,
    TravelTimeResult,
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


def _request(
    *,
    attraction_ids: list[str] | None = None,
    end_date: date = TODAY,
) -> SolverRequest:
    snapshot = {
        "schema_version": "generation-input-v1",
        "city_id": "hangzhou",
        "travel_facts": {
            "start_date": TODAY.isoformat(),
            "end_date": end_date.isoformat(),
            "arrival_at": "2026-09-01T09:00:00+08:00",
            "departure_at": f"{end_date.isoformat()}T21:00:00+08:00",
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


def _gateway_with_od(
    *,
    basis: ODBasis,
    travel_mode: ODTravelMode | None,
    distance_m: int,
    fallback_reason: str | None = None,
) -> ProductionSolverGateway:
    published = _published()
    results = {
        (origin_id, destination_id): TravelTimeResult(
            origin_id=origin_id,
            destination_id=destination_id,
            travel_min=12,
            basis=basis,
            data_version=VERSION,
            fetched_at=NOW,
            travel_mode=travel_mode,
            distance_m=distance_m,
            fallback_reason=fallback_reason,
        )
        for origin_id, destination_id in ((1, 2), (2, 1))
    }
    snapshot = PublishedSolverData(
        published.version,
        published.city_id,
        published.attractions,
        published.weather_by_date,
        InMemoryTravelTimeProvider(results),
        basis.value,
        published.weather_basis,
    )
    return ProductionSolverGateway(
        InMemoryPublishedSolverDataProvider((snapshot,)),
        FixedClock(),
    )


def _balanced_gateway() -> ProductionSolverGateway:
    attractions = tuple(
        PublishedAttraction(
            f"attr_{attraction_id}",
            Attraction(
                attraction_id,
                f"景点 {attraction_id}",
                suggested_duration=90,
                is_always_open=True,
                energy_level=1 + attraction_id % 3,
                data_verified=True,
            ),
            Coordinate(30.25 + attraction_id / 10_000, 120.16),
        )
        for attraction_id in range(1, 8)
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
        visit_date: DailyWeather(
            visit_date,
            WeatherBasis.FORECAST,
            WeatherSeverity.NORMAL,
            "sunny",
        )
        for visit_date in (TODAY + timedelta(days=offset) for offset in range(3))
    }
    snapshot = PublishedSolverData(
        VERSION,
        "hangzhou",
        attractions,
        weather,
        provider,
        "approximate",
        "forecast",
    )
    return ProductionSolverGateway(
        InMemoryPublishedSolverDataProvider((snapshot,)),
        FixedClock(),
    )


def test_gateway_runs_versioned_solver_and_maps_stable_result() -> None:
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
    connected_node = next(
        item for item in nodes if item["travel_from_previous_min"] > 0
    )
    assert connected_node["transport_mode"] == "walking_estimate"
    assert connected_node["travel_basis"] == "approximate"
    assert connected_node["travel_distance_m"] > 0
    assert connected_node["travel_fallback_reason"] is None
    assert first.result_snapshot["days"][0]["lunch"]["status"] == "full"
    assert first.audit_payload["solve_run_id"] == "solver_run_1"
    assert first.audit_payload["data_snapshot_version"] == VERSION


def test_gateway_maps_gaode_mode_and_road_distance_into_v2_result() -> None:
    outcome = _gateway_with_od(
        basis=ODBasis.GAODE,
        travel_mode=ODTravelMode.TRANSIT,
        distance_m=8_200,
    ).solve(_request())

    connected_node = next(
        node
        for node in outcome.result_snapshot["days"][0]["nodes"]
        if node["travel_from_previous_min"] > 0
    )

    assert outcome.result_schema_version == "trip-result-v2"
    assert outcome.result_snapshot["schema_version"] == "trip-result-v2"
    assert connected_node["transport_mode"] == "transit"
    assert connected_node["travel_basis"] == "gaode"
    assert connected_node["travel_distance_m"] == 8_200
    assert connected_node["travel_fallback_reason"] is None


def test_gateway_exposes_approximate_fallback_reason_without_claiming_gaode() -> None:
    outcome = _gateway_with_od(
        basis=ODBasis.APPROXIMATE,
        travel_mode=None,
        distance_m=3_400,
        fallback_reason="gaode_timeout",
    ).solve(_request())

    connected_node = next(
        node
        for node in outcome.result_snapshot["days"][0]["nodes"]
        if node["travel_from_previous_min"] > 0
    )

    assert connected_node["travel_basis"] == "approximate"
    assert connected_node["travel_fallback_reason"] == "gaode_timeout"
    assert connected_node["transport_mode"] == "taxi_estimate"


def test_gateway_derives_stable_balanced_dates_when_user_has_no_date_preference() -> None:
    attraction_ids = [f"attr_{attraction_id}" for attraction_id in range(1, 8)]
    request = _request(
        attraction_ids=attraction_ids,
        end_date=TODAY + timedelta(days=2),
    )

    first = _balanced_gateway().solve(request)
    second = _balanced_gateway().solve(request)

    first_counts = [len(day["nodes"]) for day in first.result_snapshot["days"]]
    second_counts = [len(day["nodes"]) for day in second.result_snapshot["days"]]
    scheduled_ids = {
        node["attraction_id"]
        for day in first.result_snapshot["days"]
        for node in day["nodes"]
    }

    assert first_counts == second_counts
    assert all(count > 0 for count in first_counts)
    assert max(first_counts) - min(first_counts) <= 1
    assert scheduled_ids == set(attraction_ids)
    assert first.result_snapshot["accounting"]["conserved"] is True
    assert first.result_snapshot_hash == second.result_snapshot_hash


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
