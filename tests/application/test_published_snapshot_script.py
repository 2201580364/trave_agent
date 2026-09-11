"""Published snapshot builder tests for reviewed coordinates and real weather."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

import pytest

from scripts.build_published_solver_snapshot import build_published_snapshot
from travel_agent.infrastructure.weather import qweather_snapshot_content_hash


def _attractions() -> dict[str, Any]:
    return {
        "records": [
            {
                "id": attraction_id,
                "name": name,
                "suggested_duration": 60,
                "time_rules": [],
                "is_always_open": True,
                "is_indoor": False,
                "energy_level": 1,
                "data_verified": True,
                "conflict": False,
                "active": True,
            }
            for attraction_id, name in ((1, "湖滨公园"), (2, "音乐喷泉"))
        ]
    }


def _coordinates(*, review_status: str = "human_verified") -> dict[str, Any]:
    return {
        "generated_on": "2026-08-27",
        "records": [
            {
                "id": attraction_id,
                "lat": 30.25,
                "lng": lng,
                "gaode_poi_id": f"poi-{attraction_id}",
                "routing_point_kind": "area_representative",
                "coordinate_review_status": review_status,
            }
            for attraction_id, lng in ((1, 120.158818), (2, 120.160970))
        ],
    }


def _od() -> dict[str, Any]:
    version = "gaode-published-test-v1"
    return {
        "data_version": version,
        "report": {"missing_pair_count": 0, "fallback_pair_count": 0},
        "pairs": [
            {
                "origin_id": origin,
                "destination_id": destination,
                "status": "available",
                "travel_min": minutes,
                "travel_mode": "walking",
                "distance_m": distance,
                "basis": "gaode",
                "data_version": version,
                "fetched_at": "2026-08-27T08:00:00+00:00",
                "fallback_reason": None,
            }
            for origin, destination, minutes, distance in (
                (1, 2, 4, 262),
                (2, 1, 6, 386),
            )
        ],
    }


def _weather() -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "schema_version": "weather-snapshot-v1",
        "city_id": "hangzhou",
        "location_id": "101210101",
        "data_version": "qweather-published-test-v1",
        "basis": "forecast",
        "provider": "qweather",
        "provider_update_time": "2026-08-27T14:35+08:00",
        "fetched_at": "2026-08-27T08:00:00+00:00",
        "days": [
            {
                "date": f"2026-08-{day}",
                "basis": "forecast",
                "severity": "normal",
                "condition": "晴",
                "condition_code": "100",
                "source_ref": (f"qweather:101210101:qweather-published-test-v1:2026-08-{day}"),
                "fetched_at": "2026-08-27T08:00:00+00:00",
            }
            for day in (27, 28, 29)
        ],
    }
    return {
        "schema_version": "weather-snapshot-envelope-v1",
        "content_hash": qweather_snapshot_content_hash(snapshot),
        "snapshot": snapshot,
    }


def test_build_published_snapshot_combines_strict_inputs() -> None:
    snapshot = build_published_snapshot(
        _attractions(),
        _coordinates(),
        _od(),
        _weather(),
        version="hangzhou-published-test-v1",
        city_id="hangzhou",
    )

    assert snapshot["status"] == "published"
    assert snapshot["weather_basis"] == "qweather:qweather-published-test-v1"
    attractions = cast(list[dict[str, Any]], snapshot["attractions"])
    weather = cast(list[dict[str, Any]], snapshot["weather"])
    od_pairs = cast(list[dict[str, Any]], snapshot["od_pairs"])
    assert len(attractions) == 2
    assert len(weather) == 3
    assert len(od_pairs) == 2
    assert attractions[0]["coordinate"]["review_status"] == ("human_verified")


def test_build_published_snapshot_rejects_unreviewed_coordinates() -> None:
    with pytest.raises(ValueError, match="human_verified"):
        build_published_snapshot(
            _attractions(),
            _coordinates(review_status="gaode_matched_manual_review_pending"),
            _od(),
            _weather(),
            version="hangzhou-published-test-v1",
            city_id="hangzhou",
        )


def test_build_published_snapshot_rejects_weather_hash_tampering() -> None:
    weather = _weather()
    weather["snapshot"]["days"][0]["condition"] = "台风"

    with pytest.raises(ValueError, match="content hash mismatch"):
        build_published_snapshot(
            _attractions(),
            _coordinates(),
            _od(),
            weather,
            version="hangzhou-published-test-v1",
            city_id="hangzhou",
        )


def test_build_published_snapshot_rejects_incomplete_od() -> None:
    od = deepcopy(_od())
    od["pairs"] = od["pairs"][:1]

    with pytest.raises(ValueError, match="every directed attraction pair"):
        build_published_snapshot(
            _attractions(),
            _coordinates(),
            od,
            _weather(),
            version="hangzhou-published-test-v1",
            city_id="hangzhou",
        )


def test_snapshot_preserves_discrete_session_payload():
    """H3/C2: the production builder cannot drop new multi-session facts."""
    from travel_agent.infrastructure.solver.published_json import _parse_attraction

    attractions = _attractions()
    sessions = [
        {
            "session_id": "evening",
            "source_record_id": "reviewed-source",
            "start_min": 1080,
            "end_min": 1140,
            "last_entry_min": 1070,
        }
    ]
    attractions["records"][1]["fixed_sessions"] = sessions
    snapshot = build_published_snapshot(
        attractions, _coordinates(), _od(), _weather(), version="sessions-v1", city_id="hangzhou"
    )
    rows = cast(list[dict[str, object]], snapshot["attractions"])
    assert rows[1]["fixed_sessions"] == sessions
    attraction = _parse_attraction(rows[1], require_human_review=True).attraction
    assert attraction.fixed_sessions[0].entry_min == 1070


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [{}],
        [{"source_record_id": "s", "session_id": "x", "start_min": 1}],
        [
            {
                "source_record_id": "s",
                "session_id": "x",
                "start_min": 1,
                "end_min": 2,
                "opening_hours": [None],
            }
        ],
    ],
)
def test_malformed_session_payload_fails_closed(payload):
    """H3/C2: malformed published facts produce validation errors."""
    from travel_agent.infrastructure.solver.fixed_sessions import parse_fixed_sessions

    with pytest.raises(ValueError):
        parse_fixed_sessions(payload)
