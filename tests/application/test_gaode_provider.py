"""A6-8.1 Gaode real-routing provider tests without live credentials."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

import fakeredis
import pytest

from travel_agent.infrastructure.solver import (
    GaodeFailureCode,
    GaodeODSnapshotBuilder,
    GaodeRouteClient,
    GaodeRouteError,
    GaodeSettings,
    InMemoryGaodeRouteCache,
    JsonFileGaodeRouteCache,
    RedisGaodeRouteCache,
)
from travel_agent.solver import (
    ApproximateTravelTimeProvider,
    Coordinate,
    ODBasis,
    ODTravelMode,
)

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)
ORIGIN = Coordinate(30.2590, 120.1650)
DESTINATION = Coordinate(30.2525, 120.1495)


class FixedClock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


class FakeTransport:
    def __init__(
        self,
        responses: Mapping[str, Mapping[str, object]] | None = None,
        error: GaodeRouteError | None = None,
    ) -> None:
        self.responses = dict(responses or {})
        self.error = error
        self.calls: list[tuple[str, dict[str, str], float]] = []

    def get_json(
        self,
        path: str,
        *,
        params: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        self.calls.append((path, dict(params), timeout_seconds))
        if self.error is not None:
            raise self.error
        return self.responses[path]


def _payload(
    *,
    duration_seconds: int,
    distance_m: int,
    transit: bool = False,
) -> dict[str, object]:
    collection = "transits" if transit else "paths"
    return {
        "status": "1",
        "infocode": "10000",
        "route": {
            collection: [
                {
                    "duration": str(duration_seconds),
                    "distance": str(distance_m),
                }
            ]
        },
    }


def test_gaode_settings_load_env_without_exposing_key(monkeypatch) -> None:
    monkeypatch.setenv("TRAVEL_AGENT_GAODE_API_KEY", "gaode-secret")
    monkeypatch.setenv("TRAVEL_AGENT_GAODE_CITY_CODE", "330100")
    monkeypatch.setenv("TRAVEL_AGENT_GAODE_TIMEOUT_SECONDS", "3.5")
    monkeypatch.setenv("TRAVEL_AGENT_GAODE_CACHE_TTL_SECONDS", "600")
    monkeypatch.setenv("TRAVEL_AGENT_GAODE_MODES", "walking,driving")

    settings = GaodeSettings.from_env(load_dotenv_file=False)

    assert settings.timeout_seconds == 3.5
    assert settings.cache_ttl_seconds == 600
    assert settings.enabled_modes == (
        ODTravelMode.WALKING,
        ODTravelMode.DRIVING,
    )
    assert "gaode-secret" not in repr(settings)


def test_gaode_settings_require_key(monkeypatch) -> None:
    monkeypatch.delenv("TRAVEL_AGENT_GAODE_API_KEY", raising=False)

    with pytest.raises(ValueError, match="GAODE_API_KEY"):
        GaodeSettings.from_env(load_dotenv_file=False)


def test_gaode_client_parses_walking_route_and_uses_ttl_cache() -> None:
    clock = FixedClock()
    request_gates: list[str] = []
    outcomes: list[str] = []
    transport = FakeTransport(
        {
            "/v3/direction/walking": _payload(
                duration_seconds=601,
                distance_m=1350,
            )
        }
    )
    settings = GaodeSettings(
        "secret",
        timeout_seconds=4,
        cache_ttl_seconds=60,
        enabled_modes=(ODTravelMode.WALKING,),
    )
    client = GaodeRouteClient(
        settings,
        clock,
        transport=transport,
        cache=InMemoryGaodeRouteCache(),
        before_request=lambda: request_gates.append("request"),
        on_success=lambda: outcomes.append("success"),
        on_failure=lambda code: outcomes.append(f"failure:{code}"),
    )

    first = client.fetch(ORIGIN, DESTINATION, ODTravelMode.WALKING)
    second = client.fetch(ORIGIN, DESTINATION, ODTravelMode.WALKING)

    assert first == second
    assert first.duration_min == 11
    assert first.distance_m == 1350
    assert first.mode is ODTravelMode.WALKING
    assert len(transport.calls) == 1
    assert request_gates == ["request"]
    assert outcomes == ["success"]
    path, params, timeout = transport.calls[0]
    assert path == "/v3/direction/walking"
    assert params["origin"] == "120.165000,30.259000"
    assert params["destination"] == "120.149500,30.252500"
    assert params["key"] == "secret"
    assert timeout == 4

    clock.now += timedelta(seconds=61)
    client.fetch(ORIGIN, DESTINATION, ODTravelMode.WALKING)
    assert len(transport.calls) == 2
    assert request_gates == ["request", "request"]
    assert outcomes == ["success", "success"]


def test_gaode_cache_does_not_mix_route_data_versions() -> None:
    clock = FixedClock()
    cache = InMemoryGaodeRouteCache()
    transport = FakeTransport(
        {
            "/v3/direction/walking": _payload(
                duration_seconds=600,
                distance_m=1_200,
            )
        }
    )
    first = GaodeRouteClient(
        GaodeSettings(
            "secret",
            data_version="gaode-v1",
            enabled_modes=(ODTravelMode.WALKING,),
        ),
        clock,
        transport=transport,
        cache=cache,
    )
    second = GaodeRouteClient(
        GaodeSettings(
            "secret",
            data_version="gaode-v2",
            enabled_modes=(ODTravelMode.WALKING,),
        ),
        clock,
        transport=transport,
        cache=cache,
    )

    first.fetch(ORIGIN, DESTINATION, ODTravelMode.WALKING)
    second.fetch(ORIGIN, DESTINATION, ODTravelMode.WALKING)

    assert len(transport.calls) == 2


def test_gaode_client_classifies_api_rate_limit() -> None:
    failures: list[str] = []
    transport = FakeTransport(
        {
            "/v3/direction/driving": {
                "status": "0",
                "infocode": "10044",
                "info": "USER_DAILY_QUERY_OVER_LIMIT",
            }
        }
    )
    client = GaodeRouteClient(
        GaodeSettings("secret", enabled_modes=(ODTravelMode.DRIVING,)),
        FixedClock(),
        transport=transport,
        on_failure=failures.append,
    )

    with pytest.raises(GaodeRouteError) as raised:
        client.fetch(ORIGIN, DESTINATION, ODTravelMode.DRIVING)

    assert raised.value.code is GaodeFailureCode.RATE_LIMITED
    assert raised.value.infocode == "10044"
    assert raised.value.occurred_at == NOW
    assert failures == ["rate_limited"]


def test_gaode_file_cache_reuses_routes_without_storing_key(tmp_path) -> None:
    cache_path = tmp_path / "gaode-routes.json"
    settings = GaodeSettings(
        "secret-not-for-cache",
        data_version="gaode-cache-test-v1",
        enabled_modes=(ODTravelMode.WALKING,),
    )
    first_transport = FakeTransport(
        {
            "/v3/direction/walking": _payload(
                duration_seconds=600,
                distance_m=1_200,
            )
        }
    )
    first = GaodeRouteClient(
        settings,
        FixedClock(),
        transport=first_transport,
        cache=JsonFileGaodeRouteCache(cache_path),
    )

    fetched = first.fetch(ORIGIN, DESTINATION, ODTravelMode.WALKING)
    second_transport = FakeTransport(
        error=GaodeRouteError(GaodeFailureCode.TIMEOUT, "must not be called")
    )
    second = GaodeRouteClient(
        settings,
        FixedClock(),
        transport=second_transport,
        cache=JsonFileGaodeRouteCache(cache_path),
    )

    cached = second.fetch(ORIGIN, DESTINATION, ODTravelMode.WALKING)

    assert cached == fetched
    assert len(first_transport.calls) == 1
    assert second_transport.calls == []
    assert "secret-not-for-cache" not in cache_path.read_text(encoding="utf-8")


def test_gaode_redis_cache_reuses_routes_across_clients_without_credentials() -> None:
    server = fakeredis.FakeServer()
    first_redis = fakeredis.FakeRedis(server=server, decode_responses=True)
    second_redis = fakeredis.FakeRedis(server=server, decode_responses=True)
    settings = GaodeSettings(
        "secret-not-for-redis",
        data_version="gaode-redis-test-v1",
        enabled_modes=(ODTravelMode.WALKING,),
    )
    first_transport = FakeTransport(
        {
            "/v3/direction/walking": _payload(
                duration_seconds=600,
                distance_m=1_200,
            )
        }
    )
    first = GaodeRouteClient(
        settings,
        FixedClock(),
        transport=first_transport,
        cache=RedisGaodeRouteCache(
            first_redis,  # type: ignore[arg-type]
            key_prefix="test-travel-agent",
        ),
    )
    fetched = first.fetch(ORIGIN, DESTINATION, ODTravelMode.WALKING)
    second_transport = FakeTransport(
        error=GaodeRouteError(GaodeFailureCode.TIMEOUT, "must not be called")
    )
    second = GaodeRouteClient(
        settings,
        FixedClock(),
        transport=second_transport,
        cache=RedisGaodeRouteCache(
            second_redis,  # type: ignore[arg-type]
            key_prefix="test-travel-agent",
        ),
    )

    cached = second.fetch(ORIGIN, DESTINATION, ODTravelMode.WALKING)
    keys = list(first_redis.scan_iter(match="test-travel-agent:gaode-route:*"))
    values = [first_redis.get(key) for key in keys]

    assert cached == fetched
    assert second_transport.calls == []
    assert len(keys) == 1
    assert "secret-not-for-redis" not in f"{keys!r}{values!r}"
    assert "120.165" not in str(keys)


def test_gaode_builder_materializes_both_directions_and_selects_walking() -> None:
    transport = FakeTransport(
        {
            "/v3/direction/walking": _payload(
                duration_seconds=900,
                distance_m=1500,
            ),
            "/v3/direction/driving": _payload(
                duration_seconds=480,
                distance_m=2200,
            ),
        }
    )
    settings = GaodeSettings(
        "secret",
        data_version="gaode-hangzhou-test-v1",
        enabled_modes=(ODTravelMode.WALKING, ODTravelMode.DRIVING),
    )
    client = GaodeRouteClient(settings, FixedClock(), transport=transport)

    built = GaodeODSnapshotBuilder(settings, client).build(
        {1: ORIGIN, 2: DESTINATION}
    )

    forward = built.provider.get_travel_time(1, 2)
    backward = built.provider.get_travel_time(2, 1)
    assert forward is not None and backward is not None
    assert forward.basis is ODBasis.GAODE
    assert forward.travel_mode is ODTravelMode.WALKING
    assert forward.distance_m == 1500
    assert forward.data_version == "gaode-hangzhou-test-v1"
    assert built.report.requested_pair_count == 2
    assert built.report.gaode_pair_count == 2
    assert built.report.complete
    assert len(transport.calls) == 4
    assert transport.calls[0][1]["origin"] != transport.calls[2][1]["origin"]


def test_gaode_builder_prefers_transit_when_close_to_driving_time() -> None:
    transport = FakeTransport(
        {
            "/v3/direction/transit/integrated": _payload(
                duration_seconds=1_800,
                distance_m=9_000,
                transit=True,
            ),
            "/v3/direction/driving": _payload(
                duration_seconds=1_200,
                distance_m=8_000,
            ),
        }
    )
    settings = GaodeSettings(
        "secret",
        enabled_modes=(ODTravelMode.TRANSIT, ODTravelMode.DRIVING),
    )
    client = GaodeRouteClient(settings, FixedClock(), transport=transport)

    built = GaodeODSnapshotBuilder(settings, client).build(
        {1: ORIGIN, 2: DESTINATION}
    )

    result = built.provider.get_travel_time(1, 2)
    assert result is not None
    assert result.travel_mode is ODTravelMode.TRANSIT
    assert result.travel_min == 30


def test_gaode_builder_transparently_falls_back_after_timeout() -> None:
    settings = GaodeSettings(
        "secret",
        enabled_modes=(ODTravelMode.DRIVING,),
    )
    transport = FakeTransport(
        error=GaodeRouteError(GaodeFailureCode.TIMEOUT, "timeout")
    )
    client = GaodeRouteClient(settings, FixedClock(), transport=transport)
    fallback = ApproximateTravelTimeProvider(
        {1: ORIGIN, 2: DESTINATION},
        data_version="approx-fallback-v1",
        fetched_at=NOW,
    )

    built = GaodeODSnapshotBuilder(settings, client).build(
        {1: ORIGIN, 2: DESTINATION},
        fallback=fallback,
    )

    result = built.provider.get_travel_time(1, 2)
    assert result is not None
    assert result.basis is ODBasis.APPROXIMATE
    assert result.fallback_reason == "gaode_timeout"
    assert built.report.fallback_pair_count == 2
    assert built.report.missing_pair_count == 0
    assert dict(built.report.failure_counts) == {"timeout": 2}
    assert {
        (
            item.origin_id,
            item.destination_id,
            item.mode,
            item.code,
            item.infocode,
            item.occurred_at,
        )
        for item in built.report.failure_details
    } == {
        (1, 2, ODTravelMode.DRIVING, GaodeFailureCode.TIMEOUT, None, NOW.isoformat()),
        (2, 1, ODTravelMode.DRIVING, GaodeFailureCode.TIMEOUT, None, NOW.isoformat()),
    }


def test_gaode_builder_reports_missing_pairs_without_fallback() -> None:
    settings = GaodeSettings(
        "secret",
        enabled_modes=(ODTravelMode.DRIVING,),
    )
    client = GaodeRouteClient(
        settings,
        FixedClock(),
        transport=FakeTransport(
            error=GaodeRouteError(GaodeFailureCode.NO_ROUTE, "no route")
        ),
    )

    built = GaodeODSnapshotBuilder(settings, client).build(
        {1: ORIGIN, 2: DESTINATION}
    )

    assert built.provider.get_travel_time(1, 2) is None
    assert built.report.missing_pair_count == 2
    assert not built.report.complete
    assert len(built.report.failure_details) == 2
    assert all(
        item.code is GaodeFailureCode.NO_ROUTE
        for item in built.report.failure_details
    )
