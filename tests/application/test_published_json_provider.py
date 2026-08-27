"""A6-8.1 immutable JSON published solver snapshot tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from travel_agent.infrastructure.solver import (
    JsonPublishedSolverDataProvider,
    published_snapshot_content_hash,
)
from travel_agent.solver import ODBasis, ODTravelMode

VERSION = "hangzhou-published-test-v1"


def _snapshot(
    *, status: str = "published", review_status: str = "human_verified"
) -> dict[str, Any]:
    attractions: list[dict[str, Any]] = []
    for attraction_id, name, lng in (
        (1, "湖滨公园", 120.158818),
        (2, "音乐喷泉", 120.160970),
    ):
        attractions.append(
            {
                "external_id": f"attr_{attraction_id}",
                "id": attraction_id,
                "name": name,
                "suggested_duration": 60,
                "time_rules": [],
                "is_always_open": True,
                "is_indoor": False,
                "energy_level": 1,
                "data_verified": True,
                "conflict": False,
                "coordinate": {
                    "lat": 30.25,
                    "lng": lng,
                    "gaode_poi_id": f"gaode-poi-{attraction_id}",
                    "point_kind": "area_representative",
                    "source": "gaode_web_service_v3",
                    "fetched_at": "2026-08-26T09:00:00+08:00",
                    "review_status": review_status,
                },
            }
        )
    return {
        "version": VERSION,
        "status": status,
        "city_id": "hangzhou",
        "od_version": "gaode-test-v1",
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
                "source_ref": "qweather:101210101:weather-test-v1:2026-09-01",
                "fetched_at": "2026-08-31T08:00:00+00:00",
            }
        ],
        "od_pairs": [
            {
                "origin_id": 1,
                "destination_id": 2,
                "status": "available",
                "travel_min": 6,
                "travel_mode": "walking",
                "distance_m": 386,
                "basis": "gaode",
                "data_version": "gaode-test-v1",
                "fetched_at": "2026-08-26T09:00:00+00:00",
                "fallback_reason": None,
            },
            {
                "origin_id": 2,
                "destination_id": 1,
                "status": "available",
                "travel_min": 5,
                "travel_mode": "walking",
                "distance_m": 324,
                "basis": "gaode",
                "data_version": "gaode-test-v1",
                "fetched_at": "2026-08-26T09:00:01+00:00",
                "fallback_reason": None,
            },
        ],
    }


def _write(root: Path, snapshot: dict[str, object]) -> None:
    payload = {
        "schema_version": "published-solver-data-v1",
        "content_hash": published_snapshot_content_hash(snapshot),
        "snapshot": snapshot,
    }
    (root / f"{VERSION}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_json_published_provider_loads_complete_replayable_snapshot(
    tmp_path: Path,
) -> None:
    _write(tmp_path, _snapshot())

    published = JsonPublishedSolverDataProvider(tmp_path).load(VERSION)
    route = published.travel_time_provider.get_travel_time(1, 2)

    assert published.version == VERSION
    assert published.city_id == "hangzhou"
    assert [item.external_id for item in published.attractions] == ["attr_1", "attr_2"]
    assert route is not None
    assert route.basis is ODBasis.GAODE
    assert route.travel_mode is ODTravelMode.WALKING
    assert route.distance_m == 386


def test_json_published_provider_rejects_candidate_by_default(tmp_path: Path) -> None:
    _write(
        tmp_path,
        _snapshot(
            status="candidate",
            review_status="gaode_matched_manual_review_pending",
        ),
    )

    with pytest.raises(ValueError, match="invalid published solver snapshot"):
        JsonPublishedSolverDataProvider(tmp_path).load(VERSION)

    candidate = JsonPublishedSolverDataProvider(
        tmp_path,
        allow_candidates=True,
    ).load(VERSION)

    assert candidate.version == VERSION


def test_json_published_provider_rejects_unreviewed_published_coordinate(
    tmp_path: Path,
) -> None:
    _write(tmp_path, _snapshot(review_status="gaode_matched_manual_review_pending"))

    with pytest.raises(ValueError, match="invalid published solver snapshot"):
        JsonPublishedSolverDataProvider(tmp_path).load(VERSION)


def test_json_published_provider_rejects_hash_tampering(tmp_path: Path) -> None:
    snapshot = _snapshot()
    _write(tmp_path, snapshot)
    path = tmp_path / f"{VERSION}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["snapshot"]["city_id"] = "shanghai"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid published solver snapshot"):
        JsonPublishedSolverDataProvider(tmp_path).load(VERSION)


def test_json_published_provider_rejects_incomplete_directed_od(tmp_path: Path) -> None:
    snapshot = _snapshot()
    snapshot["od_pairs"] = snapshot["od_pairs"][:1]
    _write(tmp_path, snapshot)

    with pytest.raises(ValueError, match="invalid published solver snapshot"):
        JsonPublishedSolverDataProvider(tmp_path).load(VERSION)


def test_json_published_provider_rejects_missing_coordinate_provenance(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot()
    del snapshot["attractions"][0]["coordinate"]["fetched_at"]
    _write(tmp_path, snapshot)

    with pytest.raises(ValueError, match="invalid published solver snapshot"):
        JsonPublishedSolverDataProvider(tmp_path).load(VERSION)


def test_json_published_provider_rejects_mixed_od_versions(tmp_path: Path) -> None:
    snapshot = _snapshot()
    snapshot["od_pairs"][0]["data_version"] = "gaode-other-v1"
    _write(tmp_path, snapshot)

    with pytest.raises(ValueError, match="invalid published solver snapshot"):
        JsonPublishedSolverDataProvider(tmp_path).load(VERSION)


def test_json_published_provider_rejects_unsafe_version_path(tmp_path: Path) -> None:
    with pytest.raises(LookupError, match="version is invalid"):
        JsonPublishedSolverDataProvider(tmp_path).load("../outside")


def test_json_published_provider_rejects_string_boolean(tmp_path: Path) -> None:
    snapshot = _snapshot()
    snapshot["attractions"][0]["data_verified"] = "false"
    _write(tmp_path, snapshot)

    with pytest.raises(ValueError, match="invalid published solver snapshot"):
        JsonPublishedSolverDataProvider(tmp_path).load(VERSION)


@pytest.mark.parametrize("missing_field", ["condition_code", "source_ref", "fetched_at"])
def test_json_published_provider_requires_weather_provenance(
    tmp_path: Path,
    missing_field: str,
) -> None:
    snapshot = _snapshot()
    del snapshot["weather"][0][missing_field]
    _write(tmp_path, snapshot)

    with pytest.raises(ValueError, match="invalid published solver snapshot"):
        JsonPublishedSolverDataProvider(tmp_path).load(VERSION)


def test_json_published_provider_rejects_audit_weather_for_published(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot()
    snapshot["weather_basis"] = "audit_normal_fixture"
    _write(tmp_path, snapshot)

    with pytest.raises(ValueError, match="invalid published solver snapshot"):
        JsonPublishedSolverDataProvider(tmp_path).load(VERSION)


def test_json_candidate_provider_keeps_audit_weather_compatibility(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot(
        status="candidate",
        review_status="gaode_matched_manual_review_pending",
    )
    snapshot["weather_basis"] = "audit_normal_fixture"
    snapshot["weather"] = [
        {
            "date": "2026-09-01",
            "basis": "climate",
            "severity": "normal",
            "condition": "audit-normal-fixture-not-live-weather",
        }
    ]
    _write(tmp_path, snapshot)

    loaded = JsonPublishedSolverDataProvider(
        tmp_path,
        allow_candidates=True,
    ).load(VERSION)

    assert loaded.weather_basis == "audit_normal_fixture"
