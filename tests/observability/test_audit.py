"""Solver audit model tests. Traceability: H3, ADR-0005."""

from datetime import UTC, datetime

from travel_agent.observability import DecisionEvent, SolverRunAudit, SolverRunStatus


def test_solver_audit_serializes_reproducible_decision_context() -> None:
    audit = SolverRunAudit(
        solve_run_id="solve-1",
        solver_version="0.1.0",
        constraint_version="ADR-0004",
        parameter_version="p1-defaults-v1",
        input_snapshot_hash="sha256:abc",
        data_snapshot_version="hangzhou-2026-08-22",
        od_basis="approximate",
        weather_basis="forecast",
        random_seed=42,
        duration_ratio=0.6,
        status=SolverRunStatus.COMPLETED,
        hard_constraint_violations=0,
        elapsed_ms=15,
        events=(
            DecisionEvent(
                attraction_id=5,
                constraint="C1",
                outcome="reassigned",
                reason_code="CLOSED_ON_DATE",
            ),
        ),
        created_at=datetime(2026, 8, 22, 8, 0, tzinfo=UTC),
    )

    payload = audit.to_dict()

    assert payload["solve_run_id"] == "solve-1"
    assert payload["status"] == "completed"
    assert payload["events"][0]["constraint"] == "C1"
    assert payload["created_at"] == "2026-08-22T08:00:00+00:00"

