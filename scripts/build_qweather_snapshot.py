"""Build a versioned QWeather three-day forecast snapshot.

Live requests are opt-in. The API key is loaded from the local environment and
is never serialized or printed by this command.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

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
        "--execute-live",
        action="store_true",
        help="Acknowledge that this command will call the live QWeather API.",
    )
    args = parser.parse_args()

    if not args.execute_live:
        parser.error("live requests require the explicit --execute-live flag")

    settings = replace(
        QWeatherSettings.from_env(dotenv_path=PROJECT_ROOT / ".env"),
        data_version=args.data_version,
    )
    client = QWeatherForecastClient(settings, lambda: datetime.now(UTC))
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
    print(f"Report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
