"""Validate real Redis governance and route-cache behavior without provider calls."""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from redis import Redis

from travel_agent.infrastructure.provider_governance import (
    ProviderBlockCode,
    ProviderGovernancePolicy,
    ProviderRequestBlocked,
    RedisProviderRequestGovernor,
)
from travel_agent.infrastructure.solver import GaodeRoute, RedisGaodeRouteCache
from travel_agent.solver import ODTravelMode


def main() -> None:
    redis_url = os.environ.get("TRAVEL_AGENT_PROVIDER_REDIS_URL")
    if not redis_url:
        raise SystemExit("TRAVEL_AGENT_PROVIDER_REDIS_URL is required")

    run_id = uuid.uuid4().hex[:12]
    key_prefix = f"travel-agent:validation:{run_id}"
    now = datetime(2026, 8, 28, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    clients = [Redis.from_url(redis_url, decode_responses=True) for _ in range(12)]
    if any(not client.ping() for client in clients):
        raise AssertionError("Redis PING failed")

    try:
        concurrency_policy = ProviderGovernancePolicy(
            provider="concurrency",
            daily_request_budget=20,
            minimum_interval_seconds=0,
            consecutive_failure_threshold=3,
            circuit_open_seconds=60,
        )

        def consume_request(index: int) -> None:
            governor = RedisProviderRequestGovernor(
                clients[index],
                concurrency_policy,
                lambda: now,
                key_prefix=key_prefix,
            )
            governor.before_request()
            governor.record_success()

        with ThreadPoolExecutor(max_workers=10) as executor:
            list(executor.map(consume_request, range(10)))

        concurrency_snapshot = RedisProviderRequestGovernor(
            clients[10],
            concurrency_policy,
            lambda: now,
            key_prefix=key_prefix,
        ).snapshot()
        if (
            concurrency_snapshot.request_count != 10
            or concurrency_snapshot.success_count != 10
            or concurrency_snapshot.failure_count != 0
        ):
            raise AssertionError("concurrent Redis governance counters were lost")

        circuit_policy = ProviderGovernancePolicy(
            provider="circuit",
            daily_request_budget=10,
            minimum_interval_seconds=0,
            consecutive_failure_threshold=2,
            circuit_open_seconds=60,
            circuit_failure_codes=frozenset({"timeout", "http_error"}),
        )
        first_governor = RedisProviderRequestGovernor(
            clients[0], circuit_policy, lambda: now, key_prefix=key_prefix
        )
        second_governor = RedisProviderRequestGovernor(
            clients[1], circuit_policy, lambda: now, key_prefix=key_prefix
        )
        first_governor.before_request()
        first_governor.record_failure("timeout")
        second_governor.before_request()
        second_governor.record_failure("http_error")
        try:
            first_governor.before_request()
        except ProviderRequestBlocked as exc:
            if exc.code is not ProviderBlockCode.CIRCUIT_OPEN:
                raise
        else:
            raise AssertionError("shared Redis circuit did not open")

        rate_limit_policy = ProviderGovernancePolicy(
            provider="rate-limit",
            daily_request_budget=10,
            minimum_interval_seconds=0,
            circuit_open_seconds=60,
        )
        rate_limit_governor = RedisProviderRequestGovernor(
            clients[2], rate_limit_policy, lambda: now, key_prefix=key_prefix
        )
        rate_limit_governor.before_request()
        rate_limit_governor.record_failure("rate_limited")
        try:
            rate_limit_governor.before_request()
        except ProviderRequestBlocked as exc:
            if exc.code is not ProviderBlockCode.CIRCUIT_OPEN:
                raise
        else:
            raise AssertionError("rate_limited did not open the circuit immediately")

        route_key = (
            "120.165000,30.250000",
            "120.175000,30.260000",
            ODTravelMode.WALKING.value,
        )
        route = GaodeRoute(ODTravelMode.WALKING, 18, 1450, now)
        first_cache = RedisGaodeRouteCache(clients[3], key_prefix=key_prefix)
        second_cache = RedisGaodeRouteCache(clients[4], key_prefix=key_prefix)
        first_cache.put(route_key, route, expires_at=now + timedelta(minutes=10))
        if second_cache.get(route_key, now) != route:
            raise AssertionError("second Redis client could not reuse route cache")

        stored_keys = list(clients[5].scan_iter(match=f"{key_prefix}:*"))
        stored_values = [clients[5].get(key) for key in stored_keys]
        serialized = f"{stored_keys!r}{stored_values!r}"
        if "120.165000" in str(stored_keys) or "120.175000" in str(stored_keys):
            raise AssertionError("Redis route key exposed plaintext coordinates")
        for forbidden in ("api_key", "password", "redis://", "rediss://"):
            if forbidden in serialized.lower():
                raise AssertionError(f"Redis state exposed forbidden value: {forbidden}")

        print("Redis runtime validation passed.")
        print("Ten concurrent clients preserved all governance counters.")
        print("Shared threshold and immediate rate-limit circuits passed.")
        print("Cross-client route cache reuse and hashed coordinate keys passed.")
    finally:
        cleanup_keys = list(clients[0].scan_iter(match=f"{key_prefix}:*"))
        if cleanup_keys:
            clients[0].delete(*cleanup_keys)
        for client in clients:
            client.close()


if __name__ == "__main__":
    main()
