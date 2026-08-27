"""Immutable JSON adapter for versioned published solver snapshots."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path

from travel_agent.solver import (
    Attraction,
    Coordinate,
    DailyWeather,
    InMemoryTravelTimeProvider,
    ODBasis,
    ODTravelMode,
    TimeRule,
    TravelTimeResult,
    WeatherBasis,
    WeatherSeverity,
)

from .gateway import PublishedAttraction, PublishedSolverData

_SAFE_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class JsonPublishedSolverDataProvider:
    """Load replayable solver data without contacting external providers."""

    def __init__(self, root: Path, *, allow_candidates: bool = False) -> None:
        self._root = root
        self._allow_candidates = allow_candidates
        self._cache: dict[str, PublishedSolverData] = {}

    def load(self, version: str) -> PublishedSolverData:
        if _SAFE_VERSION.fullmatch(version) is None:
            raise LookupError("published solver snapshot version is invalid")
        cached = self._cache.get(version)
        if cached is not None:
            return cached
        path = self._root / f"{version}.json"
        if not path.is_file():
            raise LookupError(f"published solver snapshot not found: {version}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            snapshot = _mapping(payload["snapshot"])
            if payload.get("schema_version") != "published-solver-data-v1":
                raise ValueError("unsupported published solver snapshot schema")
            if snapshot.get("version") != version:
                raise ValueError("published solver snapshot version mismatch")
            _verify_content_hash(snapshot, payload.get("content_hash"))
            status = snapshot.get("status")
            if status != "published" and not (
                self._allow_candidates and status == "candidate"
            ):
                raise ValueError("published solver snapshot is not published")
            loaded = _parse_snapshot(snapshot, require_human_review=status == "published")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid published solver snapshot: {version}") from exc
        self._cache[version] = loaded
        return loaded


def published_snapshot_content_hash(snapshot: dict[str, object]) -> str:
    serialized = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _verify_content_hash(snapshot: dict[str, object], expected: object) -> None:
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError("published solver snapshot content hash is required")
    if published_snapshot_content_hash(snapshot) != expected:
        raise ValueError("published solver snapshot content hash mismatch")


def _parse_snapshot(
    snapshot: dict[str, object], *, require_human_review: bool
) -> PublishedSolverData:
    version = _text(snapshot["version"])
    city_id = _text(snapshot["city_id"])
    attractions = tuple(
        _parse_attraction(_mapping(row), require_human_review=require_human_review)
        for row in _list(snapshot["attractions"])
    )
    if len(attractions) < 2:
        raise ValueError("published solver snapshot requires at least two attractions")
    attraction_ids = [item.attraction.id for item in attractions]
    external_ids = [item.external_id for item in attractions]
    if len(set(attraction_ids)) != len(attraction_ids):
        raise ValueError("published solver snapshot attraction ids must be unique")
    if len(set(external_ids)) != len(external_ids):
        raise ValueError("published solver snapshot external ids must be unique")
    weather_basis = _text(snapshot["weather_basis"])
    if require_human_review and (
        "audit" in weather_basis.lower() or "fixture" in weather_basis.lower()
    ):
        raise ValueError("published solver snapshot cannot use audit weather")
    weather = tuple(
        _parse_weather(
            _mapping(row),
            require_provenance=require_human_review,
        )
        for row in _list(snapshot["weather"])
    )
    if not weather:
        raise ValueError("published solver snapshot requires weather data")
    weather_by_date = {item.day: item for item in weather}
    if len(weather_by_date) != len(weather):
        raise ValueError("published solver snapshot weather dates must be unique")
    od_results = tuple(
        _parse_od(_mapping(row)) for row in _list(snapshot["od_pairs"])
    )
    attraction_id_set = set(attraction_ids)
    expected_pairs = {
        (origin_id, destination_id)
        for origin_id in attraction_id_set
        for destination_id in attraction_id_set
        if origin_id != destination_id
    }
    actual_pairs = {(item.origin_id, item.destination_id) for item in od_results}
    if actual_pairs != expected_pairs or len(actual_pairs) != len(od_results):
        raise ValueError("published solver snapshot must contain every directed OD pair once")
    od_basis = _text(snapshot["od_basis"])
    if {item.basis.value for item in od_results} != {od_basis}:
        raise ValueError("published solver snapshot OD basis mismatch")
    od_version = _text(snapshot["od_version"])
    if {item.data_version for item in od_results} != {od_version}:
        raise ValueError("published solver snapshot OD version mismatch")
    fetched_at = max(item.fetched_at for item in od_results)
    return PublishedSolverData(
        version,
        city_id,
        attractions,
        weather_by_date,
        InMemoryTravelTimeProvider(
            {(item.origin_id, item.destination_id): item for item in od_results},
            default_basis=ODBasis(od_basis),
            data_version=od_version,
            fetched_at=fetched_at,
        ),
        od_basis,
        weather_basis,
    )


def _parse_attraction(
    row: dict[str, object], *, require_human_review: bool
) -> PublishedAttraction:
    coordinate_row = _mapping(row["coordinate"])
    review_status = _text(coordinate_row["review_status"])
    if require_human_review and review_status != "human_verified":
        raise ValueError("published routing coordinates must be human verified")
    _text(coordinate_row["gaode_poi_id"])
    _text(coordinate_row["point_kind"])
    _text(coordinate_row["source"])
    _iso_date_or_datetime(coordinate_row["fetched_at"])
    rules = tuple(
        TimeRule.from_strings(
            _date_range(rule["date_range"]),
            _text(rule["open"]),
            _text(rule["close"]),
            _optional_text(rule.get("last_entry")),
        )
        for raw in _list(row.get("time_rules", []))
        for rule in (_mapping(raw),)
    )
    attraction = Attraction(
        _integer(row["id"]),
        _text(row["name"]),
        close_days=frozenset(
            _integer(item) for item in _list(row.get("close_days", []))
        ),
        open_on_dates=frozenset(
            date.fromisoformat(_text(item))
            for item in _list(row.get("open_on_dates", []))
        ),
        closed_on_dates=frozenset(
            date.fromisoformat(_text(item))
            for item in _list(row.get("closed_on_dates", []))
        ),
        suggested_duration=_integer(row["suggested_duration"]),
        time_rules=rules,
        is_always_open=_boolean(row["is_always_open"]),
        is_indoor=_boolean(row["is_indoor"]),
        energy_level=_integer(row["energy_level"]),
        data_verified=_boolean(row["data_verified"]),
        conflict=_boolean(row.get("conflict", False)),
        active=_boolean(row.get("active", True)),
    )
    return PublishedAttraction(
        _text(row["external_id"]),
        attraction,
        Coordinate(_number(coordinate_row["lat"]), _number(coordinate_row["lng"])),
    )


def _parse_weather(
    row: dict[str, object],
    *,
    require_provenance: bool,
) -> DailyWeather:
    condition = _optional_text(row.get("condition"))
    if require_provenance:
        condition = _text(row.get("condition"))
        _text(row.get("condition_code"))
        _text(row.get("source_ref"))
        _iso_aware_datetime(row.get("fetched_at"))
    return DailyWeather(
        date.fromisoformat(_text(row["date"])),
        WeatherBasis(_text(row["basis"])),
        WeatherSeverity(_text(row["severity"])),
        condition,
    )


def _parse_od(row: dict[str, object]) -> TravelTimeResult:
    if row.get("status", "available") != "available":
        raise ValueError("published solver snapshot cannot contain missing OD pairs")
    return TravelTimeResult(
        _integer(row["origin_id"]),
        _integer(row["destination_id"]),
        _integer(row["travel_min"]),
        ODBasis(_text(row["basis"])),
        _text(row["data_version"]),
        datetime.fromisoformat(_text(row["fetched_at"])),
        ODTravelMode(_text(row["travel_mode"])),
        _integer(row["distance_m"]),
        _optional_text(row.get("fallback_reason")),
    )


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError("expected object")
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise TypeError("expected array")
    return value


def _text(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError("expected non-empty string")
    return value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return _text(value)


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise TypeError("expected integer")
    return int(value)


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise TypeError("expected number")
    return float(value)


def _boolean(value: object) -> bool:
    if not isinstance(value, bool):
        raise TypeError("expected boolean")
    return value


def _date_range(value: object) -> tuple[str, str]:
    items = _list(value)
    if len(items) != 2:
        raise ValueError("time rule date_range must contain exactly two dates")
    return (_text(items[0]), _text(items[1]))


def _iso_date_or_datetime(value: object) -> str:
    parsed = _text(value)
    try:
        datetime.fromisoformat(parsed)
    except ValueError:
        date.fromisoformat(parsed)
    return parsed


def _iso_aware_datetime(value: object) -> str:
    parsed = _text(value)
    timestamp = datetime.fromisoformat(parsed)
    if timestamp.tzinfo is None:
        raise ValueError("expected timezone-aware datetime")
    return parsed
