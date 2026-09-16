"""User's Sep 30–Oct 2 counterexample, sourced local OD fixture; H3/ADR-0027.

Coordinates, durations and calendar/session facts captured from the reviewed
research catalog on Sep 16. No external API or mutable research DB dependency.
"""

import hashlib
import json
from datetime import UTC, date, datetime, timedelta

import pytest

from travel_agent.application.planning.ports import SolverRequest
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
    TimeRule,
    WeatherBasis,
    WeatherSeverity,
)
from travel_agent.solver.models import FixedSession


class Clock:
    def now(self):
        return datetime(2026, 9, 16, tzinfo=UTC)


def snapshot():
    specs = (
        (1, "平湖秋月", 40, 2, 30.258255, 120.152633, ()),
        (
            2,
            "浙江省博物馆孤山馆区",
            70,
            3,
            30.257361,
            120.150259,
            (TimeRule(1, 1, 12, 31, 540, 1020, 990, frozenset({2, 3, 4, 5})),),
        ),
        (
            3,
            "飞来峰景区",
            200,
            3,
            30.246768,
            120.111615,
            (TimeRule(1, 1, 12, 31, 450, 1050, 1020),),
        ),
        (
            4,
            "西溪国家湿地公园",
            200,
            4,
            30.272668,
            120.052628,
            (TimeRule(1, 1, 12, 31, 480, 1080, 1020),),
        ),
        (
            5,
            "清河坊历史文化特色街区",
            120,
            2,
            30.243454,
            120.177818,
            (TimeRule(1, 1, 12, 31, 540, 1290),),
        ),
        (6, "杭州运河游船", 110, 1, 30.279941, 120.171423, ()),
        (
            7,
            "武林夜市",
            80,
            3,
            30.267641,
            120.167273,
            (
                TimeRule(1, 1, 12, 31, 1020, 1380, weekdays=frozenset({1, 2, 3, 4, 5})),
                TimeRule(1, 1, 12, 31, 1020, 1410, weekdays=frozenset({6, 7})),
            ),
        ),
        (8, "钱江新城灯光秀", 30, 2, 30.249677, 120.221185, ()),
        (12, "断桥残雪", 70, 2, 30.264614, 120.158261, ()),
        (13, "灵隐寺", 150, 2, 30.246861, 120.111776, (TimeRule(1, 1, 12, 31, 450, 1080, 1050),)),
    )
    sessions = {
        6: (
            FixedSession("boat-1830", 1110, 1170, 1110),
            FixedSession("boat-1930", 1170, 1230, 1170),
            FixedSession("boat-2020", 1220, 1290, 1220, weekdays=frozenset({1, 2, 3, 4, 5})),
        ),
        8: (
            FixedSession(
                "show-summer",
                1230,
                1260,
                1240,
                valid_from=date(2026, 4, 15),
                valid_to=date(2026, 9, 30),
            ),
            FixedSession(
                "show-winter",
                1170,
                1200,
                1180,
                valid_from=date(2026, 10, 1),
                valid_to=date(2027, 4, 14),
            ),
            FixedSession(
                "show-weekend",
                1110,
                1140,
                1120,
                weekdays=frozenset({5, 6}),
                valid_from=date(2026, 10, 1),
                valid_to=date(2027, 4, 14),
            ),
        ),
    }
    attractions = tuple(
        PublishedAttraction(
            str(i),
            Attraction(
                i,
                name,
                suggested_duration=duration,
                energy_level=energy,
                data_verified=True,
                time_rules=rules,
                is_always_open=i in {1, 12},
                fixed_sessions=sessions.get(i, ()),
                close_days=frozenset({1}) if i == 2 else frozenset(),
            ),
            Coordinate(lat, lng),
        )
        for i, name, duration, energy, lat, lng, rules in specs
    )
    weather = {
        date(2026, 9, 28) + timedelta(days=i): DailyWeather(
            date(2026, 9, 28) + timedelta(days=i), WeatherBasis.FORECAST, WeatherSeverity.NORMAL
        )
        for i in range(8)
    }
    return PublishedSolverData(
        "ten-place-fixture",
        "hangzhou",
        attractions,
        weather,
        ApproximateTravelTimeProvider(
            {a.attraction.id: a.coordinate for a in attractions},
            speed_kmh=18,
            detour_ratio=1.6,
            minimum_travel_min=5,
            data_version="local-approximate",
            fetched_at=Clock().now(),
        ),
        "approximate",
        "deterministic_fixture",
    )


