"""Run Gate 6 degradation cases and persist a machine-readable report."""

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

from tests.degradation.degradation_cases import run_degradation_cases  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/test/reports/gate6-degradation-latest.json"),
    )
    args = parser.parse_args()
    results = run_degradation_cases()
    case_suite_passed = all(item.passed for item in results)
    timeout_case_ids = {"DEG-07", "DEG-08"}
    timeout_cases_passed = all(
        item.passed for item in results if item.case_id in timeout_case_ids
    ) and timeout_case_ids.issubset({item.case_id for item in results})
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "passed": sum(item.passed for item in results),
        "total": len(results),
        "case_suite_passed": case_suite_passed,
        "gate_passed": case_suite_passed and timeout_cases_passed,
        "timeout_best_so_far": {
            "status": "passed" if timeout_cases_passed else "failed",
            "evidence": ["DEG-07", "DEG-08"],
        },
        "cases": [asdict(item) for item in results],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Degradation cases: {payload['passed']}/{payload['total']} passed")
    print(f"Timeout best-so-far: {payload['timeout_best_so_far']['status']}")
    print(f"Complete degradation gate: {payload['gate_passed']}")
    print(f"Report: {args.output}")
    return 0 if case_suite_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
