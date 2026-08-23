"""Run Gate 6 itinerary-closeness evidence and persist a JSON report."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from tests.closeness.hangzhou_closeness import run_hangzhou_closeness_case  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/test/reports/gate6-closeness-latest.json"),
    )
    args = parser.parse_args()
    result = run_hangzhou_closeness_case()
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "suite": "hangzhou-public-guide-synthesis-closeness",
        "note": result.note,
        **asdict(result.report),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Closeness: {result.report.overall_closeness:.3f}")
    print(f"Baseline gate: {result.report.baseline_passed}")
    print(f"Report: {args.output}")
    return 0 if result.report.baseline_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
