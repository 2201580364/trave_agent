"""Executable Hangzhou closeness gate. Traceability: H3, Gate 6, ADR-0007."""

from travel_agent.solver import BaselineProvenance

from .hangzhou_closeness import run_hangzhou_closeness_case


def test_hangzhou_public_guide_closeness_case_passes() -> None:
    result = run_hangzhou_closeness_case()

    assert result.report.provenance is BaselineProvenance.PUBLIC_GUIDE_SYNTHESIS
    assert result.report.hard_gate_passed
    assert result.report.fixed_visit_score == 1
    assert result.report.overall_closeness >= result.report.threshold
    assert result.report.baseline_passed
    assert "not a domain-expert" in result.note
