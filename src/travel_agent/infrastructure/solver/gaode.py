"""Gaode route acquisition and deterministic OD snapshot construction.

Network I/O happens only while a published OD snapshot is built.  The solver
receives an ``InMemoryTravelTimeProvider`` and never calls Gaode during OR-Tools
search.  This keeps route replay deterministic and bounds external API usage.

Traceability: C6, ADR-0010, A6-8.1.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import StrEnum
from os import PathLike
from pathlib import Path
from typing import Protocol

import httpx

from travel_agent.runtime_config import load_runtime_environment
from travel_agent.solver import (
    Coordinate,
    InMemoryTravelTimeProvider,
    ODBasis,
    ODTravelMode,
    TravelTimeProvider,
    TravelTimeResult,
)

GAODE_RATE_LIMIT_CODES = frozenset(
    {
        "10003",  # daily request quota exceeded
        "10004",  # IP access quota exceeded
        "10010",  # key is bound to a different service/IP
        "10019",  # API access exhausted
        "10020",  # resident QPS exceeded
        "10021",  # resident daily quota exceeded
        "10044",  # account QPS exceeded
        "10045",  # account daily quota exceeded
    }
)


class GaodeFailureCode(StrEnum):
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    HTTP_ERROR = "http_error"
    API_ERROR = "api_error"
    NO_ROUTE = "no_route"
    INVALID_RESPONSE = "invalid_response"


class GaodeRouteError(RuntimeError):
    def __init__(
        self,
        code: GaodeFailureCode,
        message: str,
        *,
        infocode: str | None = None,
        occurred_at: datetime | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.infocode = infocode
        self.occurred_at = occurred_at


@dataclass(frozen=True, slots=True)
class GaodeSettings:
    api_key: str = field(repr=False)
    city_code: str = "330100"
    timeout_seconds: float = 5.0
    cache_ttl_seconds: int = 24 * 60 * 60
    data_version: str = "gaode-route-v1"
    base_url: str = "https://restapi.amap.com"
    enabled_modes: tuple[ODTravelMode, ...] = (
        ODTravelMode.WALKING,
        ODTravelMode.TRANSIT,
        ODTravelMode.DRIVING,
    )

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("Gaode api_key is required")
        if not self.city_code.strip():
            raise ValueError("Gaode city_code is required")
        if self.timeout_seconds <= 0:
            raise ValueError("Gaode timeout_seconds must be positive")
        if self.cache_ttl_seconds <= 0:
            raise ValueError("Gaode cache_ttl_seconds must be positive")
        if not self.data_version.strip():
            raise ValueError("Gaode data_version is required")
        if not self.enabled_modes or len(set(self.enabled_modes)) != len(
            self.enabled_modes
        ):
            raise ValueError("Gaode enabled_modes must be non-empty and unique")

    @classmethod
    def from_env(
        cls,
        *,
        dotenv_path: str | PathLike[str] | None = None,
        load_dotenv_file: bool = True,
    ) -> GaodeSettings:
        if load_dotenv_file:
            load_runtime_environment(dotenv_path)
        key = os.environ.get("TRAVEL_AGENT_GAODE_API_KEY", "").strip()
        if not key:
            raise ValueError("TRAVEL_AGENT_GAODE_API_KEY is required")
        raw_modes = os.environ.get(
            "TRAVEL_AGENT_GAODE_MODES",
            "walking,transit,driving",
        )
        modes = tuple(
            ODTravelMode(item.strip())
            for item in raw_modes.split(",")
            if item.strip()
        )
        return cls(
            api_key=key,
            city_code=os.environ.get(
                "TRAVEL_AGENT_GAODE_CITY_CODE", "330100"
            ).strip(),
            timeout_seconds=float(
                os.environ.get("TRAVEL_AGENT_GAODE_TIMEOUT_SECONDS", "5")
            ),
            cache_ttl_seconds=int(
                os.environ.get("TRAVEL_AGENT_GAODE_CACHE_TTL_SECONDS", "86400")
            ),
            data_version=os.environ.get(
                "TRAVEL_AGENT_GAODE_DATA_VERSION", "gaode-route-v1"
            ).strip(),
            enabled_modes=modes,
        )


@dataclass(frozen=True, slots=True)
class GaodeRoute:
    mode: ODTravelMode
    duration_min: int
    distance_m: int
    fetched_at: datetime

    def __post_init__(self) -> None:
        if self.duration_min <= 0 or self.distance_m <= 0:
            raise ValueError("Gaode route duration and distance must be positive")
        if self.fetched_at.tzinfo is None:
            raise ValueError("Gaode fetched_at must be timezone-aware")


class GaodeHttpTransport(Protocol):
    def get_json(
        self,
        path: str,
        *,
        params: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, object]: ...


class HttpxGaodeTransport:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def get_json(
        self,
        path: str,
        *,
        params: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        try:
            response = httpx.get(
                self._base_url + path,
                params=params,
                timeout=timeout_seconds,
                headers={"Accept": "application/json"},
            )
        except httpx.TimeoutException as exc:
            raise GaodeRouteError(GaodeFailureCode.TIMEOUT, "Gaode request timed out") from exc
        except httpx.HTTPError as exc:
            raise GaodeRouteError(GaodeFailureCode.HTTP_ERROR, "Gaode request failed") from exc
        if response.status_code == 429:
            raise GaodeRouteError(GaodeFailureCode.RATE_LIMITED, "Gaode rate limited")
        if not response.is_success:
            raise GaodeRouteError(GaodeFailureCode.HTTP_ERROR, "Gaode HTTP error")
        try:
            payload = response.json()
        except ValueError as exc:
            raise GaodeRouteError(
                GaodeFailureCode.INVALID_RESPONSE,
                "Gaode returned invalid JSON",
            ) from exc
        if not isinstance(payload, dict):
            raise GaodeRouteError(
                GaodeFailureCode.INVALID_RESPONSE,
                "Gaode response must be an object",
            )
        return payload


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    route: GaodeRoute
    expires_at: datetime


class InMemoryGaodeRouteCache:
    def __init__(self) -> None:
        self._entries: dict[tuple[object, ...], _CacheEntry] = {}

    def get(self, key: tuple[object, ...], now: datetime) -> GaodeRoute | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= now:
            self._entries.pop(key, None)
            return None
        return entry.route

    def put(
        self,
        key: tuple[object, ...],
        route: GaodeRoute,
        *,
        expires_at: datetime,
    ) -> None:
        self._entries[key] = _CacheEntry(route, expires_at)


class GaodeRouteCache(Protocol):
    def get(self, key: tuple[object, ...], now: datetime) -> GaodeRoute | None: ...

    def put(
        self,
        key: tuple[object, ...],
        route: GaodeRoute,
        *,
        expires_at: datetime,
    ) -> None: ...


class JsonFileGaodeRouteCache:
    """Small cross-process cache containing routes but never credentials."""

    def __init__(self, path: str | PathLike[str]) -> None:
        self.path = Path(path)
        self._entries = self._load()

    def get(self, key: tuple[object, ...], now: datetime) -> GaodeRoute | None:
        entry = self._entries.get(_cache_key_text(key))
        if entry is None:
            return None
        if entry.expires_at <= now:
            self._entries.pop(_cache_key_text(key), None)
            self._persist()
            return None
        return entry.route

    def put(
        self,
        key: tuple[object, ...],
        route: GaodeRoute,
        *,
        expires_at: datetime,
    ) -> None:
        self._entries[_cache_key_text(key)] = _CacheEntry(route, expires_at)
        self._persist()

    def _load(self) -> dict[str, _CacheEntry]:
        if not self.path.is_file():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            raw_entries = payload["entries"]
            if payload.get("schema_version") != 1 or not isinstance(raw_entries, dict):
                raise ValueError
            entries: dict[str, _CacheEntry] = {}
            for key, raw in raw_entries.items():
                if not isinstance(key, str) or not isinstance(raw, dict):
                    raise ValueError
                route = GaodeRoute(
                    ODTravelMode(raw["mode"]),
                    int(raw["duration_min"]),
                    int(raw["distance_m"]),
                    datetime.fromisoformat(raw["fetched_at"]),
                )
                entries[key] = _CacheEntry(
                    route,
                    datetime.fromisoformat(raw["expires_at"]),
                )
            return entries
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("Gaode route cache is invalid") from exc

    def _persist(self) -> None:
        payload = {
            "schema_version": 1,
            "entries": {
                key: {
                    "mode": entry.route.mode.value,
                    "duration_min": entry.route.duration_min,
                    "distance_m": entry.route.distance_m,
                    "fetched_at": entry.route.fetched_at.isoformat(),
                    "expires_at": entry.expires_at.isoformat(),
                }
                for key, entry in sorted(self._entries.items())
            },
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)


class GaodeRouteClient:
    def __init__(
        self,
        settings: GaodeSettings,
        clock: Callable[[], datetime],
        *,
        transport: GaodeHttpTransport | None = None,
        cache: GaodeRouteCache | None = None,
    ) -> None:
        self._settings = settings
        self._clock = clock
        self._transport = transport or HttpxGaodeTransport(settings.base_url)
        self._cache = cache or InMemoryGaodeRouteCache()

    def fetch(
        self,
        origin: Coordinate,
        destination: Coordinate,
        mode: ODTravelMode,
    ) -> GaodeRoute:
        if origin == destination:
            raise ValueError("Gaode route endpoints must be different")
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("Gaode clock must return timezone-aware datetimes")
        key = _cache_key(
            origin,
            destination,
            mode,
            self._settings.city_code,
            self._settings.data_version,
        )
        cached = self._cache.get(key, now)
        if cached is not None:
            return cached
        try:
            payload = self._transport.get_json(
                _path_for(mode),
                params=_params_for(self._settings, origin, destination, mode),
                timeout_seconds=self._settings.timeout_seconds,
            )
            route = _parse_route(payload, mode, now)
        except GaodeRouteError as exc:
            if exc.occurred_at is not None:
                raise
            raise GaodeRouteError(
                exc.code,
                str(exc),
                infocode=exc.infocode,
                occurred_at=now,
            ) from exc
        self._cache.put(
            key,
            route,
            expires_at=now + timedelta(seconds=self._settings.cache_ttl_seconds),
        )
        return route


@dataclass(frozen=True, slots=True)
class GaodeSnapshotBuildReport:
    requested_pair_count: int
    gaode_pair_count: int
    fallback_pair_count: int
    missing_pair_count: int
    failure_counts: tuple[tuple[str, int], ...]
    failure_details: tuple[GaodeFailureDetail, ...] = ()

    @property
    def complete(self) -> bool:
        return self.missing_pair_count == 0


@dataclass(frozen=True, slots=True)
class GaodeSnapshotBuild:
    provider: InMemoryTravelTimeProvider
    report: GaodeSnapshotBuildReport


@dataclass(frozen=True, slots=True)
class GaodeFailureDetail:
    origin_id: int
    destination_id: int
    mode: ODTravelMode
    code: GaodeFailureCode
    infocode: str | None
    occurred_at: str | None


class GaodeODSnapshotBuilder:
    """Fetch all directed pairs once and return a replayable provider."""

    def __init__(self, settings: GaodeSettings, client: GaodeRouteClient) -> None:
        self._settings = settings
        self._client = client

    def build(
        self,
        coordinates: Mapping[int, Coordinate],
        *,
        fallback: TravelTimeProvider | None = None,
    ) -> GaodeSnapshotBuild:
        ordered = tuple(sorted(coordinates.items()))
        results: dict[tuple[int, int], TravelTimeResult] = {}
        failures: dict[str, int] = {}
        failure_details: list[GaodeFailureDetail] = []
        gaode_count = 0
        fallback_count = 0
        missing_count = 0
        fetched_times: list[datetime] = []
        for origin_id, origin in ordered:
            for destination_id, destination in ordered:
                if origin_id == destination_id:
                    continue
                routes: list[GaodeRoute] = []
                pair_failures: list[GaodeFailureCode] = []
                for mode in self._settings.enabled_modes:
                    try:
                        routes.append(self._client.fetch(origin, destination, mode))
                    except GaodeRouteError as exc:
                        pair_failures.append(exc.code)
                        failures[exc.code.value] = failures.get(exc.code.value, 0) + 1
                        failure_details.append(
                            GaodeFailureDetail(
                                origin_id,
                                destination_id,
                                mode,
                                exc.code,
                                exc.infocode,
                                (
                                    exc.occurred_at.isoformat()
                                    if exc.occurred_at is not None
                                    else None
                                ),
                            )
                        )
                selected = _select_route(routes)
                if selected is not None:
                    results[(origin_id, destination_id)] = TravelTimeResult(
                        origin_id,
                        destination_id,
                        selected.duration_min,
                        ODBasis.GAODE,
                        self._settings.data_version,
                        selected.fetched_at,
                        selected.mode,
                        selected.distance_m,
                    )
                    fetched_times.append(selected.fetched_at)
                    gaode_count += 1
                    continue
                approximate = (
                    fallback.get_travel_time(origin_id, destination_id)
                    if fallback is not None
                    else None
                )
                if approximate is not None:
                    reason = _fallback_reason(pair_failures)
                    results[(origin_id, destination_id)] = replace(
                        approximate,
                        fallback_reason=reason,
                    )
                    fallback_count += 1
                else:
                    missing_count += 1

        fetched_at = max(fetched_times) if fetched_times else None
        provider = InMemoryTravelTimeProvider(
            results,
            default_basis=ODBasis.GAODE,
            data_version=self._settings.data_version,
            fetched_at=fetched_at,
        )
        pair_count = len(ordered) * max(0, len(ordered) - 1)
        return GaodeSnapshotBuild(
            provider,
            GaodeSnapshotBuildReport(
                pair_count,
                gaode_count,
                fallback_count,
                missing_count,
                tuple(sorted(failures.items())),
                tuple(failure_details),
            ),
        )


def _cache_key(
    origin: Coordinate,
    destination: Coordinate,
    mode: ODTravelMode,
    city_code: str,
    data_version: str,
) -> tuple[object, ...]:
    return (
        round(origin.lng, 6),
        round(origin.lat, 6),
        round(destination.lng, 6),
        round(destination.lat, 6),
        mode.value,
        city_code,
        data_version,
        "strategy-0" if mode is ODTravelMode.DRIVING else "default",
    )


def _cache_key_text(key: tuple[object, ...]) -> str:
    return json.dumps(key, ensure_ascii=False, separators=(",", ":"))


def _path_for(mode: ODTravelMode) -> str:
    return {
        ODTravelMode.WALKING: "/v3/direction/walking",
        ODTravelMode.TRANSIT: "/v3/direction/transit/integrated",
        ODTravelMode.DRIVING: "/v3/direction/driving",
    }[mode]


def _params_for(
    settings: GaodeSettings,
    origin: Coordinate,
    destination: Coordinate,
    mode: ODTravelMode,
) -> dict[str, str]:
    params = {
        "key": settings.api_key,
        "origin": f"{origin.lng:.6f},{origin.lat:.6f}",
        "destination": f"{destination.lng:.6f},{destination.lat:.6f}",
        "extensions": "base",
    }
    if mode is ODTravelMode.TRANSIT:
        params["city"] = settings.city_code
        params["cityd"] = settings.city_code
    elif mode is ODTravelMode.DRIVING:
        params["strategy"] = "0"
    return params


def _parse_route(
    payload: Mapping[str, object],
    mode: ODTravelMode,
    fetched_at: datetime,
) -> GaodeRoute:
    status = str(payload.get("status", ""))
    infocode = str(payload.get("infocode", ""))
    if status != "1" or infocode != "10000":
        code = (
            GaodeFailureCode.RATE_LIMITED
            if infocode in GAODE_RATE_LIMIT_CODES
            else GaodeFailureCode.API_ERROR
        )
        raise GaodeRouteError(
            code,
            "Gaode API rejected the route request",
            infocode=infocode or None,
        )
    route = payload.get("route")
    if not isinstance(route, dict):
        raise GaodeRouteError(
            GaodeFailureCode.INVALID_RESPONSE,
            "Gaode response has no route object",
        )
    collection_name = "transits" if mode is ODTravelMode.TRANSIT else "paths"
    candidates = route.get(collection_name)
    if not isinstance(candidates, list) or not candidates:
        raise GaodeRouteError(
            GaodeFailureCode.NO_ROUTE,
            "Gaode returned no route",
            infocode=infocode or None,
        )
    first = candidates[0]
    if not isinstance(first, dict):
        raise GaodeRouteError(
            GaodeFailureCode.INVALID_RESPONSE,
            "Gaode route candidate must be an object",
        )
    try:
        duration_seconds = int(first["duration"])
        distance_m = int(first["distance"])
    except (KeyError, TypeError, ValueError) as exc:
        raise GaodeRouteError(
            GaodeFailureCode.INVALID_RESPONSE,
            "Gaode route duration or distance is invalid",
        ) from exc
    if duration_seconds <= 0 or distance_m <= 0:
        raise GaodeRouteError(
            GaodeFailureCode.INVALID_RESPONSE,
            "Gaode route duration and distance must be positive",
        )
    return GaodeRoute(
        mode,
        max(1, math.ceil(duration_seconds / 60)),
        distance_m,
        fetched_at,
    )


def _select_route(routes: list[GaodeRoute]) -> GaodeRoute | None:
    if not routes:
        return None
    by_mode = {route.mode: route for route in routes}
    walking = by_mode.get(ODTravelMode.WALKING)
    if walking is not None and walking.distance_m <= 2_000 and walking.duration_min <= 35:
        return walking
    transit = by_mode.get(ODTravelMode.TRANSIT)
    driving = by_mode.get(ODTravelMode.DRIVING)
    if transit is not None and (
        driving is None or transit.duration_min <= driving.duration_min + 15
    ):
        return transit
    if driving is not None:
        return driving
    return min(routes, key=lambda item: (item.duration_min, item.mode.value))


def _fallback_reason(failures: list[GaodeFailureCode]) -> str:
    if not failures:
        return "gaode_no_supported_route"
    priority = (
        GaodeFailureCode.RATE_LIMITED,
        GaodeFailureCode.TIMEOUT,
        GaodeFailureCode.HTTP_ERROR,
        GaodeFailureCode.API_ERROR,
        GaodeFailureCode.NO_ROUTE,
        GaodeFailureCode.INVALID_RESPONSE,
    )
    for code in priority:
        if code in failures:
            return f"gaode_{code.value}"
    return "gaode_unavailable"
