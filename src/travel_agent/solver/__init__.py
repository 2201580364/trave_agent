"""Deterministic itinerary solver primitives."""

from .anchors import resolve_day_time_bounds
from .availability import assign_attraction_date, assign_to_nearest_available_date, is_open_on
from .data_gate import filter_solver_inputs
from .models import (
    AnchorRejectionCode,
    ArrivalEvaluation,
    Attraction,
    DateAssignment,
    DayTimeBounds,
    DayTimeBoundsResolution,
    EffectiveTimeWindow,
    RejectedAttraction,
    RejectionCode,
    SolverInputBatch,
    TimeRule,
    TimeWindowResolution,
    TripTimeAnchors,
)
from .time_windows import evaluate_arrival, resolve_effective_window

__all__ = [
    "AnchorRejectionCode",
    "ArrivalEvaluation",
    "Attraction",
    "DateAssignment",
    "DayTimeBounds",
    "DayTimeBoundsResolution",
    "EffectiveTimeWindow",
    "RejectedAttraction",
    "RejectionCode",
    "SolverInputBatch",
    "TimeRule",
    "TimeWindowResolution",
    "TripTimeAnchors",
    "assign_attraction_date",
    "assign_to_nearest_available_date",
    "evaluate_arrival",
    "filter_solver_inputs",
    "is_open_on",
    "resolve_day_time_bounds",
    "resolve_effective_window",
]
