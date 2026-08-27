"""Combine attraction, coordinate and real OD files into an audit-only snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from travel_agent.infrastructure.solver import (  # noqa: E402
    published_snapshot_content_hash,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a candidate, never-production, solver snapshot.",
    )
    parser.add_argument("--attractions", type=Path, required=True)
    parser.add_argument("--coordinates", type=Path, required=True)
    parser.add_argument("--od", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--weather-start", type=date.fromisoformat, required=True)
    parser.add_argument("--weather-end", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--acknowledge-audit-weather",
        action="store_true",
        help="Acknowledge that generated normal weather is not a live forecast.",
    )
    args = parser.parse_args()
    if not args.acknowledge_audit_weather:
        parser.error("candidate snapshots require --acknowledge-audit-weather")
    if args.weather_end < args.weather_start:
        parser.error("weather end must not precede weather start")

    snapshot = build_candidate_snapshot(
        _read_json(args.attractions),
        _read_json(args.coordinates),
        _read_json(args.od),
        version=args.version,
        weather_start=args.weather_start,
        weather_end=args.weather_end,
    )
    payload = {
        "schema_version": "published-solver-data-v1",
        "content_hash": published_snapshot_content_hash(snapshot),
        "snapshot": snapshot,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Candidate solver snapshot: {args.version}")
    print(f"Attractions: {len(snapshot['attractions'])}")
    print(f"OD pairs: {len(snapshot['od_pairs'])}")
    print("Weather basis: audit_normal_fixture")
    print(f"Report: {args.output}")
    return 0


def build_candidate_snapshot(
    attractions_payload: dict[str, object],
    coordinates_payload: dict[str, object],
    od_payload: dict[str, object],
    *,
    version: str,
    weather_start: date,
    weather_end: date,
) -> dict[str, object]:
    attraction_rows = _records(attractions_payload)
    coordinate_rows = {int(row["id"]): row for row in _records(coordinates_payload)}
    coordinate_fetched_at = coordinates_payload.get("generated_on")
    if not isinstance(coordinate_fetched_at, str) or not coordinate_fetched_at:
        raise ValueError("coordinate candidates must declare generated_on")
    od_rows = od_payload.get("pairs")
    if not isinstance(od_rows, list):
        raise ValueError("OD snapshot must contain pairs")
    report = od_payload.get("report")
    if not isinstance(report, dict) or report.get("missing_pair_count") != 0:
        raise ValueError("candidate solver snapshot requires complete OD")
    if report.get("fallback_pair_count") != 0:
        raise ValueError("candidate solver snapshot does not accept fallback OD")

    attractions = []
    for row in attraction_rows:
        attraction_id = int(row["id"])
        coordinate = coordinate_rows.get(attraction_id)
        if coordinate is None:
            raise ValueError(f"missing candidate coordinate: {attraction_id}")
        attractions.append(
            {
                "external_id": f"attr_{attraction_id}",
                "id": attraction_id,
                "name": row["name"],
                "close_days": row.get("close_days", []),
                "open_on_dates": row.get("open_on_dates", []),
                "closed_on_dates": row.get("closed_on_dates", []),
                "suggested_duration": row["suggested_duration"],
                "time_rules": row.get("time_rules", []),
                "is_always_open": row["is_always_open"],
                "is_indoor": row["is_indoor"],
                "energy_level": row["energy_level"],
                "data_verified": row["data_verified"],
                "conflict": row.get("conflict", False),
                "active": row.get("active", True),
                "coordinate": {
                    "lat": coordinate["lat"],
                    "lng": coordinate["lng"],
                    "gaode_poi_id": coordinate["gaode_poi_id"],
                    "point_kind": coordinate["routing_point_kind"],
                    "source": "gaode_web_service_v3",
                    "fetched_at": coordinate_fetched_at,
                    "review_status": coordinate["coordinate_review_status"],
                },
            }
        )
    if set(coordinate_rows) != {int(row["id"]) for row in attraction_rows}:
        raise ValueError("candidate coordinate and attraction ids must match")

    weather = []
    current = weather_start
    while current <= weather_end:
        weather.append(
            {
                "date": current.isoformat(),
                "basis": "climate",
                "severity": "normal",
                "condition": "audit-normal-fixture-not-live-weather",
            }
        )
        current += timedelta(days=1)
    return {
        "version": version,
        "status": "candidate",
        "city_id": "hangzhou",
        "od_version": od_payload["data_version"],
        "od_basis": "gaode",
        "weather_basis": "audit_normal_fixture",
        "attractions": attractions,
        "weather": weather,
        "od_pairs": od_rows,
    }


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON input must be an object: {path}")
    return payload


def _records(payload: dict[str, object]) -> list[dict[str, object]]:
    rows = payload.get("records")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("input must contain object records")
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
