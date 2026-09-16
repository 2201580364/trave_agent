"""Deterministic soft refinement for a usable, well-spread day schedule.

The routing model first establishes a hard-feasible order using the minimum
visit duration accepted by C2.  This module then uses genuine remaining slack
to move planned durations towards the published suggestion, preserve a lunch
gap, and keep daytime visits from being compressed into one part of the day.
It never changes visit order or weakens C1/C2/C4/C5/C6.

Traceability: H3, S1, DAY_SPREAD, LUNCH_BLOCK, ADR-0010.
"""

from __future__ import annotations

from dataclasses import replace

from .models import RoutedDay, RouteVisit
from .quality_refinement import refine_ordered_schedule
from .time_windows import resolve_effective_window
from .visit_periods import evaluate_visit_period

DEFAULT_DAY_SPREAD_TARGET_END_MIN = 16 * 60
DEFAULT_DAY_SPREAD_MAX_DELAY_MIN = 60
DEFAULT_LUNCH_EARLIEST_MIN = 11 * 60 + 30
DEFAULT_LUNCH_LATEST_END_MIN = 14 * 60
DEFAULT_LUNCH_DURATION_MIN = 60
DEFAULT_LUNCH_TARGET_END_MIN = 13 * 60


def refine_daytime_schedule(
    route: RoutedDay,
    *,
    daytime_visit_count: int,
    cross_buffered_min: int,
    dinner_duration_min: int,
) -> RoutedDay:
    """Expand and spread a multi-stop daytime route when real slack exists.

    The refinement is deliberately conservative:

    * a single daytime visit is only moved when a fixed evening segment exists;
    * two or more daytime visits use the meal-aware fixed-order refinement;
    * the OR-Tools order and all OD edges remain unchanged;
    * a full dinner gap before an evening segment is preserved;
    * candidates that no longer fit an attraction window are discarded;
    * the original hard-feasible route is returned when no refinement fits.
    """

    if daytime_visit_count > len(route.visits):
        return route

    if daytime_visit_count >= 2:
        return refine_ordered_schedule(route)

    route = _expand_evening_durations(route, daytime_visit_count)
    if daytime_visit_count == 1:
        return _expand_single_daytime_duration(
            route,
            cross_buffered_min=cross_buffered_min,
            dinner_duration_min=dinner_duration_min,
        )
    return route


def _expand_evening_durations(route: RoutedDay, daytime_visit_count: int) -> RoutedDay:
    """Use available event-window slack without moving evening arrivals."""

    visits = list(route.visits)
    for index in range(len(visits) - 1, daytime_visit_count - 1, -1):
        visit = visits[index]
        resolution = resolve_effective_window(visit.attraction, route.visit_date)
        if resolution.window is None:
            continue
        next_start = route.bounds.end_min
        if index + 1 < len(visits):
            following = visits[index + 1]
            next_start = (
                following.arrival_min
                - following.buffered_travel_from_previous_min
            )
        maximum_leave = min(resolution.window.close_min, next_start)
        expanded_duration = min(
            visit.attraction.suggested_duration,
            maximum_leave - visit.arrival_min,
        )
        if expanded_duration > visit.planned_duration_min:
            visits[index] = _reschedule_visit(
                visit,
                visit.arrival_min,
                expanded_duration,
            )
    return replace(route, visits=tuple(visits))


def _expand_single_daytime_duration(
    route: RoutedDay,
    *,
    cross_buffered_min: int,
    dinner_duration_min: int,
) -> RoutedDay:
    """Expand one daytime visit and cover the afternoon before an evening event.

    A single daytime node has no inter-visit order or OD to protect, so limiting
    its move to the multi-node 60-minute adjustment can leave most of the
    afternoon empty.  When an evening segment exists, this refinement therefore
    targets a 16:00 departure while preserving a full lunch before the visit,
    the real cross-segment OD, and a full dinner before the fixed event.
    """

    visit = route.visits[0]
    resolution = resolve_effective_window(visit.attraction, route.visit_date)
    if resolution.window is None:
        return route
    window = resolution.window
    deadline = min(route.bounds.end_min, window.close_min)
    can_spread_before_evening = False
    if len(route.visits) > 1:
        dinner_safe_deadline = (
            route.visits[1].arrival_min
            - cross_buffered_min
            - dinner_duration_min
        )
        if dinner_safe_deadline >= visit.leave_min:
            deadline = min(deadline, dinner_safe_deadline)
            can_spread_before_evening = True
        else:
            deadline = min(
                deadline,
                route.visits[1].arrival_min - cross_buffered_min,
            )
    expanded_duration = min(
        visit.attraction.suggested_duration,
        deadline - visit.arrival_min,
    )
    if expanded_duration < visit.planned_duration_min:
        return route
    visits = list(route.visits)
    if expanded_duration > visit.planned_duration_min:
        visits[0] = _reschedule_visit(
            visit,
            visit.arrival_min,
            expanded_duration,
        )
    expanded = replace(route, visits=tuple(visits))
    if not _times_fit(expanded):
        return route
    if not can_spread_before_evening:
        return expanded

    lunch_start = max(route.bounds.start_min, DEFAULT_LUNCH_EARLIEST_MIN)
    lunch_ready = lunch_start + DEFAULT_LUNCH_DURATION_MIN
    if lunch_ready > DEFAULT_LUNCH_LATEST_END_MIN:
        return expanded

    target_leave = min(DEFAULT_DAY_SPREAD_TARGET_END_MIN, deadline)
    desired_arrival = max(
        visit.arrival_min,
        lunch_ready,
        target_leave - expanded_duration,
    )
    latest_arrival = min(
        window.last_entry_min
        if window.last_entry_min is not None
        else window.close_min,
        window.close_min - expanded_duration,
        route.bounds.end_min - expanded_duration,
        deadline - expanded_duration,
    )
    if desired_arrival > latest_arrival:
        return expanded

    visits = list(expanded.visits)
    visits[0] = _reschedule_visit(
        visits[0],
        desired_arrival,
        expanded_duration,
    )
    candidate = replace(expanded, visits=tuple(visits))
    return candidate if _times_fit(candidate) else expanded


def _reschedule_visit(visit: RouteVisit, arrival: int, duration: int) -> RouteVisit:
    notice = None
    if duration < visit.attraction.suggested_duration:
        notice = (
            f"实际可玩 {duration} 分钟"
            f"（建议 {visit.attraction.suggested_duration} 分钟）"
        )
    period = (
        evaluate_visit_period(arrival, visit.visit_period.preference)
        if visit.visit_period is not None
        else None
    )
    return replace(
        visit,
        arrival_min=arrival,
        leave_min=arrival + duration,
        planned_duration_min=duration,
        duration_notice=notice,
        visit_period=period,
    )


def _times_fit(route: RoutedDay) -> bool:
    for visit in route.visits:
        resolution = resolve_effective_window(visit.attraction, route.visit_date)
        if resolution.window is None:
            return False
        window = resolution.window
        latest = min(
            window.last_entry_min
            if window.last_entry_min is not None
            else window.close_min,
            window.close_min - visit.planned_duration_min,
            route.bounds.end_min - visit.planned_duration_min,
        )
        if not max(route.bounds.start_min, window.open_min) <= visit.arrival_min <= latest:
            return False
    return True
