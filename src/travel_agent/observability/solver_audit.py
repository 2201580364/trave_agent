"""Pure conversion from solver output to ADR-0005 audit records.

Traceability: H3, H7, C1, C2, C4, C5, C6, ADR-0005 D4.
"""

from __future__ import annotations

from datetime import datetime

from travel_agent.solver import (
    ItineraryPlan,
    RouteSearchStatus,
    SolverQualityReport,
    constraint_name_for,
)

from .audit import DecisionEvent, SolverRunAudit, SolverRunStatus


def build_solver_run_audit(
    itinerary: ItineraryPlan,
    quality: SolverQualityReport,
    *,
    solve_run_id: str,
    solver_version: str,
    constraint_version: str,
    parameter_version: str,
    input_snapshot_hash: str,
    data_snapshot_version: str,
    od_basis: str,
    weather_basis: str,
    random_seed: int,
    duration_ratio: float,
    elapsed_ms: int,
    created_at: datetime,
) -> SolverRunAudit:
    """Build a deterministic audit payload without writing logs or storage."""

    events: list[DecisionEvent] = []
    for day in itinerary.days:
        for visit in day.visits:
            events.append(
                DecisionEvent(
                    visit.attraction.id,
                    "solver",
                    "assigned",
                    visit_date=day.visit_date.isoformat(),
                )
            )
    for reassignment in itinerary.reassignments:
        events.append(
            DecisionEvent(
                reassignment.attraction.id,
                "solver",
                "reassigned",
                from_date=reassignment.from_date.isoformat(),
                to_date=reassignment.to_date.isoformat(),
            )
        )
    for item in itinerary.unplaced:
        events.append(
            DecisionEvent(
                item.attraction.id,
                constraint_name_for(item.rejection_code).value,
                "unplaced",
                item.rejection_code.value,
            )
        )
    for item in itinerary.data_rejected:
        events.append(
            DecisionEvent(
                item.attraction.id,
                "DATA_GATE",
                "rejected",
                item.code.value,
            )
        )
    for day, validation in zip(itinerary.days, itinerary.validations, strict=True):
        for violation in validation.violations:
            events.append(
                DecisionEvent(
                    violation.attraction_id or 0,
                    constraint_name_for(violation.code).value,
                    "hard_violation",
                    violation.code.value,
                    visit_date=day.visit_date.isoformat(),
                )
            )
    for attempt in itinerary.search_attempts:
        if attempt.metadata.status in {
            RouteSearchStatus.COMPLETED,
            RouteSearchStatus.EMPTY,
        }:
            continue
        events.append(
            DecisionEvent(
                0,
                "SOLVER_SEARCH",
                attempt.metadata.status.value,
                attempt.phase.value,
                visit_date=attempt.visit_date.isoformat(),
            )
        )

    accounting = quality.accounting
    return SolverRunAudit(
        solve_run_id=solve_run_id,
        solver_version=solver_version,
        constraint_version=constraint_version,
        parameter_version=parameter_version,
        input_snapshot_hash=input_snapshot_hash,
        data_snapshot_version=data_snapshot_version,
        od_basis=od_basis,
        weather_basis=weather_basis,
        random_seed=random_seed,
        duration_ratio=duration_ratio,
        status=(
            SolverRunStatus.COMPLETED
            if quality.gate_passed
            else SolverRunStatus.FAILED
        ),
        hard_constraint_violations=quality.hard_constraint_violations,
        elapsed_ms=elapsed_ms,
        events=tuple(events),
        created_at=created_at,
        input_count=accounting.input_count,
        scheduled_count=accounting.scheduled_count,
        unplaced_count=accounting.unplaced_count,
        data_rejected_count=accounting.data_rejected_count,
        timed_out_day_count=itinerary.timed_out_day_count,
        best_so_far_day_count=itinerary.best_so_far_day_count,
        no_solution_day_count=itinerary.no_solution_day_count,
        search_attempt_count=len(itinerary.search_attempts),
    )