def solve(catalog, start=date(2026, 9, 30)):
    end = start + timedelta(days=2)
    payload = {
        "schema_version": "generation-input-v1",
        "city_id": "hangzhou",
        "data_snapshot_version": catalog.version,
        "selected_attraction_ids": [a.external_id for a in catalog.attractions],
        "visit_period_preferences": [],
        "travel_facts": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "arrival_at": f"{start}T09:00:00+08:00",
            "departure_at": f"{end}T18:00:00+08:00",
            "station_to_city_min": 0,
            "station_early_min": 0,
            "last_visit_to_station_min": 0,
            "travel_mode": "normal",
        },
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    return ProductionSolverGateway(InMemoryPublishedSolverDataProvider((catalog,)), Clock()).solve(
        SolverRequest("ten-place-run", "ten-place-intent", payload, digest, catalog.version, 1)
    )


def test_ten_places_have_full_visits_meals_balanced_load_and_real_sessions():
    catalog = snapshot()
    first, second = solve(catalog), solve(catalog)
    assert first.result_snapshot_hash == second.result_snapshot_hash
    result = first.result_snapshot
    assert first.quality_gate_passed
    assert result["summary"]["scheduled_count"] == 10
    assert result["unplaced"] == []
    assert result["accounting"]["conserved"]
    by_id = {a.external_id: a.attraction for a in catalog.attractions}
    days_by_id = {n["attraction_id"]: d["date"] for d in result["days"] for n in d["nodes"]}
    assert days_by_id["3"] == days_by_id["13"]
    assert days_by_id["1"] == days_by_id["12"] == days_by_id["2"]
    loads = []
    for day in result["days"]:
        assert len(day["nodes"]) >= 2
        assert day["lunch"]["duration_min"] == 60
        assert day["meal"]["duration_min"] == 90
        for node in day["nodes"]:
            a = by_id[node["attraction_id"]]
            if a.fixed_sessions:
                assert any(
                    s.matches(date.fromisoformat(day["date"]))
                    and s.entry_min == node["arrival_min"]
                    and s.end_min == node["leave_min"]
                    for s in a.fixed_sessions
                )
            else:
                assert node["planned_duration_min"] == a.suggested_duration
            if day is result["days"][-1]:
                assert node["leave_min"] <= 1080
        for a, b in zip(day["nodes"], day["nodes"][1:], strict=False):
            assert b["arrival_min"] >= a["leave_min"] + b["buffered_travel_from_previous_min"]
            if a["arrival_min"] >= 1020:
                assert (
                    b["arrival_min"] - a["leave_min"] - b["buffered_travel_from_previous_min"] >= 15
                )
        loads.append(
            sum(
                n["planned_duration_min"] + n["buffered_travel_from_previous_min"]
                for n in day["nodes"]
            )
        )
    assert max(loads) / min(loads) < 1.6
    lake_day = next(d for d in result["days"] if d["date"] == days_by_id["1"])
    assert next(n for n in lake_day["nodes"] if n["attraction_id"] == "1")["arrival_min"] >= 780


@pytest.mark.parametrize("start", [date(2026, 9, 28), date(2026, 9, 29)])
def test_quality_rebalance_still_checks_closed_days_and_return_time(start):
    result = solve(snapshot(), start).result_snapshot
    assert result["quality_gate_passed"]
    assert result["accounting"]["conserved"]
    for day in result["days"]:
        for node in day["nodes"]:
            if node["attraction_id"] == "2":
                assert date.fromisoformat(day["date"]).isoweekday() != 1
    assert all(n["leave_min"] <= 1080 for n in result["days"][-1]["nodes"])
