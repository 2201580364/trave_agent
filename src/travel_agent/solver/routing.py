"""OR-Tools single-day routing with C2/C4/C6 and final hard validation.

Traceability: H3, C1, C2, C4, C5, C6, S1, ADR-0001, ADR-0003, ADR-0004.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date
from time import perf_counter
from typing import Any, Protocol

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from .availability import is_open_on
from .models import (
    ConstraintViolation,
    DailyWeather,
    DayAllocation,
    DayPlan,
    RejectionCode,
    RouteSearchStatus,
    RouteSolveMetadata,
    RoutedDay,
    RouteUnplaced,
    RouteValidation,
    RouteVisit,
)
from .time_windows import DEFAULT_DURATION_RATIO, resolve_effective_window
from .transport import (
    DEFAULT_TRANSIT_BUFFER_RATIO,
    TravelTimeProvider,
    evaluate_connection,
)
from .weather import evaluate_weather_availability

DEFAULT_DROP_PENALTY = 1_000_000
DEFAULT_TIME_LIMIT_SECONDS = 2


class RoutingSearchExecutor(Protocol):
    """Injectable search boundary used for deterministic timeout-status tests."""

    def solve(self, routing: pywrapcp.RoutingModel, parameters: Any) -> Any | None: ...

    def status(self, routing: pywrapcp.RoutingModel) -> int: ...


class DefaultRoutingSearchExecutor:
    def solve(self, routing: pywrapcp.RoutingModel, parameters: Any) -> Any | None:
        return routing.SolveWithParameters(parameters)

    def status(self, routing: pywrapcp.RoutingModel) -> int:
        return routing.status()


def route_day(
    day_plan: DayPlan,
    provider: TravelTimeProvider,
    *,
    drop_penalty: int = DEFAULT_DROP_PENALTY,
    time_limit_seconds: int = DEFAULT_TIME_LIMIT_SECONDS,
    buffer_ratio: float = DEFAULT_TRANSIT_BUFFER_RATIO,
    search_executor: RoutingSearchExecutor | None = None,
) -> RoutedDay:
    """Order one day's allocations while allowing explicit, penalized dropping."""

    if drop_penalty <= 0:
        raise ValueError("drop_penalty must be positive")
    if time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be positive")
    if buffer_ratio < 1:
        raise ValueError("buffer_ratio must be at least 1")
    allocations = day_plan.allocations
    if not allocations:
        return RoutedDay(day_plan.visit_date, day_plan.bounds, (), (), 0, 0)
    attraction_ids = [item.attraction.id for item in allocations]
    if len(set(attraction_ids)) != len(attraction_ids):
        raise ValueError("day allocations must contain unique attraction ids")
    for allocation in allocations:
        if allocation.assigned_date != day_plan.visit_date:
            raise ValueError("allocation assigned_date must match DayPlan.visit_date")
        minimum_duration = math.ceil(
            allocation.attraction.suggested_duration * DEFAULT_DURATION_RATIO
        )
        if allocation.required_duration_min < minimum_duration:
            raise ValueError("allocation duration must satisfy the C2 minimum ratio")

    manager = pywrapcp.RoutingIndexManager(len(allocations) + 1, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def raw_travel_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        if from_node == 0 or to_node == 0:
            return 0
        travel = provider.get_travel_time(
            allocations[from_node - 1].attraction.id,
            allocations[to_node - 1].attraction.id,
        )
        return travel.travel_min if travel is not None else drop_penalty

    cost_callback = routing.RegisterTransitCallback(raw_travel_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(cost_callback)

    def time_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        service_min = allocations[from_node - 1].required_duration_min if from_node else 0
        if from_node == 0 or to_node == 0:
            return service_min
        travel = provider.get_travel_time(
            allocations[from_node - 1].attraction.id,
            allocations[to_node - 1].attraction.id,
        )
        if travel is None:
            return service_min + drop_penalty
        return service_min + math.ceil(travel.travel_min * buffer_ratio)

    time_callback_index = routing.RegisterTransitCallback(time_callback)
    day_span = day_plan.bounds.end_min - day_plan.bounds.start_min
    routing.AddDimension(
        time_callback_index,
        max(0, day_span),
        day_plan.bounds.end_min,
        False,
        "Time",
    )
    time_dimension = routing.GetDimensionOrDie("Time")
    start_index = routing.Start(0)
    end_index = routing.End(0)
    time_dimension.CumulVar(start_index).SetValue(day_plan.bounds.start_min)
    time_dimension.CumulVar(end_index).SetRange(
        day_plan.bounds.start_min,
        day_plan.bounds.end_min,
    )

    for node, allocation in enumerate(allocations, start=1):
        index = manager.NodeToIndex(node)
        resolution = resolve_effective_window(allocation.attraction, day_plan.visit_date)
        if resolution.window is None:
            routing.AddDisjunction([index], drop_penalty)
            routing.ActiveVar(index).SetValue(0)
            continue
        window = resolution.window
        earliest = max(day_plan.bounds.start_min, window.open_min)
        latest = min(
            day_plan.bounds.end_min - allocation.required_duration_min,
            window.last_entry_min if window.last_entry_min is not None else window.close_min,
            window.close_min - allocation.required_duration_min,
        )
        routing.AddDisjunction([index], drop_penalty)
        if earliest > latest:
            routing.ActiveVar(index).SetValue(0)
        else:
            time_dimension.CumulVar(index).SetRange(earliest, latest)

    _remove_missing_od_arcs(routing, manager, allocations, provider)

    search = pywrapcp.DefaultRoutingSearchParameters()
    search.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GREEDY_DESCENT
    )
    search.time_limit.seconds = time_limit_seconds
    executor = search_executor or DefaultRoutingSearchExecutor()
    search_started = perf_counter()
    solution = executor.solve(routing, search)
    elapsed_ms = max(0, round((perf_counter() - search_started) * 1000))
    raw_status = executor.status(routing)
    metadata = _solve_metadata(
        raw_status,
        solution_found=solution is not None,
        time_limit_seconds=time_limit_seconds,
        elapsed_ms=elapsed_ms,
    )
    if solution is None:
        rejection_code = (
            RejectionCode.SOLVER_TIME_LIMIT
            if metadata.status is RouteSearchStatus.TIME_LIMIT_NO_SOLUTION
            else RejectionCode.NO_FEASIBLE_ROUTE
        )
        return RoutedDay(
            day_plan.visit_date,
            day_plan.bounds,
            (),
            tuple(
                RouteUnplaced(item.attraction, rejection_code)
                for item in allocations
            ),
            0,
            0,
            metadata,
        )

    dropped = {
        node
        for node in range(1, len(allocations) + 1)
        if solution.Value(routing.NextVar(manager.NodeToIndex(node)))
        == manager.NodeToIndex(node)
    }
    unplaced = tuple(
        RouteUnplaced(allocations[node - 1].attraction, RejectionCode.ROUTING_UNPLACED)
        for node in sorted(dropped)
    )
    visits: list[RouteVisit] = []
    total_travel = 0
    total_buffered_travel = 0
    previous_allocation: DayAllocation | None = None
    index = solution.Value(routing.NextVar(start_index))
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        allocation = allocations[node - 1]
        arrival_min = solution.Value(time_dimension.CumulVar(index))
        travel = None
        buffered_travel = 0
        if previous_allocation is not None:
            travel = provider.get_travel_time(
                previous_allocation.attraction.id,
                allocation.attraction.id,
            )
            if travel is None:
                raise RuntimeError("solver selected an arc without OD data")
            total_travel += travel.travel_min
            buffered_travel = math.ceil(travel.travel_min * buffer_ratio)
            total_buffered_travel += buffered_travel
        notice = None
        if allocation.required_duration_min < allocation.attraction.suggested_duration:
            notice = (
                f"实际可玩 {allocation.required_duration_min} 分钟"
                f"（建议 {allocation.attraction.suggested_duration} 分钟）"
            )
        visits.append(
            RouteVisit(
                allocation.attraction,
                arrival_min,
                arrival_min + allocation.required_duration_min,
                allocation.required_duration_min,
                travel,
                buffered_travel,
                notice,
            )
        )
        previous_allocation = allocation
        index = solution.Value(routing.NextVar(index))

    return RoutedDay(
        day_plan.visit_date,
        day_plan.bounds,
        tuple(visits),
        unplaced,
        total_travel,
        total_buffered_travel,
        metadata,
    )


def _solve_metadata(
    raw_status: int,
    *,
    solution_found: bool,
    time_limit_seconds: int,
    elapsed_ms: int,
) -> RouteSolveMetadata:
    statuses = routing_enums_pb2.RoutingSearchStatus
    if solution_found:
        if raw_status == statuses.ROUTING_INVALID:
            raise RuntimeError("OR-Tools returned a solution with invalid search status")
        if raw_status in {
            statuses.ROUTING_PARTIAL_SUCCESS_LOCAL_OPTIMUM_NOT_REACHED,
            statuses.ROUTING_FAIL_TIMEOUT,
        }:
            status = RouteSearchStatus.BEST_SO_FAR
        else:
            status = RouteSearchStatus.COMPLETED
    elif raw_status == statuses.ROUTING_FAIL_TIMEOUT:
        status = RouteSearchStatus.TIME_LIMIT_NO_SOLUTION
    elif raw_status == statuses.ROUTING_INVALID:
        status = RouteSearchStatus.INVALID
    else:
        status = RouteSearchStatus.NO_SOLUTION
    return RouteSolveMetadata(
        status,
        time_limit_seconds,
        elapsed_ms,
        solution_found,
        status
        in {
            RouteSearchStatus.COMPLETED,
            RouteSearchStatus.NO_SOLUTION,
            RouteSearchStatus.INVALID,
        },
    )


def validate_routed_day(
    routed_day: RoutedDay,
    provider: TravelTimeProvider,
    *,
    weather_by_date: Mapping[date, DailyWeather],
    buffer_ratio: float = DEFAULT_TRANSIT_BUFFER_RATIO,
) -> RouteValidation:
    """Recheck C1/C2/C4/C5/C6 independently of the route construction."""

    violations: list[ConstraintViolation] = []
    weather = weather_by_date.get(routed_day.visit_date)
    for visit in routed_day.visits:
        attraction = visit.attraction
        if not is_open_on(attraction, routed_day.visit_date):
            violations.append(ConstraintViolation(RejectionCode.CLOSED_ON_DATE, attraction.id))
        if weather is None:
            violations.append(
                ConstraintViolation(RejectionCode.WEATHER_DATA_MISSING, attraction.id)
            )
        else:
            if weather.day != routed_day.visit_date:
                raise ValueError("weather mapping key must match DailyWeather.day")
            weather_result = evaluate_weather_availability(attraction, weather)
            if weather_result.rejection_code is not None:
                violations.append(
                    ConstraintViolation(weather_result.rejection_code, attraction.id)
                )
        resolution = resolve_effective_window(attraction, routed_day.visit_date)
        if resolution.window is None:
            if resolution.rejection_code is not None:
                violations.append(ConstraintViolation(resolution.rejection_code, attraction.id))
        else:
            window = resolution.window
            latest_for_planned_duration = min(
                window.last_entry_min
                if window.last_entry_min is not None
                else window.close_min,
                window.close_min - visit.planned_duration_min,
            )
            if not window.open_min <= visit.arrival_min <= latest_for_planned_duration:
                violations.append(
                    ConstraintViolation(
                        RejectionCode.ARRIVAL_AFTER_LATEST_ARRIVAL,
                        attraction.id,
                    )
                )
        minimum_duration = math.ceil(
            attraction.suggested_duration * DEFAULT_DURATION_RATIO
        )
        if (
            visit.planned_duration_min < minimum_duration
            or visit.leave_min != visit.arrival_min + visit.planned_duration_min
        ):
            violations.append(
                ConstraintViolation(
                    RejectionCode.VISIT_DURATION_INSUFFICIENT,
                    attraction.id,
                )
            )
    if routed_day.visits:
        if any(
            visit.arrival_min < routed_day.bounds.start_min
            or visit.leave_min > routed_day.bounds.end_min
            for visit in routed_day.visits
        ):
            violations.append(ConstraintViolation(RejectionCode.ANCHOR_VIOLATION))
    for previous, current in zip(
        routed_day.visits,
        routed_day.visits[1:],
        strict=False,
    ):
        connection = evaluate_connection(
            provider,
            origin_id=previous.attraction.id,
            destination_id=current.attraction.id,
            previous_leave_min=previous.leave_min,
            next_arrival_min=current.arrival_min,
            buffer_ratio=buffer_ratio,
        )
        if connection.rejection_code is not None:
            violations.append(
                ConstraintViolation(
                    connection.rejection_code,
                    current.attraction.id,
                    previous.attraction.id,
                )
            )
    return RouteValidation(not violations, tuple(violations))


def _remove_missing_od_arcs(
    routing: pywrapcp.RoutingModel,
    manager: pywrapcp.RoutingIndexManager,
    allocations: tuple[DayAllocation, ...],
    provider: TravelTimeProvider,
) -> None:
    for origin_node, origin in enumerate(allocations, start=1):
        origin_index = manager.NodeToIndex(origin_node)
        for destination_node, destination in enumerate(allocations, start=1):
            if origin_node == destination_node:
                continue
            if (
                provider.get_travel_time(origin.attraction.id, destination.attraction.id)
                is None
            ):
                routing.NextVar(origin_index).RemoveValue(manager.NodeToIndex(destination_node))
