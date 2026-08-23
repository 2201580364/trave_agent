"""Automated Gate 6 performance thresholds. Traceability: H3, Gate 6."""

import pytest

from .solver_benchmark import BENCHMARK_CASES, BenchmarkCase, run_benchmark


@pytest.mark.parametrize("case", BENCHMARK_CASES, ids=lambda case: case.case_id)
def test_solver_scale_target(case: BenchmarkCase) -> None:
    result = run_benchmark(case, repetitions=2)

    assert result.quality_passed
    assert result.deterministic
    assert result.threshold_passed, {
        "threshold_seconds": case.threshold_seconds,
        "max_ms": result.max_ms,
    }
