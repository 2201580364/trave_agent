"""Build a versioned directed OD snapshot through the Gaode Web API.

Live requests are opt-in. The API key is read by ``GaodeSettings.from_env``
and is never serialized or printed by this script.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, replace
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
from travel_agent.infrastructure.solver import (  # noqa: E402
    GaodeODSnapshotBuilder,
    GaodeRouteClient,
    GaodeSettings,
    JsonFileGaodeRouteCache,
    RedisGaodeRouteCache,
)
from travel_agent.solver import (  # noqa: E402
    ApproximateTravelTimeProvider,
    Coordinate,
    TravelTimeProvider,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a versioned Gaode directed OD snapshot.",
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-version", required=True)
    parser.add_argument(
        "--cache",
        type=Path,
        default=PROJECT_ROOT / "var" / "cache" / "gaode-routes.json",
        help="Persistent credential-free route cache used across snapshot builds.",
    )
    parser.add_argument(
        "--request-interval-seconds",
        type=float,
        default=1.05,
        help="Minimum interval between live cache-miss requests; defaults to 1.05s.",
    )
    parser.add_argument(
        "--governance-state",
        type=Path,
        default=PROJECT_ROOT / "var" / "ops" / "provider-governance.json",
        help="Credential-free shared quota and circuit-breaker state.",
    )
    parser.add_argument(
        "--allow-approximate-fallback",
        action="store_true",
        help="Fill failed Gaode pairs with explicitly labelled approximate OD.",
    )
    parser.add_argument(
        "--allow-coordinate-candidates",
        action="store_true",
        help="Allow explicitly pending coordinate candidates for non-production audit builds.",
    )
    parser.add_argument(
        "--execute-live",
        action="store_true",
        help="Acknowledge that this command will call the live Gaode Web API.",
    )
    args = parser.parse_args()

    if not args.execute_live:
        parser.error("live requests require the explicit --execute-live flag")
    if args.request_interval_seconds < 0:
        parser.error("--request-interval-seconds must be non-negative")

    coordinates = _load_coordinates(
        args.input,
        allow_coordinate_candidates=args.allow_coordinate_candidates,
    )
    settings = replace(
        GaodeSettings.from_env(dotenv_path=PROJECT_ROOT / ".env"),
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
            provider="gaode",
            daily_request_budget=_positive_env_int(
                "TRAVEL_AGENT_GAODE_DAILY_REQUEST_BUDGET",
                1_000,
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
    route_cache = (
        RedisGaodeRouteCache.from_url(
            redis_url,
            key_prefix=redis_key_prefix,
        )
        if redis_url
        else JsonFileGaodeRouteCache(args.cache)
    )
    client = GaodeRouteClient(
        settings,
        clock,
        cache=route_cache,
        before_request=lambda: _wait_for_request_slot(governor),
        on_success=governor.record_success,
        on_failure=governor.record_failure,
    )
    fallback = None
    if args.allow_approximate_fallback:
        fallback = ApproximateTravelTimeProvider(
            coordinates,
            speed_kmh=18,
            detour_ratio=1.6,
            minimum_travel_min=5,
            data_version=f"{args.data_version}-approximate-fallback",
            fetched_at=clock(),
        )

    built = GaodeODSnapshotBuilder(settings, client).build(
        coordinates,
        fallback=fallback,
    )
    payload = {
        "schema_version": "gaode-od-snapshot-v1",
        "data_version": args.data_version,
        "generated_at": clock().isoformat(),
        "city_code": settings.city_code,
        "enabled_modes": [mode.value for mode in settings.enabled_modes],
        "report": asdict(built.report),
        "pairs": _serialize_pairs(coordinates, built.provider),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Gaode OD snapshot: {args.data_version}")
    print(f"Pairs: {built.report.requested_pair_count}")
    print(f"Gaode: {built.report.gaode_pair_count}")
    print(f"Approximate fallback: {built.report.fallback_pair_count}")
    print(f"Missing: {built.report.missing_pair_count}")
    print(f"Mode failures: {len(built.report.failure_details)}")
    print(f"Cache backend: {'redis' if redis_url else 'json'}")
    if not redis_url:
        print(f"Cache: {args.cache}")
    print(f"Request interval: {args.request_interval_seconds:.2f}s")
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
    return 0 if built.report.complete else 2


def _wait_for_request_slot(governor: ProviderRequestGovernor) -> None:
    """Wait only for the shared short rate window; propagate hard governance blocks."""

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


def _load_coordinates(
    path: Path,
    *,
    allow_coordinate_candidates: bool = False,
) -> dict[int, Coordinate]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    records = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        raise ValueError("input must contain a records array")

    coordinates: dict[int, Coordinate] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("each attraction record must be an object")
        if (
            record.get("data_verified") is not True
            or record.get("conflict") is True
            or record.get("active", True) is not True
        ):
            raise ValueError("all snapshot records must pass the publication data gate")
        coordinate_review_status = record.get("coordinate_review_status")
        if (
            coordinate_review_status is not None
            and coordinate_review_status != "human_verified"
            and not allow_coordinate_candidates
        ):
            raise ValueError(
                "coordinate candidates require --allow-coordinate-candidates"
            )
        try:
            attraction_id = int(record["id"])
            coordinate = Coordinate(float(record["lat"]), float(record["lng"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("each record requires a valid id, lat and lng") from exc
        if attraction_id in coordinates:
            raise ValueError(f"duplicate attraction id: {attraction_id}")
        coordinates[attraction_id] = coordinate

    if len(coordinates) < 2:
        raise ValueError("at least two published attraction coordinates are required")
    return coordinates


def _serialize_pairs(
    coordinates: dict[int, Coordinate],
    provider: TravelTimeProvider,
) -> list[dict[str, object]]:
    pairs: list[dict[str, object]] = []
    for origin_id in sorted(coordinates):
        for destination_id in sorted(coordinates):
            if origin_id == destination_id:
                continue
            result = provider.get_travel_time(origin_id, destination_id)
            if result is None:
                pairs.append(
                    {
                        "origin_id": origin_id,
                        "destination_id": destination_id,
                        "status": "missing",
                    }
                )
                continue
            pairs.append(
                {
                    "origin_id": origin_id,
                    "destination_id": destination_id,
                    "status": "available",
                    "travel_min": result.travel_min,
                    "travel_mode": (
                        result.travel_mode.value
                        if result.travel_mode is not None
                        else None
                    ),
                    "distance_m": result.distance_m,
                    "basis": result.basis.value,
                    "data_version": result.data_version,
                    "fetched_at": result.fetched_at.isoformat(),
                    "fallback_reason": result.fallback_reason,
                }
            )
    return pairs


if __name__ == "__main__":
    raise SystemExit(main())
