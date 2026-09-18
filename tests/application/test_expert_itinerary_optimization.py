"""Ten-place expert review regression. Traceability: H2, H3, H7, ADR-0028."""

from datetime import timedelta
from typing import Any, cast

from travel_agent.infrastructure.solver.gateway import (
    InMemoryPublishedSolverDataProvider,
    ProductionSolverGateway,
    PublishedAttraction,
    PublishedSolverData,
)
from travel_agent.solver import (
    Attraction,
    DailyWeather,
    FixedSession,
    InMemoryTravelTimeProvider,
    ODBasis,
    ODTravelMode,
    TimeRule,
    TravelTimeResult,
    WeatherBasis,
    WeatherSeverity,
)

from .test_solver_gateway import NOW, TODAY, VERSION, FixedClock, _request


def _ten_place_gateway() -> ProductionSolverGateway:
    definitions = (
        (1, "灵隐寺", 150, 4),
        (2, "飞来峰景区", 200, 4),
        (3, "西溪国家湿地公园", 200, 3),
        (4, "断桥残雪", 70, 2),
        (5, "浙江省博物馆孤山馆区", 120, 2),
        (6, "平湖秋月", 40, 1),
        (7, "清河坊历史文化特色街区", 120, 2),
        (8, "钱江新城灯光秀", 30, 1),
        (9, "武林夜市", 80, 2),
        (10, "杭州运河游船", 60, 2),
    )
    attractions = []
    for place_id, name, duration, energy in definitions:
        sessions: tuple[FixedSession, ...] = ()
        rules: tuple[TimeRule, ...] = ()
        always_open = True
        if place_id == 8:
            sessions = (
                FixedSession(
                    "light-show",
                    18 * 60 + 30,
                    19 * 60,
                    last_entry_min=18 * 60 + 40,
                ),
            )
            always_open = False
        elif place_id == 9:
            rules = (TimeRule.from_strings(("01-01", "12-31"), "18:00", "23:00"),)
            always_open = False
        elif place_id == 10:
            sessions = (FixedSession("canal-evening", 19 * 60 + 30, 20 * 60 + 30),)
            always_open = False
        attractions.append(
            PublishedAttraction(
                f"attr_{place_id}",
                Attraction(
                    place_id,
                    name,
                    suggested_duration=duration,
                    time_rules=rules,
                    is_always_open=always_open,
                    energy_level=energy,
                    data_verified=True,
                    fixed_sessions=sessions,
                ),
            )
        )

    close_costs = {
        frozenset({1, 2}): 5,
        frozenset({4, 5}): 6,
        frozenset({4, 6}): 4,
        frozenset({5, 6}): 5,
        frozenset({8, 9}): 12,
        frozenset({9, 10}): 10,
    }
    results = {}
    for origin_id, *_ in definitions:
        for destination_id, *_ in definitions:
            if origin_id == destination_id:
                continue
            pair = frozenset({origin_id, destination_id})
            travel_min = close_costs.get(pair, 38 if 3 in pair else 24)
            results[(origin_id, destination_id)] = TravelTimeResult(
                origin_id,
                destination_id,
                travel_min,
                ODBasis.GAODE,
                "hangzhou-ten-place-reviewed-od-v1",
                NOW,
                ODTravelMode.WALKING if travel_min <= 12 else ODTravelMode.DRIVING,
                travel_min * 250,
            )
    weather = {
        TODAY + timedelta(days=offset): DailyWeather(
            TODAY + timedelta(days=offset),
            WeatherBasis.FORECAST,
            WeatherSeverity.NORMAL,
            "sunny",
        )
        for offset in range(3)
    }
    snapshot = PublishedSolverData(
        VERSION,
        "hangzhou",
        tuple(attractions),
        weather,
        InMemoryTravelTimeProvider(results),
        "gaode",
        "forecast",
    )
    return ProductionSolverGateway(
        InMemoryPublishedSolverDataProvider((snapshot,)),
        FixedClock(),
    )


def test_ten_place_three_day_review_keeps_neighbours_and_bounds_search() -> None:
    result = _ten_place_gateway().solve(
        _request(
            attraction_ids=[f"attr_{place_id}" for place_id in range(1, 11)],
            end_date=TODAY + timedelta(days=2),
        )
    )
    snapshot = cast(dict[str, Any], result.result_snapshot)
    days = cast(list[dict[str, Any]], snapshot["days"])
    day_by_place = {node["attraction_id"]: day["date"] for day in days for node in day["nodes"]}
    review = cast(dict[str, Any], snapshot["itinerary_review"])
    optimization = cast(dict[str, Any], snapshot["quality_optimization"])

    assert result.quality_gate_passed
    assert snapshot["accounting"]["conserved"] is True
    assert snapshot["summary"]["scheduled_count"] == 10
    assert all(day["nodes"] for day in days)
    visit_loads = [sum(node["planned_duration_min"] for node in day["nodes"]) for day in days]
    assert max(visit_loads) - min(visit_loads) <= 120
    assert day_by_place["attr_1"] == day_by_place["attr_2"]
    assert day_by_place["attr_4"] == day_by_place["attr_6"]
    assert day_by_place["attr_8"] != day_by_place["attr_10"]
    assert review["scoring_policy_version"] == "expert-itinerary-review-v1"
    assert review["severe_issue_count"] == 0
    assert optimization["route_evaluation_count"] <= 256
    assert optimization["rounds"] <= 6
