"""Build a versioned QWeather three-day forecast snapshot.

Live requests are opt-in. The API key is loaded from the local environment and
is never serialized or printed by this command.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from travel_agent.infrastructure.provider_governance import (  # noqa: E402
    ProviderBlockCode,
    ProviderGovernancePolicy,
    ProviderRequestBlocked,
    ProviderRequestGovernor,
    build_provider_request_governor,
)
from travel_agent.infrastructure.weather import (  # noqa: E402
    QWeatherForecastClient,
    QWeatherSettings,
    qweather_snapshot_content_hash,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a versioned QWeather three-day forecast snapshot.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-version", required=True)
    parser.add_argument("--city-id", default="hangzhou")
    parser.add_argument(
        "--governance-state",
        type=Path,
        default=PROJECT_ROOT / "var" / "ops" / "provider-governance.json",
        help="Credential-free shared quota and circuit-breaker state.",
    )
    parser.add_argument(
        "--request-interval-seconds",
        type=float,
        default=1.05,
        help="Minimum interval between live requests across local processes.",
    )
    parser.add_argument(
        "--execute-live",
        action="store_true",
        help="Acknowledge that this command will call the live QWeather API.",
    )
    args = parser.parse_args()

    if not args.execute_live:
        parser.error("live requests require the explicit --execute-live flag")
    if args.request_interval_seconds < 0:
        parser.error("--request-interval-seconds must be non-negative")

    settings = replace(
        QWeatherSettings.from_env(dotenv_path=PROJECT_ROOT / ".env"),
        data_version=args.data_version,
    )
    def clock() -> datetime:
        return datetime.now(UTC)

    redis_url = os.environ.get("TRAVEL_AGENT_PROVIDER_REDIS_URL", "").strip()
    redis_key_prefix = os.environ.get(
        "TRAVEL_AGENT_PROVIDER_REDIS_PREFIX",
        "travel-agent",
    ).strip()
    governor = build_provider_request_governor(
        ProviderGovernancePolicy(
            provider="qweather",
            daily_request_budget=_positive_env_int(
                "TRAVEL_AGENT_QWEATHER_DAILY_REQUEST_BUDGET",
                100,
            ),
            minimum_interval_seconds=args.request_interval_seconds,
            consecutive_failure_threshold=_positive_env_int(
                "TRAVEL_AGENT_PROVIDER_CIRCUIT_FAILURE_THRESHOLD",
                3,
            ),
            circuit_open_seconds=_positive_env_int(
                "TRAVEL_AGENT_PROVIDER_CIRCUIT_OPEN_SECONDS",
                300,
            ),
            circuit_failure_codes=frozenset(
                {
                    "timeout",
                    "rate_limited",
                    "http_error",
                    "api_error",
                    "invalid_response",
                }
            ),
        ),
        clock,
        json_path=args.governance_state,
        redis_url=redis_url,
        redis_key_prefix=redis_key_prefix,
    )
    client = QWeatherForecastClient(
        settings,
        clock,
        before_request=lambda: _wait_for_request_slot(governor),
        on_success=governor.record_success,
        on_failure=governor.record_failure,
    )
    snapshot = client.fetch_three_day(city_id=args.city_id).to_dict()
    payload = {
        "schema_version": "weather-snapshot-envelope-v1",
        "content_hash": qweather_snapshot_content_hash(snapshot),
        "snapshot": snapshot,
    }
    days = snapshot.get("days")
    if not isinstance(days, list):
        raise ValueError("QWeather snapshot days must be an array")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"QWeather snapshot: {args.data_version}")
    print(f"City: {args.city_id}")
    print(f"Location: {settings.location_id}")
    print(f"Forecast days: {len(days)}")
    usage = governor.snapshot()
    print(
        "Provider budget: "
        f"{usage.request_count}/{usage.daily_request_budget} "
        f"({usage.remaining_request_budget} remaining)"
    )
    print(f"Provider governance backend: {'redis' if redis_url else 'json'}")
    if not redis_url:
        print(f"Provider governance: {args.governance_state}")
    print(f"Report: {args.output}")
    return 0


def _wait_for_request_slot(governor: ProviderRequestGovernor) -> None:
    while True:
        try:
            governor.before_request()
            return
        except ProviderRequestBlocked as exc:
            if exc.code is not ProviderBlockCode.RATE_WINDOW or exc.retry_at is None:
                raise
            remaining = (exc.retry_at - datetime.now(UTC)).total_seconds()
            if remaining > 0:
                time.sleep(remaining)


def _positive_env_int(name: str, default: int) -> int:
    value = int(os.environ.get(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
