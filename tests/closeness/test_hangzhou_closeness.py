"""Executable Hangzhou closeness gate. Traceability: H3, Gate 6, ADR-0007."""

from travel_agent.solver import BaselineProvenance, ExpectationOutcome

from .hangzhou_closeness import run_hangzhou_closeness_case


def test_hangzhou_public_guide_closeness_case_passes() -> None:
    result = run_hangzhou_closeness_case()

    assert result.report.provenance is BaselineProvenance.PUBLIC_GUIDE_SYNTHESIS
    assert result.report.hard_gate_passed
    assert result.report.fixed_visit_score == 1
    assert result.report.overall_closeness >= result.report.threshold
    assert result.report.baseline_passed
    assert "not a domain-expert" in result.note
    river_street_bucket = next(
        item
        for item in result.report.expectation_outcomes
        if item.component == "time_bucket" and item.attraction_ids == (16,)
    )
    assert river_street_bucket.actual_values == ("morning",)
    assert river_street_bucket.outcome is ExpectationOutcome.MISSED
