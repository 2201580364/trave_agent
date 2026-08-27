"""A6-8.1 durable quota, rate-window and circuit-breaker tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import fakeredis
import pytest

from travel_agent.infrastructure.provider_governance import (
    JsonProviderRequestGovernor,
    ProviderBlockCode,
    ProviderGovernancePolicy,
    ProviderRequestBlocked,
    RedisProviderRequestGovernor,
    read_provider_usage,
    read_redis_provider_usage,
)

NOW = datetime(2026, 8, 27, 8, 0, tzinfo=UTC)


class FixedClock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


def _policy(**overrides: object) -> ProviderGovernancePolicy:
    values: dict[str, object] = {
        "provider": "gaode",
        "daily_request_budget": 3,
        "minimum_interval_seconds": 1.0,
        "consecutive_failure_threshold": 2,
        "circuit_open_seconds": 60,
        "circuit_failure_codes": frozenset({"timeout", "http_error"}),
    }
    values.update(overrides)
    return ProviderGovernancePolicy(**values)  # type: ignore[arg-type]


def test_governor_tracks_credential_free_usage_and_shared_instances(tmp_path) -> None:
    path = tmp_path / "provider-governance.json"
    clock = FixedClock()
    first = JsonProviderRequestGovernor(path, _policy(), clock)
    second = JsonProviderRequestGovernor(path, _policy(), clock)

    first.before_request()
    first.record_success()
    clock.now += timedelta(seconds=1)
    second.before_request()
    second.record_failure("timeout")

    snapshot = first.snapshot()
    persisted = path.read_text(encoding="utf-8")

    assert snapshot.request_count == 2
    assert snapshot.remaining_request_budget == 1
    assert snapshot.success_count == 1
    assert snapshot.failure_count == 1
    assert snapshot.failure_counts == (("timeout", 1),)
    assert "credential" not in persisted
    assert read_provider_usage(path) == (snapshot,)


def test_governor_enforces_cross_process_request_interval(tmp_path) -> None:
    clock = FixedClock()
    governor = JsonProviderRequestGovernor(
        tmp_path / "state.json",
        _policy(),
        clock,
    )
    governor.before_request()

    with pytest.raises(ProviderRequestBlocked) as raised:
        governor.before_request()

    assert raised.value.code is ProviderBlockCode.RATE_WINDOW
    assert raised.value.retry_at == NOW + timedelta(seconds=1)


def test_governor_blocks_after_daily_safety_budget(tmp_path) -> None:
    clock = FixedClock()
    governor = JsonProviderRequestGovernor(
        tmp_path / "state.json",
        _policy(daily_request_budget=2, minimum_interval_seconds=0),
        clock,
    )
    governor.before_request()
    governor.before_request()

    with pytest.raises(ProviderRequestBlocked) as raised:
        governor.before_request()

    assert raised.value.code is ProviderBlockCode.DAILY_BUDGET_EXHAUSTED


def test_governor_opens_and_recovers_circuit(tmp_path) -> None:
    clock = FixedClock()
    governor = JsonProviderRequestGovernor(
        tmp_path / "state.json",
        _policy(minimum_interval_seconds=0),
        clock,
    )
    governor.before_request()
    governor.record_failure("timeout")
    governor.before_request()
    governor.record_failure("http_error")

    with pytest.raises(ProviderRequestBlocked) as raised:
        governor.before_request()

    assert raised.value.code is ProviderBlockCode.CIRCUIT_OPEN
    assert raised.value.retry_at == NOW + timedelta(seconds=60)

    clock.now += timedelta(seconds=60)
    governor.before_request()
    governor.record_success()

    assert governor.snapshot().consecutive_failures == 0
    assert governor.snapshot().circuit_open_until is None


def test_rate_limit_opens_circuit_immediately(tmp_path) -> None:
    governor = JsonProviderRequestGovernor(
        tmp_path / "state.json",
        _policy(minimum_interval_seconds=0),
        FixedClock(),
    )
    governor.before_request()
    governor.record_failure("rate_limited")

    with pytest.raises(ProviderRequestBlocked) as raised:
        governor.before_request()

    assert raised.value.code is ProviderBlockCode.CIRCUIT_OPEN


def test_daily_counts_roll_over_without_erasing_active_circuit(tmp_path) -> None:
    clock = FixedClock()
    governor = JsonProviderRequestGovernor(
        tmp_path / "state.json",
        _policy(minimum_interval_seconds=0, circuit_open_seconds=86_500),
        clock,
    )
    governor.before_request()
    governor.record_failure("rate_limited")
    clock.now += timedelta(days=1)

    snapshot = governor.snapshot()

    assert snapshot.quota_day == "2026-08-28"
    assert snapshot.request_count == 0
    assert snapshot.failure_count == 0
    assert snapshot.circuit_open_until is not None


def test_redis_governor_shares_budget_and_circuit_across_clients() -> None:
    server = fakeredis.FakeServer()
    first_client = fakeredis.FakeRedis(server=server, decode_responses=True)
    second_client = fakeredis.FakeRedis(server=server, decode_responses=True)
    clock = FixedClock()
    first = RedisProviderRequestGovernor(
        first_client,  # type: ignore[arg-type]
        _policy(minimum_interval_seconds=0),
        clock,
        key_prefix="test-travel-agent",
    )
    second = RedisProviderRequestGovernor(
        second_client,  # type: ignore[arg-type]
        _policy(minimum_interval_seconds=0),
        clock,
        key_prefix="test-travel-agent",
    )

    first.before_request()
    first.record_failure("timeout")
    second.before_request()
    second.record_failure("http_error")

    with pytest.raises(ProviderRequestBlocked) as raised:
        first.before_request()

    assert raised.value.code is ProviderBlockCode.CIRCUIT_OPEN
    assert second.snapshot().request_count == 2
    assert read_redis_provider_usage(
        first_client,  # type: ignore[arg-type]
        key_prefix="test-travel-agent",
    ) == (second.snapshot(),)


def test_redis_governor_does_not_store_credentials() -> None:
    client = fakeredis.FakeRedis(decode_responses=True)
    governor = RedisProviderRequestGovernor(
        client,  # type: ignore[arg-type]
        _policy(provider="qweather", minimum_interval_seconds=0),
        FixedClock(),
        key_prefix="test-travel-agent",
    )

    governor.before_request()
    governor.record_success()

    keys = list(client.scan_iter(match="test-travel-agent:*"))
    values = [client.get(key) for key in keys]
    serialized = f"{keys!r}{values!r}"
    assert "api_key" not in serialized
    assert "password" not in serialized
