"""Show credential-free provider quota and circuit-breaker state."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from redis import Redis

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from travel_agent.infrastructure.provider_governance import (  # noqa: E402
    read_provider_usage,
    read_redis_provider_usage,
)
from travel_agent.runtime_config import load_runtime_environment  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Show local third-party provider governance status.",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=PROJECT_ROOT / "var" / "ops" / "provider-governance.json",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    load_runtime_environment(PROJECT_ROOT / ".env")
    redis_url = os.environ.get("TRAVEL_AGENT_PROVIDER_REDIS_URL", "").strip()
    redis_key_prefix = os.environ.get(
        "TRAVEL_AGENT_PROVIDER_REDIS_PREFIX",
        "travel-agent",
    ).strip()
    if redis_url:
        snapshots = read_redis_provider_usage(
            Redis.from_url(redis_url, decode_responses=True),
            key_prefix=redis_key_prefix,
        )
        backend = "redis"
    else:
        snapshots = read_provider_usage(args.state)
        backend = "json"
    if args.json:
        print(
            json.dumps(
                {
                    "backend": backend,
                    "providers": [item.to_dict() for item in snapshots],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if not snapshots:
        print(f"No provider governance state has been recorded in {backend}.")
        return 0
    print(f"Backend: {backend}")
    for item in snapshots:
        circuit = item.circuit_open_until or "closed"
        print(
            f"{item.provider}: {item.request_count}/{item.daily_request_budget} "
            f"requests, {item.remaining_request_budget} remaining, "
            f"success={item.success_count}, failure={item.failure_count}, "
            f"circuit={circuit}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
