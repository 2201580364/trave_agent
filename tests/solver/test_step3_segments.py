"""G5 Step 3 tests. Traceability: H3, C2, C4, C6, ADR-0004 P0-2."""

import math
from datetime import UTC, date, datetime

from travel_agent.solver import (
    Attraction,
    DailyWeather,
    DayAllocation,
    DayPlan,
    DayTimeBounds,
    InMemoryTravelTimeProvider,
    MealPlacement,
    MealStatus,
    ODBasis,
    PaceLevel,
    RejectionCode,
    Step1Plan,
    TimeRule,
    TravelTimeResult,
    WeatherBasis,
    WeatherSeverity,
    route_itinerary,
    route_segmented_day,
)

DAY = date(2026, 8, 24)
NEXT_DAY = date(2026, 8, 25)
NOW = datetime(2026, 8, 23, tzinfo=UTC)
DAY_RULE = (TimeRule.from_strings(("01-01", "12-31"), "09:00", "17:30"),)
EVENING_RULE = (TimeRule.from_strings(("01-01", "12-31"), "19:00", "23:00"),)
SHOW_RULE = (TimeRule.from_strings(("01-01", "12-31"), "18:30", "19:00"),)


def _attraction(
    attraction_id: int,
    rules: tuple[TimeRule, ...],
    *,
    duration: int = 60,
) -> Attraction:
    return Attraction(
        attraction_id,
        f"景点 {attraction_id}",
        suggested_duration=duration,
        time_rules=rules,
        data_verified=True,
    )


