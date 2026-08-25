"""Daytime/evening separation with a flexible soft dinner block.

Traceability: H3, C2, C4, C6, trip-solver Step 3, ADR-0004 P0-2.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import replace
from datetime import date

from .day_assignment import rebuild_day_plan
from .models import (
    DailyWeather,
    DayAllocation,
    DayPlan,
    MealPlacement,
    MealPlan,
    MealStatus,
    RejectionCode,
    RoutedDay,
    RouteSearchStatus,
    RouteSegment,
    RouteSolveMetadata,
    RouteUnplaced,
    RouteVisit,
    SegmentedDay,
    TravelMode,
    TravelTimeResult,
)
from .routing import RoutingSearchExecutor, route_day, validate_routed_day
from .schedule_refinement import refine_daytime_schedule
from .time_windows import resolve_effective_window
from .transport import DEFAULT_TRANSIT_BUFFER_RATIO, TravelTimeProvider
from .visit_periods import evaluate_visit_period

DEFAULT_EVENING_OPEN_MIN = 17 * 60
DEFAULT_DINNER_EARLIEST_MIN = 16 * 60 + 30
DEFAULT_DINNER_LATEST_END_MIN = 22 * 60
DEFAULT_DINNER_DURATION_MIN = 90
REDUCED_DINNER_DURATION_MIN = 60


def route_segmented_day(
    day_plan: DayPlan,
    provider: TravelTimeProvider,
    *,
    weather_by_date: Mapping[date, DailyWeather],
    evening_open_min: int = DEFAULT_EVENING_OPEN_MIN,
    dinner_earliest_min: int = DEFAULT_DINNER_EARLIEST_MIN,
    dinner_latest_end_min: int = DEFAULT_DINNER_LATEST_END_MIN,
    dinner_duration_min: int = DEFAULT_DINNER_DURATION_MIN,
    reduced_dinner_duration_min: int = REDUCED_DINNER_DURATION_MIN,
    buffer_ratio: float = DEFAULT_TRANSIT_BUFFER_RATIO,
    travel_mode: TravelMode = TravelMode.NORMAL,
    search_executor: RoutingSearchExecutor | None = None,
) -> SegmentedDay:
    """Keep evening-only nodes after daytime nodes; dinner remains a soft block."""

    if evening_open_min < 0 or dinner_earliest_min < 0:
        raise ValueError("segment and dinner thresholds must be non-negative")
    if dinner_latest_end_min <= dinner_earliest_min:
        raise ValueError("dinner preference window is invalid")
    if not 0 < reduced_dinner_duration_min <= dinner_duration_min:
        raise ValueError("dinner durations are invalid")

    daytime_allocations: list[DayAllocation] = []
    evening_allocations: list[DayAllocation] = []
    for allocation in day_plan.allocations:
        segment = _segment_for(allocation, day_plan.visit_date, evening_open_min)
        if segment is RouteSegment.EVENING:
            evening_allocations.append(allocation)
        else:
            daytime_allocations.append(allocation)

    daytime_route = _route_allocations(
        day_plan,
        daytime_allocations,
        provider,
        buffer_ratio,
        travel_mode,
        search_executor,
    )
    evening_route = _route_allocations(
        day_plan,
        evening_allocations,
        provider,
        buffer_ratio,
        travel_mode,
        search_executor,
    )
    merged, cross_rejection, cross_buffered = _merge_segments(
        day_plan,
        daytime_route,
        evening_route,
        provider,
        buffer_ratio,
    )
    merged = refine_daytime_schedule(
        merged,
        daytime_visit_count=len(daytime_route.visits) if daytime_route is not None else 0,
        cross_buffered_min=cross_buffered,
        dinner_duration_min=dinner_duration_min,
    )
    meal_plan = _schedule_meal(
        merged,
        daytime_visit_count=len(daytime_route.visits) if daytime_route is not None else 0,
        cross_buffered_min=cross_buffered,
        dinner_earliest_min=dinner_earliest_min,
        dinner_latest_end_min=dinner_latest_end_min,
        full_duration_min=dinner_duration_min,
        reduced_duration_min=reduced_dinner_duration_min,
    )
    validation = validate_routed_day(
        merged,
        provider,
        weather_by_date=weather_by_date,
        buffer_ratio=buffer_ratio,
    )
    return SegmentedDay(
        merged,
        daytime_route,
        evening_route,
        meal_plan,
        cross_rejection,
        validation,
    )


def _route_allocations(
    base: DayPlan,
    allocations: list[DayAllocation],
    provider: TravelTimeProvider,
    buffer_ratio: float,
    travel_mode: TravelMode,
    search_executor: RoutingSearchExecutor | None,
) -> RoutedDay | None:
    if not allocations:
        return None
    plan = rebuild_day_plan(base, allocations, travel_mode)
    return route_day(
        plan,
        provider,
        buffer_ratio=buffer_ratio,
        search_executor=search_executor,
    )


def _segment_for(
    allocation: DayAllocation,
    visit_date: date,
    evening_open_min: int,
) -> RouteSegment:
    resolution = resolve_effective_window(allocation.attraction, visit_date)
    if resolution.window is not None and resolution.window.open_min >= evening_open_min:
        return RouteSegment.EVENING
    return RouteSegment.DAYTIME


def _merge_segments(
    original_plan: DayPlan,
    daytime: RoutedDay | None,
    evening: RoutedDay | None,
    provider: TravelTimeProvider,
    buffer_ratio: float,
) -> tuple[RoutedDay, RejectionCode | None, int]:
    solve_metadata = _combine_solve_metadata(daytime, evening)
    daytime_visits = list(daytime.visits) if daytime is not None else []
    evening_visits = list(evening.visits) if evening is not None else []
    daytime_unplaced = daytime.unplaced if daytime is not None else ()
    evening_unplaced = evening.unplaced if evening is not None else ()
    daytime_raw = daytime.total_travel_min if daytime is not None else 0
    evening_raw = evening.total_travel_min if evening is not None else 0
    daytime_buffered = daytime.total_buffered_travel_min if daytime is not None else 0
    evening_buffered = evening.total_buffered_travel_min if evening is not None else 0
    if not daytime_visits or not evening_visits:
        return (
            RoutedDay(
                original_plan.visit_date,
                original_plan.bounds,
                (*daytime_visits, *evening_visits),
                (*daytime_unplaced, *evening_unplaced),
                daytime_raw + evening_raw,
                daytime_buffered + evening_buffered,
                solve_metadata,
            ),
            None,
            0,
        )

    travel = provider.get_travel_time(
        daytime_visits[-1].attraction.id,
        evening_visits[0].attraction.id,
    )
    if travel is None:
        return (
            _reject_evening_segment(
                original_plan,
                daytime_visits,
                daytime_unplaced,
                evening_unplaced,
                evening_visits,
                daytime_raw,
                daytime_buffered,
                RejectionCode.OD_DATA_MISSING,
                solve_metadata,
            ),
            RejectionCode.OD_DATA_MISSING,
            0,
        )

    cross_buffered = math.ceil(travel.travel_min * buffer_ratio)
    required_arrival = daytime_visits[-1].leave_min + cross_buffered
    shift = max(0, required_arrival - evening_visits[0].arrival_min)
    if shift:
        evening_visits = [_shift_visit(visit, shift) for visit in evening_visits]
    candidate = _combined_route(
        original_plan,
        daytime_visits,
        evening_visits,
        daytime_unplaced,
        evening_unplaced,
        daytime_raw + evening_raw + travel.travel_min,
        daytime_buffered + evening_buffered + cross_buffered,
        travel,
        cross_buffered,
        solve_metadata,
    )
    if not _times_fit(candidate):
        return (
            _reject_evening_segment(
                original_plan,
                daytime_visits,
                daytime_unplaced,
                evening_unplaced,
                evening_visits,
                daytime_raw,
                daytime_buffered,
                RejectionCode.TRANSIT_INFEASIBLE,
                solve_metadata,
            ),
            RejectionCode.TRANSIT_INFEASIBLE,
            0,
        )
    return candidate, None, cross_buffered


def _combined_route(
    original_plan: DayPlan,
    daytime_visits: list[RouteVisit],
    evening_visits: list[RouteVisit],
    daytime_unplaced: tuple[RouteUnplaced, ...],
    evening_unplaced: tuple[RouteUnplaced, ...],
    total_raw: int,
    total_buffered: int,
    cross_travel: TravelTimeResult,
    cross_buffered: int,
    solve_metadata: RouteSolveMetadata,
) -> RoutedDay:
    evening_visits[0] = replace(
        evening_visits[0],
        travel_from_previous=cross_travel,
        buffered_travel_from_previous_min=cross_buffered,
    )
    return RoutedDay(
        original_plan.visit_date,
        original_plan.bounds,
        (*daytime_visits, *evening_visits),
        (*daytime_unplaced, *evening_unplaced),
        total_raw,
        total_buffered,
        solve_metadata,
    )


def _reject_evening_segment(
    original_plan: DayPlan,
    daytime_visits: list[RouteVisit],
    daytime_unplaced: tuple[RouteUnplaced, ...],
    evening_unplaced: tuple[RouteUnplaced, ...],
    evening_visits: list[RouteVisit],
    daytime_raw: int,
    daytime_buffered: int,
    code: RejectionCode,
    solve_metadata: RouteSolveMetadata,
) -> RoutedDay:
    rejected = tuple(RouteUnplaced(visit.attraction, code) for visit in evening_visits)
    return RoutedDay(
        original_plan.visit_date,
        original_plan.bounds,
        tuple(daytime_visits),
        (*daytime_unplaced, *evening_unplaced, *rejected),
        daytime_raw,
        daytime_buffered,
        solve_metadata,
    )


def _combine_solve_metadata(
    daytime: RoutedDay | None,
    evening: RoutedDay | None,
) -> RouteSolveMetadata:
    metadata = tuple(
        route.solve_metadata for route in (daytime, evening) if route is not None
    )
    if not metadata:
        return RouteSolveMetadata(RouteSearchStatus.EMPTY, 0, 0, False, True)
    statuses = {item.status for item in metadata}
    has_timeout = bool(
        statuses.intersection(
            {
                RouteSearchStatus.BEST_SO_FAR,
                RouteSearchStatus.TIME_LIMIT_NO_SOLUTION,
            }
        )
    )
    if has_timeout and any(item.solution_found for item in metadata):
        status = RouteSearchStatus.BEST_SO_FAR
    elif has_timeout:
        status = RouteSearchStatus.TIME_LIMIT_NO_SOLUTION
    elif RouteSearchStatus.INVALID in statuses:
        status = RouteSearchStatus.INVALID
    elif RouteSearchStatus.NO_SOLUTION in statuses:
        status = RouteSearchStatus.NO_SOLUTION
    else:
        status = RouteSearchStatus.COMPLETED
    return RouteSolveMetadata(
        status,
        sum(item.time_limit_seconds for item in metadata),
        sum(item.elapsed_ms for item in metadata),
        status in {RouteSearchStatus.COMPLETED, RouteSearchStatus.BEST_SO_FAR},
        status
        in {
            RouteSearchStatus.EMPTY,
            RouteSearchStatus.COMPLETED,
            RouteSearchStatus.NO_SOLUTION,
            RouteSearchStatus.INVALID,
        },
    )


def _schedule_meal(
    route: RoutedDay,
    *,
    daytime_visit_count: int,
    cross_buffered_min: int,
    dinner_earliest_min: int,
    dinner_latest_end_min: int,
    full_duration_min: int,
    reduced_duration_min: int,
) -> MealPlan:
    intervals: list[tuple[MealPlacement, int, int, bool]] = []
    visits = route.visits
    if daytime_visit_count and len(visits) > daytime_visit_count:
        daytime_last = visits[daytime_visit_count - 1]
        evening_first = visits[daytime_visit_count]
        intervals.append(
            (
                MealPlacement.BETWEEN_SEGMENTS,
                daytime_last.leave_min,
                evening_first.arrival_min - cross_buffered_min,
                True,
            )
        )
    if visits:
        intervals.append(
            (
                MealPlacement.AFTER_LAST_VISIT,
                visits[-1].leave_min,
                route.bounds.end_min,
                False,
            )
        )
        intervals.append(
            (
                MealPlacement.BEFORE_FIRST_VISIT,
                route.bounds.start_min,
                visits[0].arrival_min,
                True,
            )
        )
    else:
        intervals.append(
            (
                MealPlacement.AFTER_LAST_VISIT,
                route.bounds.start_min,
                route.bounds.end_min,
                False,
            )
        )

    for duration, status in (
        (full_duration_min, MealStatus.FULL),
        (reduced_duration_min, MealStatus.REDUCED),
    ):
        for placement, start, end, schedule_late in intervals:
            meal = _fit_meal(
                placement,
                start,
                end,
                duration,
                dinner_earliest_min,
                dinner_latest_end_min,
                schedule_late,
                status,
            )
            if meal is not None:
                return meal
    return MealPlan(
        MealStatus.UNSCHEDULED,
        None,
        None,
        None,
        0,
        "当日晚餐时间紧张，请提前用餐或准备简餐",
    )


def _fit_meal(
    placement: MealPlacement,
    interval_start: int,
    interval_end: int,
    duration: int,
    preferred_start: int,
    preferred_end: int,
    schedule_late: bool,
    status: MealStatus,
) -> MealPlan | None:
    start_bound = max(interval_start, preferred_start)
    end_bound = min(interval_end, preferred_end)
    if end_bound - start_bound < duration:
        return None
    if schedule_late:
        end = end_bound
        start = end - duration
    else:
        start = start_bound
        end = start + duration
    notice = (
        f"已预留 {duration} 分钟晚餐"
        if status is MealStatus.FULL
        else f"晚餐留白缩短为 {duration} 分钟"
    )
    return MealPlan(status, placement, start, end, duration, notice)


def _shift_visit(visit: RouteVisit, shift: int) -> RouteVisit:
    arrival_min = visit.arrival_min + shift
    visit_period = (
        evaluate_visit_period(arrival_min, visit.visit_period.preference)
        if visit.visit_period is not None
        else None
    )
    return replace(
        visit,
        arrival_min=arrival_min,
        leave_min=visit.leave_min + shift,
        visit_period=visit_period,
    )


def _times_fit(route: RoutedDay) -> bool:
    for visit in route.visits:
        resolution = resolve_effective_window(visit.attraction, route.visit_date)
        if resolution.window is None:
            return False
        window = resolution.window
        latest = min(
            window.last_entry_min if window.last_entry_min is not None else window.close_min,
            window.close_min - visit.planned_duration_min,
            route.bounds.end_min - visit.planned_duration_min,
        )
        if not max(route.bounds.start_min, window.open_min) <= visit.arrival_min <= latest:
            return False
    return True
