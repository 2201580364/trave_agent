"""Machine-readable P1 solver contract freeze.

Traceability: H3, Gate 6, ADR-0009.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .anchors import DEFAULT_DAY_END_MIN, DEFAULT_DAY_START_MIN
from .day_assignment import DEFAULT_DURATION_RATIO_BY_MODE
from .models import RejectionCode, RouteSearchStatus, TravelMode
from .routing import (
    DEFAULT_DROP_PENALTY,
    DEFAULT_PERIOD_DEVIATION_COST,
    DEFAULT_TIME_LIMIT_SECONDS,
    DEFAULT_TRAVEL_COST_SCALE,
)
from .schedule_refinement import (
    DEFAULT_DAY_SPREAD_MAX_DELAY_MIN,
    DEFAULT_DAY_SPREAD_TARGET_END_MIN,
    DEFAULT_LUNCH_DURATION_MIN,
    DEFAULT_LUNCH_EARLIEST_MIN,
    DEFAULT_LUNCH_LATEST_END_MIN,
)
from .segments import (
    DEFAULT_DINNER_DURATION_MIN,
    DEFAULT_DINNER_EARLIEST_MIN,
    DEFAULT_DINNER_LATEST_END_MIN,
    DEFAULT_EVENING_OPEN_MIN,
    REDUCED_DINNER_DURATION_MIN,
)
from .transport import DEFAULT_TRANSIT_BUFFER_RATIO

LEGACY_SOLVER_CONTRACT_VERSION = "solver-p1-v1"
SOLVER_CONTRACT_VERSION = "solver-p1-v2"
CONSTRAINT_VERSION = "constraints-p1-v2"
PARAMETER_VERSION = "parameters-p1-2026-08-25"


@dataclass(frozen=True, slots=True)
class SolverP1Contract:
    contract_version: str
    constraint_version: str
    parameter_version: str
    duration_ratios: tuple[tuple[str, float], ...]
    transit_buffer_ratio: float
    route_time_limit_seconds: int
    drop_penalty: int
    travel_cost_scale: int
    period_deviation_cost: int
    day_spread_target_end_min: int
    day_spread_max_delay_min: int
    lunch_earliest_min: int
    lunch_latest_end_min: int
    lunch_duration_min: int
    default_day_start_min: int
    default_day_end_min: int
    evening_start_min: int
    dinner_earliest_min: int
    dinner_latest_end_min: int
    dinner_full_duration_min: int
    dinner_reduced_duration_min: int
    time_buckets: tuple[tuple[str, int, int], ...]
    hard_constraints: tuple[str, ...]
    soft_objectives: tuple[str, ...]
    search_statuses: tuple[str, ...]
    rejection_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.contract_version or not self.parameter_version:
            raise ValueError("solver contract versions are required")
        if self.transit_buffer_ratio < 1:
            raise ValueError("solver contract transit buffer must be at least one")
        if self.route_time_limit_seconds <= 0 or self.drop_penalty <= 0:
            raise ValueError("solver contract routing parameters must be positive")
        if self.dinner_reduced_duration_min > self.dinner_full_duration_min:
            raise ValueError("reduced dinner duration cannot exceed full duration")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


DEFAULT_SOLVER_P1_CONTRACT = SolverP1Contract(
    contract_version=SOLVER_CONTRACT_VERSION,
    constraint_version=CONSTRAINT_VERSION,
    parameter_version=PARAMETER_VERSION,
    duration_ratios=tuple(
        (mode.value, DEFAULT_DURATION_RATIO_BY_MODE[mode])
        for mode in (TravelMode.SPEED, TravelMode.NORMAL, TravelMode.LEISURE)
    ),
    transit_buffer_ratio=DEFAULT_TRANSIT_BUFFER_RATIO,
    route_time_limit_seconds=DEFAULT_TIME_LIMIT_SECONDS,
    drop_penalty=DEFAULT_DROP_PENALTY,
    travel_cost_scale=DEFAULT_TRAVEL_COST_SCALE,
    period_deviation_cost=DEFAULT_PERIOD_DEVIATION_COST,
    day_spread_target_end_min=DEFAULT_DAY_SPREAD_TARGET_END_MIN,
    day_spread_max_delay_min=DEFAULT_DAY_SPREAD_MAX_DELAY_MIN,
    lunch_earliest_min=DEFAULT_LUNCH_EARLIEST_MIN,
    lunch_latest_end_min=DEFAULT_LUNCH_LATEST_END_MIN,
    lunch_duration_min=DEFAULT_LUNCH_DURATION_MIN,
    default_day_start_min=DEFAULT_DAY_START_MIN,
    default_day_end_min=DEFAULT_DAY_END_MIN,
    evening_start_min=DEFAULT_EVENING_OPEN_MIN,
    dinner_earliest_min=DEFAULT_DINNER_EARLIEST_MIN,
    dinner_latest_end_min=DEFAULT_DINNER_LATEST_END_MIN,
    dinner_full_duration_min=DEFAULT_DINNER_DURATION_MIN,
    dinner_reduced_duration_min=REDUCED_DINNER_DURATION_MIN,
    time_buckets=(
        ("morning", 0, 12 * 60 - 1),
        ("afternoon", 12 * 60, 17 * 60 - 1),
        ("evening", 17 * 60, 24 * 60 - 1),
    ),
    hard_constraints=("C1", "C2", "C4", "C5", "C6"),
    soft_objectives=(
        "S1_DURATION_RATIO",
        "S2_ENERGY_BALANCE",
        "VISIT_PERIOD",
        "DINNER_BLOCK",
        "LUNCH_BLOCK",
        "DAY_SPREAD",
    ),
    search_statuses=tuple(item.value for item in RouteSearchStatus),
    rejection_codes=tuple(item.value for item in RejectionCode),
)
