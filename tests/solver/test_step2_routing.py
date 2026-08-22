"""G5 Step 2 routing tests. Traceability: H3, C1, C2, C4, C5, C6, S1."""

import math
from datetime import UTC, date, datetime

from travel_agent.solver import (
    Attraction,
    DailyWeather,
    DayAllocation,
    DayPlan,
    DayTimeBounds,
    InMemoryTravelTimeProvider,
    ODBasis,
    PaceLevel,
    RejectionCode,
    RoutedDay,
    RouteVisit,
    TimeRule,
    TravelTimeResult,
    WeatherBasis,
    WeatherSeverity,
    route_day,
    validate_routed_day,
)


DAY = date(2026, 8, 24)
NOW = datetime(2026, 8, 22, tzinfo=UTC)
ALL_DAY = (TimeRule.from_strings(("01-01", "12-31"), "09:00", "21:00"),)


def _attraction(
    attraction_id: int,
    *,
    rules: tuple[TimeRule, ...] = ALL_DAY,
    duration: int = 60,
) -> Attraction:
    return Attraction(
        attraction_id,
        f"景点 {attraction_id}",
        suggested_duration=duration,
        time_rules=rules,
        data_verified=True,
    )


def _travel(origin: int, destination: int, minutes: int) -> TravelTimeResult:
    return TravelTimeResult(
        origin,
        destination,
        minutes,
        ODBasis.GAODE,
        "test-od-v1",
        NOW,
    )


def _day(
    *attractions: Attraction,
    bounds: tuple[int, int] = (9 * 60, 18 * 60),
) -> DayPlan:
    allocations = tuple(
        DayAllocation(item, DAY, DAY, math.ceil(item.suggested_duration * 0.6))
        for item in attractions
    )
    return DayPlan(
        DAY,
        DayTimeBounds(*bounds),
        allocations,
        sum(item.required_duration_min for item in allocations),
        len(allocations),
        PaceLevel.BALANCED,
        "本日节奏适中",
    )


def _weather(
    severity: WeatherSeverity = WeatherSeverity.NORMAL,
) -> dict[date, DailyWeather]:
    return {DAY: DailyWeather(DAY, WeatherBasis.FORECAST, severity)}


def test_step2_routes_all_attractions_and_minimizes_raw_travel() -> None:
    first, second, third = _attraction(1), _attraction(2), _attraction(3)
    provider = InMemoryTravelTimeProvider(
        {
            (1, 2): _travel(1, 2, 10),
            (2, 3): _travel(2, 3, 10),
            (1, 3): _travel(1, 3, 50),
            (3, 2): _travel(3, 2, 50),
            (2, 1): _travel(2, 1, 50),
            (3, 1): _travel(3, 1, 10),
        }
    )

    result = route_day(_day(first, second, third), provider)

    assert len(result.visits) == 3
    assert result.unplaced == ()
    assert result.total_travel_min == 20
    assert validate_routed_day(result, provider, weather_by_date=_weather()).valid


def test_step2_waits_until_attraction_opens() -> None:
    afternoon = _attraction(
        1,
        rules=(TimeRule.from_strings(("01-01", "12-31"), "14:00", "18:00"),),
    )
    result = route_day(_day(afternoon), InMemoryTravelTimeProvider({}))

    assert result.visits[0].arrival_min == 14 * 60


def test_step2_honors_last_entry_and_drops_infeasible_attraction() -> None:
    late_only = _attraction(
        1,
        rules=(
            TimeRule.from_strings(
                ("01-01", "12-31"),
                "09:00",
                "21:00",
                last_entry="10:00",
            ),
        ),
    )
    result = route_day(
        _day(late_only, bounds=(11 * 60, 18 * 60)),
        InMemoryTravelTimeProvider({}),
    )

    assert result.visits == ()
    assert result.unplaced[0].rejection_code is RejectionCode.ROUTING_UNPLACED


