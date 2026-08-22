"""Availability-aware, capacity-safe deterministic day assignment.

Traceability: H2, H3, C1, C2, C4, C5, S2, ADR-0002, ADR-0003, ADR-0004.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date

from .anchors import resolve_day_time_bounds
from .availability import is_open_on
from .data_gate import filter_solver_inputs
from .models import (
    Attraction,
    AttractionPreference,
    DailyWeather,
    DateRejection,
    DayAllocation,
    DayPlan,
    DayTimeBounds,
    PaceLevel,
    RejectionCode,
    Step1Plan,
    TravelMode,
    TripTimeAnchors,
    UnplacedAttraction,
)
from .time_windows import DEFAULT_DURATION_RATIO, resolve_effective_window
from .weather import evaluate_weather_availability


@dataclass(slots=True)
class _DayState:
    visit_date: date
    bounds: DayTimeBounds
    allocations: list[DayAllocation]
    used_duration_min: int = 0
    energy_total: int = 0

    @property
    def capacity_min(self) -> int:
        return self.bounds.end_min - self.bounds.start_min


def assign_days(
    preferences: Iterable[AttractionPreference],
    *,
    trip_dates: Iterable[date],
    weather_by_date: Mapping[date, DailyWeather],
    anchors: TripTimeAnchors,
    travel_mode: TravelMode = TravelMode.NORMAL,
    duration_ratio: float | None = None,
) -> Step1Plan:
    """Run the Step 1 data gate and assign every eligible attraction or reject it.

    Capacity uses the minimum visit duration accepted by C2. OD travel is not
    estimated here because sequence-dependent travel belongs to Step 2; C6 is
    enforced when the ordered route is built and during final validation.
    """

    ordered_dates = tuple(sorted(set(trip_dates)))
    if not ordered_dates:
        raise ValueError("trip_dates must not be empty")
    if set(weather_by_date).difference(ordered_dates):
        raise ValueError("weather dates must be within trip_dates")

    preferences_by_id: dict[int, AttractionPreference] = {}
    ordered_preferences: list[AttractionPreference] = []
    for preference in preferences:
        attraction_id = preference.attraction.id
        if attraction_id in preferences_by_id:
            raise ValueError(f"duplicate attraction id: {attraction_id}")
        if preference.preferred_date not in ordered_dates:
            raise ValueError("preferred_date must be within trip_dates")
        preferences_by_id[attraction_id] = preference
        ordered_preferences.append(preference)

    gate = filter_solver_inputs(item.attraction for item in ordered_preferences)
    eligible_ids = {item.id for item in gate.eligible}
    ratio = duration_ratio if duration_ratio is not None else _duration_ratio(travel_mode)
    if not 0 < ratio <= 1:
        raise ValueError("duration_ratio must be within (0, 1]")

    states: dict[date, _DayState] = {}
    unavailable_days: set[date] = set()
    for day_index, visit_date in enumerate(ordered_dates, start=1):
        resolution = resolve_day_time_bounds(
            day_index=day_index,
            total_days=len(ordered_dates),
            anchors=anchors,
        )
        if resolution.bounds is None:
            unavailable_days.add(visit_date)
        else:
            states[visit_date] = _DayState(visit_date, resolution.bounds, [])

    unplaced: list[UnplacedAttraction] = []
    eligible_preferences = [
        item for item in ordered_preferences if item.attraction.id in eligible_ids
    ]
    eligible_preferences.sort(key=lambda item: (-item.attraction.energy_level, item.attraction.id))

    for preference in eligible_preferences:
        attraction = preference.attraction
        required_duration = math.ceil(attraction.suggested_duration * ratio)
        date_rejections: list[DateRejection] = []
        candidates: list[_DayState] = []

        for visit_date in ordered_dates:
            reasons = _date_rejection_reasons(
                attraction,
                visit_date,
                weather_by_date,
                states.get(visit_date),
                required_duration,
                ratio,
            )
            if reasons:
                date_rejections.append(DateRejection(visit_date, tuple(reasons)))
            else:
                candidates.append(states[visit_date])

        if not candidates:
            rejection_code = _overall_rejection_code(date_rejections, unavailable_days)
            unplaced.append(
                UnplacedAttraction(
                    attraction,
                    preference.preferred_date,
                    rejection_code,
                    tuple(date_rejections),
                )
            )
            continue

        selected = min(
            candidates,
            key=lambda state: _candidate_key(
                state,
                preference,
                required_duration,
                travel_mode,
            ),
        )
        allocation = DayAllocation(
            attraction,
            preference.preferred_date,
            selected.visit_date,
            required_duration,
        )
        selected.allocations.append(allocation)
        selected.used_duration_min += required_duration
        selected.energy_total += attraction.energy_level

    days = tuple(
        _build_day_plan(states[visit_date], travel_mode)
        for visit_date in ordered_dates
        if visit_date in states
    )
    return Step1Plan(days, tuple(unplaced), gate.rejected, travel_mode)


def rebuild_day_plan(
    base: DayPlan,
    allocations: Iterable[DayAllocation],
    travel_mode: TravelMode,
) -> DayPlan:
    """Recompute derived day totals after a cross-day reassignment."""

    allocation_list = list(allocations)
    state = _DayState(
        base.visit_date,
        base.bounds,
        allocation_list,
        sum(item.required_duration_min for item in allocation_list),
        sum(item.attraction.energy_level for item in allocation_list),
    )
    return _build_day_plan(state, travel_mode)


def _date_rejection_reasons(
    attraction: Attraction,
    visit_date: date,
    weather_by_date: Mapping[date, DailyWeather],
    state: _DayState | None,
    required_duration: int,
    duration_ratio: float,
) -> list[RejectionCode]:
    reasons: list[RejectionCode] = []
    if state is None:
        return [RejectionCode.EMPTY_DAY_WINDOW]
    if not is_open_on(attraction, visit_date):
        reasons.append(RejectionCode.CLOSED_ON_DATE)
    weather = weather_by_date.get(visit_date)
    if weather is None:
        reasons.append(RejectionCode.WEATHER_DATA_MISSING)
    else:
        if weather.day != visit_date:
            raise ValueError("weather mapping key must match DailyWeather.day")
        weather_result = evaluate_weather_availability(attraction, weather)
        if weather_result.rejection_code is not None:
            reasons.append(weather_result.rejection_code)
    window_resolution = resolve_effective_window(
        attraction,
        visit_date,
        duration_ratio=duration_ratio,
    )
    window = window_resolution.window
    if window is None:
        if window_resolution.rejection_code is not None:
            reasons.append(window_resolution.rejection_code)
    else:
        earliest_start = max(state.bounds.start_min, window.open_min)
        latest_start = min(state.bounds.end_min - required_duration, window.latest_arrival_min)
        if earliest_start > latest_start:
            reasons.append(RejectionCode.ARRIVAL_AFTER_LATEST_ARRIVAL)
    if not reasons and state.used_duration_min + required_duration > state.capacity_min:
        reasons.append(RejectionCode.DAY_CAPACITY_EXCEEDED)
    return reasons


def _candidate_key(
    state: _DayState,
    preference: AttractionPreference,
    required_duration: int,
    travel_mode: TravelMode,
) -> tuple[int, int, int, date]:
    distance = abs((state.visit_date - preference.preferred_date).days)
    projected_energy = state.energy_total + preference.attraction.energy_level
    projected_load = state.used_duration_min + required_duration
    if travel_mode is TravelMode.LEISURE:
        return projected_energy, distance, projected_load, state.visit_date
    if travel_mode is TravelMode.NORMAL:
        return distance, projected_energy, projected_load, state.visit_date
    return distance, projected_load, projected_energy, state.visit_date


def _overall_rejection_code(
    date_rejections: list[DateRejection],
    unavailable_days: set[date],
) -> RejectionCode:
    reason_sets = [set(item.reasons) for item in date_rejections]
    if reason_sets and all(
        RejectionCode.DAY_CAPACITY_EXCEEDED in reasons for reasons in reason_sets
    ):
        return RejectionCode.DAY_CAPACITY_EXCEEDED
    if reason_sets and all(
        RejectionCode.EXTREME_WEATHER_OUTDOOR in reasons for reasons in reason_sets
    ):
        return RejectionCode.NO_WEATHER_SAFE_DATE
    if unavailable_days and len(unavailable_days) == len(date_rejections):
        return RejectionCode.EMPTY_DAY_WINDOW
    return RejectionCode.NO_AVAILABLE_DATE


def _duration_ratio(travel_mode: TravelMode) -> float:
    return 0.7 if travel_mode is TravelMode.LEISURE else DEFAULT_DURATION_RATIO


def _build_day_plan(state: _DayState, travel_mode: TravelMode) -> DayPlan:
    pace = _pace_level(state, travel_mode)
    notices = {
        PaceLevel.RELAXED: "本日节奏偏松",
        PaceLevel.BALANCED: "本日节奏适中",
        PaceLevel.TIGHT: "本日节奏偏紧",
    }
    return DayPlan(
        state.visit_date,
        state.bounds,
        tuple(state.allocations),
        state.used_duration_min,
        state.energy_total,
        pace,
        notices[pace],
    )


def _pace_level(state: _DayState, travel_mode: TravelMode) -> PaceLevel:
    if state.capacity_min == 0:
        return PaceLevel.TIGHT
    utilization = state.used_duration_min / state.capacity_min
    tight_energy = {TravelMode.SPEED: 12, TravelMode.NORMAL: 9, TravelMode.LEISURE: 7}
    if utilization >= 0.8 or state.energy_total >= tight_energy[travel_mode]:
        return PaceLevel.TIGHT
    if utilization <= 0.35 and state.energy_total <= 3:
        return PaceLevel.RELAXED
    return PaceLevel.BALANCED
