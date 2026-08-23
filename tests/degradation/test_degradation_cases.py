"""Automated Gate 6 degradation suite. Traceability: H3, S6, C1-C6."""

from collections.abc import Callable

import pytest

from .degradation_cases import CASES, DegradationCaseResult


@pytest.mark.parametrize("case", CASES, ids=lambda case: case().case_id)
def test_safe_degradation(case: Callable[[], DegradationCaseResult]) -> None:
    result = case()
    assert result.passed, result.details
