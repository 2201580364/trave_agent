"""Combine reviewed attractions, strict Gaode OD and real weather for publication."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from travel_agent.infrastructure.solver import (  # noqa: E402
    published_snapshot_content_hash,
)
from travel_agent.infrastructure.weather import (  # noqa: E402
    qweather_snapshot_content_hash,
)
from travel_agent.solver import WeatherBasis, WeatherSeverity  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build an immutable production published solver snapshot.",
    )
    parser.add_argument("--attractions", type=Path, required=True)
    parser.add_argument("--coordinates", type=Path, required=True)
    parser.add_argument("--od", type=Path, required=True)
    parser.add_argument("--weather", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--city-id", default="hangzhou")
    args = parser.parse_args()

    snapshot = build_published_snapshot(
        _read_json(args.attractions),
        _read_json(args.coordinates),
        _read_json(args.od),
        _read_json(args.weather),
        version=args.version,
        city_id=args.city_id,
    )
    payload = {
        "schema_version": "published-solver-data-v1",
        "content_hash": published_snapshot_content_hash(snapshot),
        "snapshot": snapshot,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(payload, output, ensure_ascii=False, indent=2)
            output.write("\n")
    except FileExistsError as exc:
        raise FileExistsError(
            f"published snapshot already exists and is immutable: {args.output}"
        ) from exc

    print(f"Published solver snapshot: {args.version}")
    print(f"City: {args.city_id}")
    print(f"Attractions: {len(_list(snapshot['attractions']))}")
    print(f"OD pairs: {len(_list(snapshot['od_pairs']))}")
    print(f"Weather days: {len(_list(snapshot['weather']))}")
    print(f"Report: {args.output}")
    return 0


def build_published_snapshot(
    attractions_payload: dict[str, object],
    coordinates_payload: dict[str, object],
    od_payload: dict[str, object],
    weather_payload: dict[str, object],
    *,
    version: str,
    city_id: str,
) -> dict[str, object]:
    if not version.strip() or not city_id.strip():
        raise ValueError("published snapshot version and city_id are required")
    attraction_rows = _records(attractions_payload)
    coordinate_rows = {
        _integer(row["id"]): row for row in _records(coordinates_payload)
    }
    attraction_ids = {_integer(row["id"]) for row in attraction_rows}
    if set(coordinate_rows) != attraction_ids:
        raise ValueError("reviewed coordinate and attraction ids must match")
    coordinate_fetched_at = _text(coordinates_payload.get("generated_on"))

    attractions: list[dict[str, object]] = []
    for row in attraction_rows:
        attraction_id = _integer(row["id"])
        if (
            row.get("data_verified") is not True
            or row.get("conflict", False) is True
            or row.get("active", True) is not True
        ):
            raise ValueError("all attractions must pass the publication data gate")
        coordinate = coordinate_rows[attraction_id]
        if coordinate.get("coordinate_review_status") != "human_verified":
            raise ValueError("all published coordinates must be human_verified")
        attractions.append(
            {
                "external_id": f"attr_{attraction_id}",
                "id": attraction_id,
                "name": row["name"],
                "close_days": row.get("close_days", []),
                "open_on_dates": row.get("open_on_dates", []),
                "closed_on_dates": row.get("closed_on_dates", []),
                "suggested_duration": row["suggested_duration"],
                "time_rules": row.get("time_rules", []),
                "is_always_open": row["is_always_open"],
                "is_indoor": row["is_indoor"],
                "energy_level": row["energy_level"],
                "data_verified": row["data_verified"],
                "conflict": row.get("conflict", False),
                "active": row.get("active", True),
                "coordinate": {
                    "lat": coordinate["lat"],
                    "lng": coordinate["lng"],
                    "gaode_poi_id": _text(coordinate.get("gaode_poi_id")),
                    "point_kind": _text(coordinate.get("routing_point_kind")),
                    "source": "gaode_web_service_v3",
                    "fetched_at": coordinate_fetched_at,
                    "review_status": "human_verified",
                },
            }
        )

    od_pairs, od_version, od_basis = _validated_od_pairs(od_payload, attraction_ids)
    weather_days, weather_basis = _validated_weather(
        weather_payload,
        city_id=city_id,
    )
    return {
        "version": version,
        "status": "published",
        "city_id": city_id,
        "od_version": od_version,
        "od_basis": od_basis,
        "weather_basis": weather_basis,
        "attractions": attractions,
        "weather": weather_days,
        "od_pairs": od_pairs,
    }


def _validated_od_pairs(
    payload: dict[str, object],
    attraction_ids: set[int],
) -> tuple[list[object], str, str]:
    report = _mapping(payload.get("report"))
    if report.get("missing_pair_count") != 0 or report.get("fallback_pair_count") != 0:
        raise ValueError("published OD must be complete and contain no fallback")
    pairs = _list(payload.get("pairs"))
    expected = {
        (origin_id, destination_id)
        for origin_id in attraction_ids
        for destination_id in attraction_ids
        if origin_id != destination_id
    }
    actual: set[tuple[int, int]] = set()
    bases: set[str] = set()
    versions: set[str] = set()
    for raw in pairs:
        row = _mapping(raw)
        if row.get("status") != "available":
            raise ValueError("published OD cannot contain missing pairs")
        pair = (_integer(row["origin_id"]), _integer(row["destination_id"]))
        if pair in actual:
            raise ValueError("published OD pairs must be unique")
        actual.add(pair)
        bases.add(_text(row.get("basis")))
        versions.add(_text(row.get("data_version")))
        _text(row.get("travel_mode"))
        _integer(row["travel_min"])
        _integer(row["distance_m"])
        _aware_datetime(row.get("fetched_at"))
    if actual != expected:
        raise ValueError("published OD must contain every directed attraction pair")
    declared_version = _text(payload.get("data_version"))
    if versions != {declared_version}:
        raise ValueError("published OD data versions are inconsistent")
    if bases != {"gaode"}:
        raise ValueError("published OD must use strict Gaode basis")
    return pairs, declared_version, "gaode"


def _validated_weather(
    payload: dict[str, object],
    *,
    city_id: str,
) -> tuple[list[object], str]:
    if payload.get("schema_version") != "weather-snapshot-envelope-v1":
        raise ValueError("unsupported weather snapshot envelope")
    snapshot = _mapping(payload.get("snapshot"))
    expected_hash = _text(payload.get("content_hash"))
    if qweather_snapshot_content_hash(snapshot) != expected_hash:
        raise ValueError("weather snapshot content hash mismatch")
    if snapshot.get("schema_version") != "weather-snapshot-v1":
        raise ValueError("unsupported weather snapshot schema")
    if snapshot.get("city_id") != city_id:
        raise ValueError("weather snapshot city mismatch")
    if snapshot.get("provider") != "qweather":
        raise ValueError("published weather provider must be qweather")
    if snapshot.get("basis") != WeatherBasis.FORECAST.value:
        raise ValueError("QWeather three-day snapshot must use forecast basis")
    data_version = _text(snapshot.get("data_version"))
    _aware_datetime(snapshot.get("fetched_at"))
    days = _list(snapshot.get("days"))
    if len(days) != 3:
        raise ValueError("published QWeather snapshot must contain three days")
    seen_dates: set[str] = set()
    for raw in days:
        row = _mapping(raw)
        day = _text(row.get("date"))
        datetime.fromisoformat(day)
        if day in seen_dates:
            raise ValueError("published weather dates must be unique")
        seen_dates.add(day)
        WeatherBasis(_text(row.get("basis")))
        WeatherSeverity(_text(row.get("severity")))
        _text(row.get("condition"))
        _text(row.get("condition_code"))
        _text(row.get("source_ref"))
        _aware_datetime(row.get("fetched_at"))
    return days, f"qweather:{data_version}"


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON input must be an object: {path}")
    return payload


def _records(payload: dict[str, object]) -> list[dict[str, object]]:
    rows = payload.get("records")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("input must contain object records")
    return rows


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError("expected object")
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise TypeError("expected array")
    return value


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError("expected non-empty string")
    return value.strip()


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise TypeError("expected integer")
    return int(value)


def _aware_datetime(value: object) -> datetime:
    parsed = datetime.fromisoformat(_text(value))
    if parsed.tzinfo is None:
        raise ValueError("expected timezone-aware datetime")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
