"""Whole-itinerary routing with deterministic cross-day recovery.

Traceability: H2, H3, C1, C2, C4, C5, C6, S2, ADR-0003, ADR-0004.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import date

from .availability import is_open_on
from .day_assignment import rebuild_day_plan
from .models import (
    DailyWeather,
    DayAllocation,
    DayPlan,
    ItineraryPlan,
    ItineraryReassignment,
    ItineraryUnplaced,
    RejectionCode,
    RoutingAttempt,
    Step1Plan,
)
from .routing import validate_routed_day
from .segments import route_segmented_day
from .time_windows import resolve_effective_window
from .transport import DEFAULT_TRANSIT_BUFFER_RATIO, TravelTimeProvider
from .weather import evaluate_weather_availability


def route_itinerary(
    step1_plan: Step1Plan,
    provider: TravelTimeProvider,
    *,
    weather_by_date: Mapping[date, DailyWeather],
    buffer_ratio: float = DEFAULT_TRANSIT_BUFFER_RATIO,
) -> ItineraryPlan:
    """Route every day and rescue Step 2 drops on another feasible date."""

    base_by_date = {day.visit_date: day for day in step1_plan.days}
    if len(base_by_date) != len(step1_plan.days):
        raise ValueError("Step1Plan must contain unique day dates")
    allocated_ids = [
        allocation.attraction.id
        for day in step1_plan.days
        for allocation in day.allocations
    ]
    if len(set(allocated_ids)) != len(allocated_ids):
        raise ValueError("an attraction may be allocated to only one day")
    ordered_dates = tuple(sorted(base_by_date))
    allocations_by_date = {
        day.visit_date: list(day.allocations) for day in step1_plan.days
    }
    initial_routes = {
        visit_date: route_segmented_day(
            base_by_date[visit_date],
            provider,
            weather_by_date=weather_by_date,
            buffer_ratio=buffer_ratio,
            travel_mode=step1_plan.travel_mode,
        ).routed_day
        for visit_date in ordered_dates
    }

    dropped: list[tuple[date, DayAllocation, RejectionCode]] = []
    for source_date in ordered_dates:
        route = initial_routes[source_date]
        dropped_codes = {item.attraction.id: item.rejection_code for item in route.unplaced}
        if not dropped_codes:
            continue
        retained: list[DayAllocation] = []
        for allocation in allocations_by_date[source_date]:
            rejection_code = dropped_codes.get(allocation.attraction.id)
            if rejection_code is None:
                retained.append(allocation)
            else:
                dropped.append((source_date, allocation, rejection_code))
        allocations_by_date[source_date] = retained

    reassignments: list[ItineraryReassignment] = [
        ItineraryReassignment(
            allocation.attraction,
            allocation.preferred_date,
            allocation.assigned_date,
        )
        for day in step1_plan.days
        for allocation in day.allocations
        if allocation.preferred_date != allocation.assigned_date
    ]
    unplaced: list[ItineraryUnplaced] = [
        ItineraryUnplaced(
            item.attraction,
            item.preferred_date,
            item.rejection_code,
            tuple(
                RoutingAttempt(rejection.visit_date, rejection.reasons)
                for rejection in item.date_rejections
                if rejection.reasons
            ),
        )
        for item in step1_plan.unplaced
    ]

    dropped.sort(key=lambda item: (item[0], item[1].attraction.id))
    for source_date, allocation, original_code in dropped:
        attempts: list[RoutingAttempt] = []
        moved = False
        candidate_dates = sorted(
            (day for day in ordered_dates if day != source_date),
            key=lambda day: (abs((day - allocation.preferred_date).days), day),
        )
        for target_date in candidate_dates:
            base = base_by_date[target_date]
            reasons = _precheck_target(
                allocation,
                target_date,
                base,
                weather_by_date,
            )
            if reasons:
                attempts.append(RoutingAttempt(target_date, reasons))
                continue

            moved_allocation = replace(allocation, assigned_date=target_date)
            target_allocations = (*allocations_by_date[target_date], moved_allocation)
            candidate_plan = rebuild_day_plan(
                base,
                target_allocations,
                step1_plan.travel_mode,
            )
            candidate_route = route_segmented_day(
                candidate_plan,
                provider,
                weather_by_date=weather_by_date,
                buffer_ratio=buffer_ratio,
                travel_mode=step1_plan.travel_mode,
            ).routed_day
            expected_ids = {item.attraction.id for item in target_allocations}
            routed_ids = {item.attraction.id for item in candidate_route.visits}
            if routed_ids != expected_ids:
                candidate_dropped = {
                    item.attraction.id: item.rejection_code
                    for item in candidate_route.unplaced
                }
                code = candidate_dropped.get(
                    allocation.attraction.id,
                    RejectionCode.REASSIGNMENT_DISPLACES_EXISTING,
                )
                attempts.append(RoutingAttempt(target_date, (code,)))
                continue
            validation = validate_routed_day(
                candidate_route,
                provider,
                weather_by_date=weather_by_date,
                buffer_ratio=buffer_ratio,
            )
            if not validation.valid:
                codes = tuple(dict.fromkeys(item.code for item in validation.violations))
                attempts.append(RoutingAttempt(target_date, codes))
                continue

            allocations_by_date[target_date].append(moved_allocation)
            reassignments.append(
                ItineraryReassignment(
                    allocation.attraction,
                    source_date,
                    target_date,
                )
            )
            moved = True
            break

        if not moved:
            unplaced.append(
                ItineraryUnplaced(
                    allocation.attraction,
                    allocation.preferred_date,
                    original_code,
                    tuple(attempts),
                )
            )

    final_days = []
    final_segmented_days = []
    validations = []
    final_unplaced_ids = {item.attraction.id for item in unplaced}
    for visit_date in ordered_dates:
        plan = rebuild_day_plan(
            base_by_date[visit_date],
            allocations_by_date[visit_date],
            step1_plan.travel_mode,
        )
        segmented = route_segmented_day(
            plan,
            provider,
            weather_by_date=weather_by_date,
            buffer_ratio=buffer_ratio,
            travel_mode=step1_plan.travel_mode,
        )
        routed = segmented.routed_day
        final_days.append(routed)
        final_segmented_days.append(segmented)
        validations.append(
            validate_routed_day(
                routed,
                provider,
                weather_by_date=weather_by_date,
                buffer_ratio=buffer_ratio,
            )
        )
        allocation_by_id = {item.attraction.id: item for item in plan.allocations}
        for item in routed.unplaced:
            if item.attraction.id in final_unplaced_ids:
                continue
            allocation = allocation_by_id[item.attraction.id]
            unplaced.append(
                ItineraryUnplaced(
                    item.attraction,
                    allocation.preferred_date,
                    item.rejection_code,
                )
            )
            final_unplaced_ids.add(item.attraction.id)

    return ItineraryPlan(
        tuple(final_days),
        tuple(unplaced),
        step1_plan.data_rejected,
        tuple(reassignments),
        tuple(validations),
        all(item.valid for item in validations),
        tuple(final_segmented_days),
    )


def _precheck_target(
    allocation: DayAllocation,
    target_date: date,
    target_day: DayPlan,
    weather_by_date: Mapping[date, DailyWeather],
) -> tuple[RejectionCode, ...]:
    attraction = allocation.attraction
    reasons: list[RejectionCode] = []
    if not is_open_on(attraction, target_date):
        reasons.append(RejectionCode.CLOSED_ON_DATE)
    weather = weather_by_date.get(target_date)
    if weather is None:
        reasons.append(RejectionCode.WEATHER_DATA_MISSING)
    else:
        if weather.day != target_date:
            raise ValueError("weather mapping key must match DailyWeather.day")
        weather_result = evaluate_weather_availability(attraction, weather)
        if weather_result.rejection_code is not None:
            reasons.append(weather_result.rejection_code)
    resolution = resolve_effective_window(attraction, target_date)
    if resolution.window is None:
        if resolution.rejection_code is not None:
            reasons.append(resolution.rejection_code)
    else:
        window = resolution.window
        earliest = max(target_day.bounds.start_min, window.open_min)
        latest = min(
            target_day.bounds.end_min - allocation.required_duration_min,
            window.last_entry_min if window.last_entry_min is not None else window.close_min,
            window.close_min - allocation.required_duration_min,
        )
        if earliest > latest:
            reasons.append(RejectionCode.ARRIVAL_AFTER_LATEST_ARRIVAL)
    return tuple(reasons)
