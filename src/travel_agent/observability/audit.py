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

    def to_dict(self) -> dict[str, object]:
        return {
            "attraction_id": self.attraction_id,
            "constraint": self.constraint,
            "outcome": self.outcome,
            "reason_code": self.reason_code,
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

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.hard_constraint_violations < 0:
            raise ValueError("hard_constraint_violations cannot be negative")
        if self.elapsed_ms < 0:
            raise ValueError("elapsed_ms cannot be negative")

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
        }

