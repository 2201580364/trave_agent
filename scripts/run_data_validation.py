"""Validate a raw attraction snapshot and persist the Gate 6 report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from travel_agent.solver import GeoBounds, validate_attraction_data  # noqa: E402


HANGZHOU_BOUNDS = GeoBounds(29.1, 30.6, 118.3, 120.8)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("tests/data/hangzhou_attractions_snapshot.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/test/reports/gate6-data-validation-latest.json"),
    )
    parser.add_argument("--target-date", type=date.fromisoformat, default=date(2026, 8, 25))
    args = parser.parse_args()

    source = json.loads(args.input.read_text(encoding="utf-8"))
    validations = [
        validate_attraction_data(
            record,
            target_date=args.target_date,
            city_bounds=HANGZHOU_BOUNDS,
        )
        for record in source["records"]
    ]
    rule_totals = {
        str(rule_number): sum(
            validation.rules[rule_number - 1].passed for validation in validations
        )
        for rule_number in range(1, 10)
    }
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "input": str(args.input),
        "target_date": args.target_date.isoformat(),
        "record_count": len(validations),
        "structurally_valid_count": sum(item.structurally_valid for item in validations),
        "solver_eligible_count": sum(item.solver_eligible for item in validations),
        "rule_pass_counts": rule_totals,
        "gate_passed": all(item.solver_eligible for item in validations),
        "records": [
            {
                "attraction_id": validation.attraction_id,
                "structurally_valid": validation.structurally_valid,
                "solver_eligible": validation.solver_eligible,
                "rules": [
                    {
                        "rule": int(result.rule),
                        "passed": result.passed,
                        "errors": list(result.errors),
                    }
                    for result in validation.rules
                ],
            }
            for validation in validations
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "Data validation: "
        f"{payload['solver_eligible_count']}/{payload['record_count']} eligible"
    )
    print(f"Report: {args.output}")
    return 0 if payload["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
