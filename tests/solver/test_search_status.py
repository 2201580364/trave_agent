"""OR-Tools search status and timeout evidence. Traceability: H3, Gate 6."""

from datetime import UTC, date, datetime
from typing import Any

from ortools.constraint_solver import routing_enums_pb2

from travel_agent.observability import build_solver_run_audit
from travel_agent.solver import (
    Attraction,
    AttractionPreference,
    DailyWeather,
    DayAllocation,
    DayPlan,
    DayTimeBounds,
    DefaultRoutingSearchExecutor,
    DegradationCode,
    InMemoryTravelTimeProvider,
    PaceLevel,
    RejectionCode,
    RouteSearchStatus,
    RoutingSearchExecutor,
    TimeRule,
    TripTimeAnchors,
    WeatherBasis,
    WeatherSeverity,
    assign_days,
    evaluate_itinerary_degradation,
    evaluate_solver_quality,
    route_day,
    route_itinerary,
    validate_routed_day,
)


DAY = date(2026, 8, 24)
NOW = datetime(2026, 8, 23, tzinfo=UTC)
RULES = (TimeRule.from_strings(("01-01", "12-31"), "09:00", "18:00"),)


class ForcedStatusExecutor(RoutingSearchExecutor):
    def __init__(self, status: int, *, return_solution: bool) -> None:
        self.forced_status = status
        self.return_solution = return_solution
        self.delegate = DefaultRoutingSearchExecutor()

    def solve(self, routing: Any, parameters: Any) -> Any | None:
        if not self.return_solution:
            return None
        return self.delegate.solve(routing, parameters)

    def status(self, routing: Any) -> int:
        return self.forced_status


def _attraction() -> Attraction:
    return Attraction(
        1,
        "搜索状态景点",
        suggested_duration=60,
        time_rules=RULES,
        data_verified=True,
    )


def _day_plan(attraction: Attraction) -> DayPlan:
    allocation = DayAllocation(attraction, DAY, DAY, 36)
    return DayPlan(
        DAY,
        DayTimeBounds(9 * 60, 18 * 60),
        (allocation,),
        36,
        1,
        PaceLevel.RELAXED,
        "本日节奏偏松",
    )


def _weather() -> dict[date, DailyWeather]:
    return {
        DAY: DailyWeather(DAY, WeatherBasis.FORECAST, WeatherSeverity.NORMAL)
    }


def test_default_search_exposes_completed_metadata() -> None:
    route = route_day(_day_plan(_attraction()), InMemoryTravelTimeProvider({}))

    assert route.solve_metadata.status is RouteSearchStatus.COMPLETED
    assert route.solve_metadata.solution_found
    assert route.solve_metadata.search_finished
    assert route.solve_metadata.time_limit_seconds == 2


def test_partial_status_keeps_validated_best_so_far_solution() -> None:
    executor = ForcedStatusExecutor(
        routing_enums_pb2.RoutingSearchStatus.ROUTING_PARTIAL_SUCCESS_LOCAL_OPTIMUM_NOT_REACHED,
        return_solution=True,
    )
    provider = InMemoryTravelTimeProvider({})
    route = route_day(_day_plan(_attraction()), provider, search_executor=executor)
    validation = validate_routed_day(route, provider, weather_by_date=_weather())

    assert route.solve_metadata.status is RouteSearchStatus.BEST_SO_FAR
    assert route.solve_metadata.solution_found
    assert not route.solve_metadata.search_finished
    assert validation.valid


def test_timeout_without_solution_uses_structured_rejection() -> None:
    executor = ForcedStatusExecutor(
        routing_enums_pb2.RoutingSearchStatus.ROUTING_FAIL_TIMEOUT,
        return_solution=False,
    )
    route = route_day(
        _day_plan(_attraction()),
        InMemoryTravelTimeProvider({}),
        search_executor=executor,
    )

    assert route.solve_metadata.status is RouteSearchStatus.TIME_LIMIT_NO_SOLUTION
    assert not route.solve_metadata.solution_found
    assert not route.solve_metadata.search_finished
    assert route.unplaced[0].rejection_code is RejectionCode.SOLVER_TIME_LIMIT


def test_itinerary_timeout_counts_flow_to_degradation_and_audit() -> None:
    attraction = _attraction()
    weather = _weather()
    step1 = assign_days(
        (AttractionPreference(attraction, DAY),),
        trip_dates=(DAY,),
        weather_by_date=weather,
        anchors=TripTimeAnchors(9 * 60, 0, 18 * 60, 0, 0),
    )
    executor = ForcedStatusExecutor(
        routing_enums_pb2.RoutingSearchStatus.ROUTING_PARTIAL_SUCCESS_LOCAL_OPTIMUM_NOT_REACHED,
        return_solution=True,
    )
    itinerary = route_itinerary(
        step1,
        InMemoryTravelTimeProvider({}),
        weather_by_date=weather,
        search_executor=executor,
    )
    quality = evaluate_solver_quality(itinerary, (attraction,))
    degradation = evaluate_itinerary_degradation(
        itinerary,
        quality,
        input_count=1,
        day_count=1,
    )
    audit = build_solver_run_audit(
        itinerary,
        quality,
        solve_run_id="timeout-1",
        solver_version="0.1.0",
        constraint_version="ADR-0004",
        parameter_version="p1-v1",
        input_snapshot_hash="sha256:test",
        data_snapshot_version="fixture",
        od_basis="approximate",
        weather_basis="forecast",
        random_seed=0,
        duration_ratio=0.6,
        elapsed_ms=10,
        created_at=NOW,
    )

    assert quality.gate_passed
    assert itinerary.timed_out_day_count == 1
    assert itinerary.best_so_far_day_count == 1
    assert itinerary.no_solution_day_count == 0
    assert degradation.explainable
    assert any(
        item.code is DegradationCode.SEARCH_BEST_SO_FAR
        for item in degradation.notices
    )
    assert audit.timed_out_day_count == 1
    assert audit.best_so_far_day_count == 1
