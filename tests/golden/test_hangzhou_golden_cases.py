"""Executable Gate 6 regression entry point. Traceability: H2, H3, C1-C6."""

from collections.abc import Callable

import pytest

from .hangzhou_cases import CASES, GoldenCaseResult, run_hangzhou_golden_cases


@pytest.mark.parametrize("case", CASES, ids=lambda case: case().case_id)
def test_hangzhou_golden_case(case: Callable[[], GoldenCaseResult]) -> None:
    result = case()
    assert result.passed, result.details


def test_hangzhou_golden_cases_are_deterministic() -> None:
    assert run_hangzhou_golden_cases() == run_hangzhou_golden_cases()
