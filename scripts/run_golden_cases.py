"""Run Gate 6 Golden Cases and persist a machine-readable report."""

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

from tests.golden.hangzhou_cases import run_hangzhou_golden_cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/test/reports/gate6-golden-latest.json"),
    )
    args = parser.parse_args()
    results = run_hangzhou_golden_cases()
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "suite": "hangzhou-realistic-golden-cases",
        "passed": sum(result.passed for result in results),
        "total": len(results),
        "gate_passed": all(result.passed for result in results),
        "cases": [asdict(result) for result in results],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Golden Cases: {payload['passed']}/{payload['total']} passed")
    print(f"Report: {args.output}")
    return 0 if payload["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
