"""Run Gate 6 solver benchmarks and persist a machine-readable report."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import ortools

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from tests.performance.solver_benchmark import (  # noqa: E402
    BENCHMARK_CASES,
    run_benchmark,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/test/reports/gate6-performance-latest.json"),
    )
    args = parser.parse_args()
    results = tuple(
        run_benchmark(case, repetitions=args.repetitions) for case in BENCHMARK_CASES
    )
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "processor": platform.processor() or "unknown",
            "ortools": ortools.__version__,
        },
        "environment_note": (
            "Local deterministic synthetic benchmark; not concurrency/load testing."
        ),
        "implementation_note": "route_itinerary currently routes days sequentially.",
        "repetitions": args.repetitions,
        "gate_passed": all(result.gate_passed for result in results),
        "cases": [
            {
                "case_id": result.case.case_id,
                "attraction_count": result.case.attraction_count,
                "day_count": result.case.day_count,
                "threshold_seconds": result.case.threshold_seconds,
                "min_ms": result.min_ms,
                "mean_ms": result.mean_ms,
                "p50_ms": result.p50_ms,
                "p95_ms": result.p95_ms,
                "max_ms": result.max_ms,
                "deterministic": result.deterministic,
                "threshold_passed": result.threshold_passed,
                "quality_passed": result.quality_passed,
                "gate_passed": result.gate_passed,
                "samples": [
                    {
                        "step1_ms": sample.step1_ms,
                        "routing_ms": sample.routing_ms,
                        "quality_ms": sample.quality_ms,
                        "total_ms": sample.total_ms,
                        "scheduled_count": sample.scheduled_count,
                        "unplaced_count": sample.unplaced_count,
                        "hard_constraint_violations": (
                            sample.hard_constraint_violations
                        ),
                        "gate_passed": sample.gate_passed,
                    }
                    for sample in result.samples
                ],
            }
            for result in results
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for result in results:
        print(
            f"{result.case.case_id}: p95={result.p95_ms:.2f}ms, "
            f"max={result.max_ms:.2f}ms, passed={result.gate_passed}"
        )
    print(f"Report: {args.output}")
    return 0 if payload["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
