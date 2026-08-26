"""Build a versioned directed OD snapshot through the Gaode Web API.

Live requests are opt-in. The API key is read by ``GaodeSettings.from_env``
and is never serialized or printed by this script.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from travel_agent.infrastructure.solver import (  # noqa: E402
    GaodeODSnapshotBuilder,
    GaodeRouteClient,
    GaodeSettings,
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
        "--allow-approximate-fallback",
        action="store_true",
        help="Fill failed Gaode pairs with explicitly labelled approximate OD.",
    )
    parser.add_argument(
        "--execute-live",
        action="store_true",
        help="Acknowledge that this command will call the live Gaode Web API.",
    )
    args = parser.parse_args()

    if not args.execute_live:
        parser.error("live requests require the explicit --execute-live flag")

    coordinates = _load_coordinates(args.input)
    settings = replace(GaodeSettings.from_env(), data_version=args.data_version)

    def clock() -> datetime:
        return datetime.now(UTC)

    client = GaodeRouteClient(settings, clock)
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
    print(f"Report: {args.output}")
    return 0 if built.report.complete else 2


def _load_coordinates(path: Path) -> dict[int, Coordinate]:
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
