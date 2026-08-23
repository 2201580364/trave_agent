"""Itinerary-level accounting and hard-constraint quality gate.

Traceability: H3, C1, C2, C4, C5, C6, Gate 5, Gate 6, ADR-0005.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from .models import Attraction, ItineraryPlan, RejectionCode


class ConstraintName(StrEnum):
    C1 = "C1"
    C2 = "C2"
    C4 = "C4"
    C5 = "C5"
    C6 = "C6"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class ConstraintCount:
    constraint: ConstraintName
    count: int


@dataclass(frozen=True, slots=True)
class ItineraryAccounting:
    input_count: int
    scheduled_count: int
    unplaced_count: int
    data_rejected_count: int
    missing_ids: tuple[int, ...]
    duplicate_ids: tuple[int, ...]
    unexpected_ids: tuple[int, ...]
    conserved: bool


@dataclass(frozen=True, slots=True)
class SolverQualityReport:
    accounting: ItineraryAccounting
    hard_constraint_counts: tuple[ConstraintCount, ...]
    hard_constraint_violations: int
    gate_passed: bool

    def __post_init__(self) -> None:
        if self.hard_constraint_violations != sum(
            item.count for item in self.hard_constraint_counts
        ):
            raise ValueError("hard constraint total does not match per-constraint counts")
        expected = self.accounting.conserved and self.hard_constraint_violations == 0
        if self.gate_passed != expected:
            raise ValueError("quality gate result is inconsistent")


def evaluate_solver_quality(
    itinerary: ItineraryPlan,
    input_attractions: Iterable[Attraction],
) -> SolverQualityReport:
    """Prove attraction conservation and count final C1/C2/C4/C5/C6 violations."""

    inputs = tuple(input_attractions)
    input_ids = [item.id for item in inputs]
    if len(set(input_ids)) != len(input_ids):
        raise ValueError("input attraction ids must be unique")

    scheduled_ids = [
        visit.attraction.id for day in itinerary.days for visit in day.visits
    ]
    unplaced_ids = [item.attraction.id for item in itinerary.unplaced]
    rejected_ids = [item.attraction.id for item in itinerary.data_rejected]
    outcome_ids = (*scheduled_ids, *unplaced_ids, *rejected_ids)
    outcome_counts = Counter(outcome_ids)
    input_id_set = set(input_ids)
    outcome_id_set = set(outcome_ids)
    missing_ids = tuple(sorted(input_id_set - outcome_id_set))
    unexpected_ids = tuple(sorted(outcome_id_set - input_id_set))
    duplicate_ids = tuple(
        sorted(attraction_id for attraction_id, count in outcome_counts.items() if count > 1)
    )
    conserved = not missing_ids and not unexpected_ids and not duplicate_ids
    accounting = ItineraryAccounting(
        len(input_ids),
        len(scheduled_ids),
        len(unplaced_ids),
        len(rejected_ids),
        missing_ids,
        duplicate_ids,
        unexpected_ids,
        conserved,
    )

    counts = Counter(
        _constraint_for(violation.code)
        for validation in itinerary.validations
        for violation in validation.violations
    )
    constraint_counts = tuple(
        ConstraintCount(name, counts[name])
        for name in (
            ConstraintName.C1,
            ConstraintName.C2,
            ConstraintName.C4,
            ConstraintName.C5,
            ConstraintName.C6,
            ConstraintName.OTHER,
        )
    )
    hard_total = sum(item.count for item in constraint_counts)
    return SolverQualityReport(
        accounting,
        constraint_counts,
        hard_total,
        accounting.conserved and hard_total == 0,
    )


def constraint_name_for(code: RejectionCode) -> ConstraintName:
    """Expose the stable C-x mapping for audit and reports."""

    return _constraint_for(code)


def _constraint_for(code: RejectionCode) -> ConstraintName:
    mapping = {
        RejectionCode.CLOSED_ON_DATE: ConstraintName.C1,
        RejectionCode.NO_MATCHING_TIME_RULE: ConstraintName.C2,
        RejectionCode.TIME_RULE_CONFLICT: ConstraintName.C2,
        RejectionCode.ARRIVAL_AFTER_LATEST_ARRIVAL: ConstraintName.C2,
        RejectionCode.VISIT_DURATION_INSUFFICIENT: ConstraintName.C2,
        RejectionCode.EMPTY_DAY_WINDOW: ConstraintName.C4,
        RejectionCode.ANCHOR_VIOLATION: ConstraintName.C4,
        RejectionCode.EXTREME_WEATHER_OUTDOOR: ConstraintName.C5,
        RejectionCode.WEATHER_DATA_MISSING: ConstraintName.C5,
        RejectionCode.OD_DATA_MISSING: ConstraintName.C6,
        RejectionCode.TRANSIT_INFEASIBLE: ConstraintName.C6,
    }
    return mapping.get(code, ConstraintName.OTHER)
