"""Pure domain models for solver decision audit records.

Traceability: H3, H7, ADR-0005 D4.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SolverRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class DecisionEvent:
    attraction_id: int
    constraint: str
    outcome: str
    reason_code: str | None = None
    visit_date: str | None = None
    from_date: str | None = None
    to_date: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "attraction_id": self.attraction_id,
            "constraint": self.constraint,
            "outcome": self.outcome,
            "reason_code": self.reason_code,
            "visit_date": self.visit_date,
            "from_date": self.from_date,
            "to_date": self.to_date,
        }


@dataclass(frozen=True, slots=True)
class SolverRunAudit:
    solve_run_id: str
    solver_version: str
    constraint_version: str
    parameter_version: str
    input_snapshot_hash: str
    data_snapshot_version: str
    od_basis: str
    weather_basis: str
    random_seed: int
    duration_ratio: float
    status: SolverRunStatus
    hard_constraint_violations: int
    elapsed_ms: int
    events: tuple[DecisionEvent, ...]
    created_at: datetime
    input_count: int = 0
    scheduled_count: int = 0
    unplaced_count: int = 0
    data_rejected_count: int = 0
    timed_out_day_count: int = 0
    best_so_far_day_count: int = 0
    no_solution_day_count: int = 0
    search_attempt_count: int = 0

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.hard_constraint_violations < 0:
            raise ValueError("hard_constraint_violations cannot be negative")
        if self.elapsed_ms < 0:
            raise ValueError("elapsed_ms cannot be negative")
        counts = (
            self.input_count,
            self.scheduled_count,
            self.unplaced_count,
            self.data_rejected_count,
            self.timed_out_day_count,
            self.best_so_far_day_count,
            self.no_solution_day_count,
            self.search_attempt_count,
        )
        if any(count < 0 for count in counts):
            raise ValueError("audit counts cannot be negative")

    def to_dict(self) -> dict[str, object]:
        return {
            "solve_run_id": self.solve_run_id,
            "solver_version": self.solver_version,
            "constraint_version": self.constraint_version,
            "parameter_version": self.parameter_version,
            "input_snapshot_hash": self.input_snapshot_hash,
            "data_snapshot_version": self.data_snapshot_version,
            "od_basis": self.od_basis,
            "weather_basis": self.weather_basis,
            "random_seed": self.random_seed,
            "duration_ratio": self.duration_ratio,
            "status": self.status.value,
            "hard_constraint_violations": self.hard_constraint_violations,
            "elapsed_ms": self.elapsed_ms,
            "events": [event.to_dict() for event in self.events],
            "created_at": self.created_at.isoformat(),
            "input_count": self.input_count,
            "scheduled_count": self.scheduled_count,
            "unplaced_count": self.unplaced_count,
            "data_rejected_count": self.data_rejected_count,
            "timed_out_day_count": self.timed_out_day_count,
            "best_so_far_day_count": self.best_so_far_day_count,
            "no_solution_day_count": self.no_solution_day_count,
            "search_attempt_count": self.search_attempt_count,
        }
