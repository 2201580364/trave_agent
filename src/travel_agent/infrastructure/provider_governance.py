"""Durable local governance for third-party snapshot-build requests.

The solver and production HTTP request path never call these providers. This
module protects the separate publication workflow with a daily safety budget,
cross-process request spacing, a circuit breaker and a credential-free status
file that can be inspected by operations.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Protocol, TypeVar
from zoneinfo import ZoneInfo

from redis import Redis
from redis.exceptions import WatchError

from travel_agent.observability.file_lock import InterProcessFileLock

_T = TypeVar("_T")


class ProviderBlockCode(StrEnum):
    RATE_WINDOW = "rate_window"
    DAILY_BUDGET_EXHAUSTED = "daily_budget_exhausted"
    CIRCUIT_OPEN = "circuit_open"


class ProviderRequestBlocked(RuntimeError):
    def __init__(
        self,
        code: ProviderBlockCode,
        message: str,
        *,
        retry_at: datetime | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retry_at = retry_at


class ProviderRequestGovernor(Protocol):
    def before_request(self) -> None: ...

    def record_success(self) -> None: ...

    def record_failure(self, failure_code: str) -> None: ...

    def snapshot(self) -> ProviderUsageSnapshot: ...


@dataclass(frozen=True, slots=True)
class ProviderGovernancePolicy:
    provider: str
    daily_request_budget: int
    minimum_interval_seconds: float = 0.0
    consecutive_failure_threshold: int = 3
    circuit_open_seconds: int = 5 * 60
    circuit_failure_codes: frozenset[str] = frozenset()
    immediate_circuit_codes: frozenset[str] = frozenset({"rate_limited"})
    quota_timezone: str = "Asia/Shanghai"

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider governance name is required")
        if self.daily_request_budget <= 0:
            raise ValueError("provider daily request budget must be positive")
        if self.minimum_interval_seconds < 0:
            raise ValueError("provider minimum request interval must be non-negative")
        if self.consecutive_failure_threshold <= 0:
            raise ValueError("provider failure threshold must be positive")
        if self.circuit_open_seconds <= 0:
            raise ValueError("provider circuit open seconds must be positive")
        ZoneInfo(self.quota_timezone)


@dataclass(frozen=True, slots=True)
class ProviderUsageSnapshot:
    provider: str
    quota_day: str
    daily_request_budget: int
    request_count: int
    success_count: int
    failure_count: int
    consecutive_failures: int
    failure_counts: tuple[tuple[str, int], ...]
    last_request_at: str | None
    circuit_open_until: str | None

    @property
    def remaining_request_budget(self) -> int:
        return max(0, self.daily_request_budget - self.request_count)

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "quota_day": self.quota_day,
            "daily_request_budget": self.daily_request_budget,
            "request_count": self.request_count,
            "remaining_request_budget": self.remaining_request_budget,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "consecutive_failures": self.consecutive_failures,
            "failure_counts": dict(self.failure_counts),
            "last_request_at": self.last_request_at,
            "circuit_open_until": self.circuit_open_until,
        }


@dataclass(slots=True)
class _ProviderState:
    quota_day: date
    daily_request_budget: int
    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    failure_counts: dict[str, int] = field(default_factory=dict)
    last_request_at: datetime | None = None
    circuit_open_until: datetime | None = None

    def rollover(self, quota_day: date, daily_request_budget: int) -> None:
        self.quota_day = quota_day
        self.daily_request_budget = daily_request_budget
        self.request_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.failure_counts = {}

    def snapshot(self, provider: str) -> ProviderUsageSnapshot:
        return ProviderUsageSnapshot(
            provider,
            self.quota_day.isoformat(),
            self.daily_request_budget,
            self.request_count,
            self.success_count,
            self.failure_count,
            self.consecutive_failures,
            tuple(sorted(self.failure_counts.items())),
            self.last_request_at.isoformat() if self.last_request_at else None,
            (
                self.circuit_open_until.isoformat()
                if self.circuit_open_until is not None
                else None
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "quota_day": self.quota_day.isoformat(),
            "daily_request_budget": self.daily_request_budget,
            "request_count": self.request_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "consecutive_failures": self.consecutive_failures,
            "failure_counts": dict(sorted(self.failure_counts.items())),
            "last_request_at": (
                self.last_request_at.isoformat()
                if self.last_request_at is not None
                else None
            ),
            "circuit_open_until": (
                self.circuit_open_until.isoformat()
                if self.circuit_open_until is not None
                else None
            ),
        }


class JsonProviderRequestGovernor:
    """Coordinate provider usage across processes through a locked JSON file."""

    def __init__(
        self,
        path: str | Path,
        policy: ProviderGovernancePolicy,
        clock: Callable[[], datetime],
    ) -> None:
        self.path = Path(path)
        self._lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self._policy = policy
        self._clock = clock
        self._timezone = ZoneInfo(policy.quota_timezone)

    def before_request(self) -> None:
        now = self._now()
        with InterProcessFileLock(self._lock_path):
            states = _load_states(self.path)
            state = self._state_for_today(states, now)
            _apply_before_request(state, self._policy, now)
            states[self._policy.provider] = state
            _persist_states(self.path, states)

    def record_success(self) -> None:
        now = self._now()
        with InterProcessFileLock(self._lock_path):
            states = _load_states(self.path)
            state = self._state_for_today(states, now)
            _apply_success(state)
            states[self._policy.provider] = state
            _persist_states(self.path, states)

    def record_failure(self, failure_code: str) -> None:
        if not failure_code.strip():
            raise ValueError("provider failure code is required")
        now = self._now()
        with InterProcessFileLock(self._lock_path):
            states = _load_states(self.path)
            state = self._state_for_today(states, now)
            _apply_failure(state, self._policy, failure_code, now)
            states[self._policy.provider] = state
            _persist_states(self.path, states)

    def snapshot(self) -> ProviderUsageSnapshot:
        now = self._now()
        with InterProcessFileLock(self._lock_path):
            states = _load_states(self.path)
            state = self._state_for_today(states, now)
            states[self._policy.provider] = state
            _persist_states(self.path, states)
            return state.snapshot(self._policy.provider)

    def _state_for_today(
        self,
        states: dict[str, _ProviderState],
        now: datetime,
    ) -> _ProviderState:
        quota_day = now.astimezone(self._timezone).date()
        state = states.get(self._policy.provider)
        if state is None:
            return _ProviderState(quota_day, self._policy.daily_request_budget)
        if state.quota_day != quota_day:
            state.rollover(quota_day, self._policy.daily_request_budget)
        else:
            state.daily_request_budget = self._policy.daily_request_budget
        return state

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("provider governance clock must be timezone-aware")
        return now


class RedisProviderRequestGovernor:
    """Coordinate provider usage across machines through Redis transactions."""

    def __init__(
        self,
        client: Redis[str],
        policy: ProviderGovernancePolicy,
        clock: Callable[[], datetime],
        *,
        key_prefix: str = "travel-agent",
        state_ttl_seconds: int = 90 * 24 * 60 * 60,
    ) -> None:
        if not key_prefix.strip():
            raise ValueError("provider Redis key prefix is required")
        if state_ttl_seconds <= 0:
            raise ValueError("provider Redis state TTL must be positive")
        self._client = client
        self._policy = policy
        self._clock = clock
        self._timezone = ZoneInfo(policy.quota_timezone)
        self._key = f"{key_prefix}:provider-governance:{policy.provider}"
        self._state_ttl_seconds = state_ttl_seconds

    @classmethod
    def from_url(
        cls,
        redis_url: str,
        policy: ProviderGovernancePolicy,
        clock: Callable[[], datetime],
        *,
        key_prefix: str = "travel-agent",
        state_ttl_seconds: int = 90 * 24 * 60 * 60,
    ) -> RedisProviderRequestGovernor:
        if not redis_url.strip():
            raise ValueError("provider Redis URL is required")
        client = Redis.from_url(redis_url, decode_responses=True)
        return cls(
            client,
            policy,
            clock,
            key_prefix=key_prefix,
            state_ttl_seconds=state_ttl_seconds,
        )

    def before_request(self) -> None:
        now = self._now()
        self._transact(
            now,
            lambda state: _apply_before_request(state, self._policy, now),
        )

    def record_success(self) -> None:
        now = self._now()
        self._transact(now, _apply_success)

    def record_failure(self, failure_code: str) -> None:
        if not failure_code.strip():
            raise ValueError("provider failure code is required")
        now = self._now()
        self._transact(
            now,
            lambda state: _apply_failure(
                state,
                self._policy,
                failure_code,
                now,
            ),
        )

    def snapshot(self) -> ProviderUsageSnapshot:
        now = self._now()
        return self._transact(
            now,
            lambda state: state.snapshot(self._policy.provider),
        )

    def _transact(
        self,
        now: datetime,
        operation: Callable[[_ProviderState], _T],
    ) -> _T:
        while True:
            with self._client.pipeline() as pipeline:
                try:
                    pipeline.watch(self._key)
                    state = self._state_for_today(
                        _load_redis_state(pipeline.get(self._key)),
                        now,
                    )
                    result = operation(state)
                    pipeline.multi()
                    pipeline.set(
                        self._key,
                        json.dumps(
                            state.to_dict(),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                        ex=self._state_ttl_seconds,
                    )
                    pipeline.execute()
                    return result
                except WatchError:
                    continue

    def _state_for_today(
        self,
        state: _ProviderState | None,
        now: datetime,
    ) -> _ProviderState:
        quota_day = now.astimezone(self._timezone).date()
        if state is None:
            return _ProviderState(quota_day, self._policy.daily_request_budget)
        if state.quota_day != quota_day:
            state.rollover(quota_day, self._policy.daily_request_budget)
        else:
            state.daily_request_budget = self._policy.daily_request_budget
        return state

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("provider governance clock must be timezone-aware")
        return now


def build_provider_request_governor(
    policy: ProviderGovernancePolicy,
    clock: Callable[[], datetime],
    *,
    json_path: str | Path,
    redis_url: str | None = None,
    redis_key_prefix: str = "travel-agent",
) -> ProviderRequestGovernor:
    if redis_url is not None and redis_url.strip():
        return RedisProviderRequestGovernor.from_url(
            redis_url,
            policy,
            clock,
            key_prefix=redis_key_prefix,
        )
    return JsonProviderRequestGovernor(json_path, policy, clock)


def read_provider_usage(path: str | Path) -> tuple[ProviderUsageSnapshot, ...]:
    state_path = Path(path)
    lock_path = state_path.with_suffix(state_path.suffix + ".lock")
    with InterProcessFileLock(lock_path):
        states = _load_states(state_path)
    return tuple(
        state.snapshot(provider)
        for provider, state in sorted(states.items())
    )


def read_redis_provider_usage(
    client: Redis[str],
    *,
    key_prefix: str = "travel-agent",
) -> tuple[ProviderUsageSnapshot, ...]:
    prefix = f"{key_prefix}:provider-governance:"
    snapshots: list[ProviderUsageSnapshot] = []
    for raw_key in client.scan_iter(match=f"{prefix}*"):
        key = _redis_text(raw_key)
        provider = key.removeprefix(prefix)
        state = _load_redis_state(client.get(key))
        if not provider or state is None:
            continue
        snapshots.append(state.snapshot(provider))
    return tuple(sorted(snapshots, key=lambda item: item.provider))


def _load_states(path: Path) -> dict[str, _ProviderState]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError
        raw_providers = payload.get("providers")
        if not isinstance(raw_providers, dict):
            raise ValueError
        return {
            provider: _parse_state(raw)
            for provider, raw in raw_providers.items()
            if isinstance(provider, str) and isinstance(raw, dict)
        }
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("provider governance state is invalid") from exc


def _parse_state(raw: Mapping[str, object]) -> _ProviderState:
    raw_failure_counts = raw.get("failure_counts")
    if not isinstance(raw_failure_counts, dict):
        raise ValueError
    failure_counts = {
        code: _integer(count)
        for code, count in raw_failure_counts.items()
        if isinstance(code, str)
    }
    return _ProviderState(
        quota_day=date.fromisoformat(_text(raw.get("quota_day"))),
        daily_request_budget=_integer(raw.get("daily_request_budget")),
        request_count=_integer(raw.get("request_count")),
        success_count=_integer(raw.get("success_count")),
        failure_count=_integer(raw.get("failure_count")),
        consecutive_failures=_integer(raw.get("consecutive_failures")),
        failure_counts=failure_counts,
        last_request_at=_optional_datetime(raw.get("last_request_at")),
        circuit_open_until=_optional_datetime(raw.get("circuit_open_until")),
    )


def _load_redis_state(raw: object) -> _ProviderState | None:
    if raw is None:
        return None
    try:
        payload = json.loads(_redis_text(raw))
        if not isinstance(payload, dict):
            raise ValueError
        return _parse_state(payload)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("provider Redis governance state is invalid") from exc


def _apply_before_request(
    state: _ProviderState,
    policy: ProviderGovernancePolicy,
    now: datetime,
) -> None:
    if state.circuit_open_until is not None:
        if now < state.circuit_open_until:
            raise ProviderRequestBlocked(
                ProviderBlockCode.CIRCUIT_OPEN,
                f"{policy.provider} provider circuit is open",
                retry_at=state.circuit_open_until,
            )
        state.circuit_open_until = None
        state.consecutive_failures = 0
    if state.last_request_at is not None:
        retry_at = state.last_request_at + timedelta(
            seconds=policy.minimum_interval_seconds
        )
        if now < retry_at:
            raise ProviderRequestBlocked(
                ProviderBlockCode.RATE_WINDOW,
                f"{policy.provider} provider request interval is active",
                retry_at=retry_at,
            )
    if state.request_count >= policy.daily_request_budget:
        raise ProviderRequestBlocked(
            ProviderBlockCode.DAILY_BUDGET_EXHAUSTED,
            f"{policy.provider} provider daily safety budget is exhausted",
        )
    state.request_count += 1
    state.last_request_at = now


def _apply_success(state: _ProviderState) -> None:
    state.success_count += 1
    state.consecutive_failures = 0
    state.circuit_open_until = None


def _apply_failure(
    state: _ProviderState,
    policy: ProviderGovernancePolicy,
    failure_code: str,
    now: datetime,
) -> None:
    state.failure_count += 1
    state.failure_counts[failure_code] = state.failure_counts.get(failure_code, 0) + 1
    if failure_code in policy.circuit_failure_codes:
        state.consecutive_failures += 1
    if (
        failure_code in policy.immediate_circuit_codes
        or state.consecutive_failures >= policy.consecutive_failure_threshold
    ):
        state.circuit_open_until = now + timedelta(
            seconds=policy.circuit_open_seconds
        )


def _persist_states(path: Path, states: Mapping[str, _ProviderState]) -> None:
    payload = {
        "schema_version": 1,
        "providers": {
            provider: state.to_dict()
            for provider, state in sorted(states.items())
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _text(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError
    return value


def _integer(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError
    return value


def _optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(_text(value))
    if parsed.tzinfo is None:
        raise ValueError
    return parsed


def _redis_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, str):
        return value
    raise ValueError("Redis value must be text")