def _day(
    *attractions: Attraction,
    bounds: tuple[int, int] = (9 * 60, 23 * 60),
) -> DayPlan:
    allocations = tuple(
        DayAllocation(
            item,
            DAY,
            DAY,
            math.ceil(item.suggested_duration * 0.6),
        )
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


def _travel(origin: int, destination: int, minutes: int) -> TravelTimeResult:
    return TravelTimeResult(origin, destination, minutes, ODBasis.GAODE, "v1", NOW)


def _weather(*days: date) -> dict[date, DailyWeather]:
    selected_days = days or (DAY,)
    return {
        day: DailyWeather(day, WeatherBasis.FORECAST, WeatherSeverity.NORMAL)
        for day in selected_days
    }


def test_step3_1830_light_show_is_kept_and_meal_is_scheduled_before_it() -> None:
    daytime = _attraction(1, DAY_RULE)
    light_show = _attraction(2, SHOW_RULE, duration=30)
    provider = InMemoryTravelTimeProvider(
        {(1, 2): _travel(1, 2, 10), (2, 1): _travel(2, 1, 10)}
    )

    result = route_segmented_day(
        _day(daytime, light_show),
        provider,
        weather_by_date=_weather(),
    )

    assert [item.attraction.id for item in result.routed_day.visits] == [1, 2]
    assert result.routed_day.visits[1].arrival_min == 18 * 60 + 30
    assert result.routed_day.visits[0].planned_duration_min == 60
    assert result.routed_day.visits[1].planned_duration_min == 30
    assert result.meal_plan.status is MealStatus.FULL
    assert result.meal_plan.placement is MealPlacement.BETWEEN_SEGMENTS
    assert result.meal_plan.end_min <= 18 * 60 + 30 - 12
    assert result.validation.valid


def test_step3_spreads_two_daytime_visits_across_lunch_before_1830_show() -> None:
    museum = _attraction(1, DAY_RULE, duration=120)
    lake = _attraction(2, DAY_RULE, duration=150)
    light_show = _attraction(3, SHOW_RULE, duration=30)
    provider = InMemoryTravelTimeProvider(
        {
            (1, 2): _travel(1, 2, 10),
            (2, 1): _travel(2, 1, 10),
            (2, 3): _travel(2, 3, 5),
            (3, 2): _travel(3, 2, 5),
            (1, 3): _travel(1, 3, 15),
            (3, 1): _travel(3, 1, 15),
        }
    )

    result = route_segmented_day(
        _day(museum, lake, light_show),
        provider,
        weather_by_date=_weather(),
    )

    visits = result.routed_day.visits
    assert {item.attraction.id for item in visits[:2]} == {1, 2}
    assert visits[2].attraction.id == 3
    assert {item.planned_duration_min for item in visits[:2]} == {120, 150}
    assert visits[1].arrival_min >= 13 * 60
    assert visits[1].leave_min >= 15 * 60
    assert visits[2].arrival_min == 18 * 60 + 30
    assert visits[2].planned_duration_min == 30
    lunch_gap = (
        visits[1].arrival_min
        - visits[1].buffered_travel_from_previous_min
        - visits[0].leave_min
    )
    assert lunch_gap >= 60
    assert result.meal_plan.status is MealStatus.FULL
    assert result.validation.valid


def test_step3_day_spread_falls_back_when_full_duration_would_break_window() -> None:
    first = _attraction(
        1,
        (TimeRule.from_strings(("01-01", "12-31"), "09:00", "11:00"),),
        duration=120,
    )
    second = _attraction(
        2,
        (TimeRule.from_strings(("01-01", "12-31"), "10:30", "12:30"),),
        duration=120,
    )
    provider = InMemoryTravelTimeProvider(
        {(1, 2): _travel(1, 2, 10), (2, 1): _travel(2, 1, 10)}
    )

    result = route_segmented_day(
        _day(first, second, bounds=(9 * 60, 13 * 60)),
        provider,
        weather_by_date=_weather(),
    )

    assert len(result.routed_day.visits) == 2
    assert all(item.planned_duration_min >= 72 for item in result.routed_day.visits)
    assert result.validation.valid


def test_step3_evening_only_1830_show_is_not_forced_to_start_at_1900() -> None:
    light_show = _attraction(1, SHOW_RULE, duration=30)

    result = route_segmented_day(
        _day(light_show),
        InMemoryTravelTimeProvider({}),
        weather_by_date=_weather(),
    )

    assert result.routed_day.visits[0].arrival_min == 18 * 60 + 30
    assert result.meal_plan.status is MealStatus.FULL
    assert result.meal_plan.placement in {
        MealPlacement.BEFORE_FIRST_VISIT,
        MealPlacement.AFTER_LAST_VISIT,
    }


def test_step3_meal_reduces_to_60_minutes_without_dropping_attractions() -> None:
    late_day_rule = (
        TimeRule.from_strings(("01-01", "12-31"), "16:59", "17:36"),
    )
    daytime = _attraction(1, late_day_rule)
    evening = _attraction(2, EVENING_RULE, duration=30)
    provider = InMemoryTravelTimeProvider(
        {(1, 2): _travel(1, 2, 10), (2, 1): _travel(2, 1, 10)}
    )

    result = route_segmented_day(
        _day(daytime, evening, bounds=(17 * 60, 20 * 60)),
        provider,
        weather_by_date=_weather(),
    )

    assert len(result.routed_day.visits) == 2
    assert result.meal_plan.status is MealStatus.REDUCED
    assert result.meal_plan.duration_min == 60
    assert result.meal_plan.notice == "晚餐留白缩短为 60 分钟"


def test_step3_no_meal_slot_keeps_hard_feasible_attractions_and_warns() -> None:
    late_day_rule = (
        TimeRule.from_strings(("01-01", "12-31"), "16:59", "17:36"),
    )
    daytime = _attraction(1, late_day_rule)
    light_show = _attraction(2, SHOW_RULE, duration=30)
    provider = InMemoryTravelTimeProvider(
        {(1, 2): _travel(1, 2, 10), (2, 1): _travel(2, 1, 10)}
    )

    result = route_segmented_day(
        _day(daytime, light_show, bounds=(17 * 60, 19 * 60 + 30)),
        provider,
        weather_by_date=_weather(),
    )

    assert len(result.routed_day.visits) == 2
    assert result.routed_day.unplaced == ()
    assert result.meal_plan.status is MealStatus.UNSCHEDULED
    assert "晚餐时间紧张" in result.meal_plan.notice
    assert result.validation.valid


def test_step3_day_only_route_can_schedule_meal_after_last_visit() -> None:
    all_day = _attraction(
        1,
        (TimeRule.from_strings(("01-01", "12-31"), "09:00", "23:00"),),
    )

    result = route_segmented_day(
        _day(all_day, bounds=(18 * 60, 21 * 60)),
        InMemoryTravelTimeProvider({}),
        weather_by_date=_weather(),
    )

    assert len(result.routed_day.visits) == 1
    assert result.meal_plan.status is MealStatus.FULL
    assert result.meal_plan.placement is MealPlacement.AFTER_LAST_VISIT


def test_step3_missing_cross_segment_od_still_rejects_evening_segment() -> None:
    daytime = _attraction(1, DAY_RULE)
    evening = _attraction(2, EVENING_RULE)

    result = route_segmented_day(
        _day(daytime, evening),
        InMemoryTravelTimeProvider({}),
        weather_by_date=_weather(),
    )

    assert [item.attraction.id for item in result.routed_day.visits] == [1]
    assert result.routed_day.unplaced[-1].attraction.id == 2
    assert result.cross_segment_rejection_code is RejectionCode.OD_DATA_MISSING
    assert result.validation.valid


def test_step3_only_genuine_c6_failure_rejects_evening_segment() -> None:
    all_day = _attraction(
        1,
        (TimeRule.from_strings(("01-01", "12-31"), "09:00", "23:00"),),
    )
    light_show = _attraction(2, SHOW_RULE, duration=30)
    provider = InMemoryTravelTimeProvider(
        {(1, 2): _travel(1, 2, 30), (2, 1): _travel(2, 1, 30)}
    )

    result = route_segmented_day(
        _day(all_day, light_show, bounds=(18 * 60, 21 * 60)),
        provider,
        weather_by_date=_weather(),
    )

    assert len(result.routed_day.visits) == 1
    assert result.cross_segment_rejection_code is RejectionCode.TRANSIT_INFEASIBLE


def test_step3_cross_segment_hard_failure_enters_cross_day_recovery() -> None:
    daytime = _attraction(1, DAY_RULE)
    evening = _attraction(2, EVENING_RULE)
    first_day = _day(daytime, evening)
    second_day = DayPlan(
        NEXT_DAY,
        DayTimeBounds(9 * 60, 23 * 60),
        (),
        0,
        0,
        PaceLevel.RELAXED,
        "本日节奏偏松",
    )
    step1 = Step1Plan((first_day, second_day), (), ())

    result = route_itinerary(
        step1,
        InMemoryTravelTimeProvider({}),
        weather_by_date=_weather(DAY, NEXT_DAY),
    )

    assert [len(day.visits) for day in result.days] == [1, 1]
    assert result.reassignments[0].attraction.id == 2
    assert result.reassignments[0].to_date == NEXT_DAY
    assert result.segmented_days[1].meal_plan.status is MealStatus.FULL
    assert result.valid