def test_step2_c6_buffer_can_force_one_attraction_to_be_dropped() -> None:
    morning = _attraction(
        1,
        rules=(TimeRule.from_strings(("01-01", "12-31"), "09:00", "10:00"),),
    )
    fixed = _attraction(
        2,
        rules=(TimeRule.from_strings(("01-01", "12-31"), "10:00", "10:36"),),
    )
    provider = InMemoryTravelTimeProvider(
        {(1, 2): _travel(1, 2, 30), (2, 1): _travel(2, 1, 30)}
    )

    result = route_day(_day(morning, fixed, bounds=(9 * 60, 12 * 60)), provider)

    assert len(result.visits) == 1
    assert len(result.unplaced) == 1


def test_step2_missing_od_is_not_used_as_a_zero_minute_arc() -> None:
    first, second = _attraction(1), _attraction(2)
    result = route_day(_day(first, second), InMemoryTravelTimeProvider({}))

    assert len(result.visits) == 1
    assert len(result.unplaced) == 1


def test_step2_last_visit_service_must_finish_before_c4_end() -> None:
    attraction = _attraction(1, duration=120)
    result = route_day(
        _day(attraction, bounds=(9 * 60, 10 * 60)),
        InMemoryTravelTimeProvider({}),
    )

    assert result.visits == ()
    assert len(result.unplaced) == 1


def test_step2_s1_notice_uses_planned_partial_duration() -> None:
    attraction = _attraction(1, duration=120)
    result = route_day(_day(attraction), InMemoryTravelTimeProvider({}))

    assert result.visits[0].planned_duration_min == 72
    assert result.visits[0].duration_notice == "实际可玩 72 分钟（建议 120 分钟）"


def test_step2_window_uses_actual_planned_duration_not_default_ratio() -> None:
    attraction = _attraction(
        1,
        rules=(TimeRule.from_strings(("01-01", "12-31"), "09:00", "10:30"),),
        duration=120,
    )
    allocation = DayAllocation(attraction, DAY, DAY, 84)
    day = DayPlan(
        DAY,
        DayTimeBounds(9 * 60 + 20, 12 * 60),
        (allocation,),
        84,
        1,
        PaceLevel.BALANCED,
        "本日节奏适中",
    )

    result = route_day(day, InMemoryTravelTimeProvider({}))

    assert result.visits == ()
    assert len(result.unplaced) == 1


def test_final_validator_rejects_below_60_percent_visit_duration() -> None:
    attraction = _attraction(1, duration=100)
    routed = RoutedDay(
        DAY,
        DayTimeBounds(9 * 60, 12 * 60),
        (RouteVisit(attraction, 9 * 60, 9 * 60 + 59, 59),),
        (),
        0,
        0,
    )

    validation = validate_routed_day(
        routed,
        InMemoryTravelTimeProvider({}),
        weather_by_date=_weather(),
    )

    assert RejectionCode.VISIT_DURATION_INSUFFICIENT in {
        item.code for item in validation.violations
    }


def test_final_validator_detects_c1_c5_c6_and_anchor_violations() -> None:
    outdoor_closed = Attraction(
        1,
        "关闭的室外景点",
        close_days=frozenset({1}),
        time_rules=ALL_DAY,
        data_verified=True,
    )
    second = _attraction(2)
    routed = RoutedDay(
        DAY,
        DayTimeBounds(9 * 60, 12 * 60),
        (
            RouteVisit(outdoor_closed, 8 * 60, 9 * 60, 60),
            RouteVisit(second, 9 * 60, 10 * 60, 60),
        ),
        (),
        0,
        0,
    )
    validation = validate_routed_day(
        routed,
        InMemoryTravelTimeProvider({}),
        weather_by_date=_weather(WeatherSeverity.EXTREME),
    )
    codes = {item.code for item in validation.violations}

    assert not validation.valid
    assert RejectionCode.CLOSED_ON_DATE in codes
    assert RejectionCode.EXTREME_WEATHER_OUTDOOR in codes
    assert RejectionCode.OD_DATA_MISSING in codes
    assert RejectionCode.ANCHOR_VIOLATION in codes
