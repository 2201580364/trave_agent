"""Whole-itinerary recovery tests. Traceability: H3, C1, C2, C4, C5, C6."""

from datetime import date
from typing import Any

from travel_agent.solver import (
    Attraction,
    DailyWeather,
    DayAllocation,
    DayPlan,
    DayTimeBounds,
    InMemoryTravelTimeProvider,
    PaceLevel,
    RejectionCode,
    Step1Plan,
    TimeRule,
    UnplacedAttraction,
    WeatherBasis,
    WeatherSeverity,
    route_itinerary,
)


MONDAY = date(2026, 8, 24)
TUESDAY = date(2026, 8, 25)
WEDNESDAY = date(2026, 8, 26)
ALL_DAY = (TimeRule.from_strings(("01-01", "12-31"), "09:00", "18:00"),)


def _attraction(attraction_id: int, **kwargs: Any) -> Attraction:
    time_rules = kwargs.pop("time_rules", ALL_DAY)
    return Attraction(
        attraction_id,
        f"景点 {attraction_id}",
        suggested_duration=60,
        time_rules=time_rules,
        data_verified=True,
        **kwargs,
    )


def _allocation(attraction: Attraction, day: date) -> DayAllocation:
    return DayAllocation(attraction, day, day, 36)


def _day(day: date, *allocations: DayAllocation) -> DayPlan:
    return DayPlan(
        day,
        DayTimeBounds(9 * 60, 18 * 60),
        tuple(allocations),
        sum(item.required_duration_min for item in allocations),
        sum(item.attraction.energy_level for item in allocations),
        PaceLevel.BALANCED,
        "本日节奏适中",
    )


def _weather(*days: date) -> dict[date, DailyWeather]:
    return {
        day: DailyWeather(day, WeatherBasis.FORECAST, WeatherSeverity.NORMAL)
        for day in days
    }


def test_itinerary_moves_step2_drop_to_empty_day() -> None:
    first, second = _attraction(1), _attraction(2)
    step1 = Step1Plan(
        (_day(MONDAY, _allocation(first, MONDAY), _allocation(second, MONDAY)), _day(TUESDAY)),
        (),
        (),
    )

    result = route_itinerary(
        step1,
        InMemoryTravelTimeProvider({}),
        weather_by_date=_weather(MONDAY, TUESDAY),
    )

    assert [len(day.visits) for day in result.days] == [1, 1]
    assert len(result.reassignments) == 1
    assert result.reassignments[0].to_date == TUESDAY
    assert result.unplaced == ()
    assert result.valid


def test_itinerary_skips_closed_target_and_uses_next_date() -> None:
    future_rule = (TimeRule.from_strings(("08-25", "08-26"), "09:00", "18:00"),)
    fixed = _attraction(1)
    movable = _attraction(
        2,
        close_days=frozenset({2}),
        time_rules=future_rule,
    )
    step1 = Step1Plan(
        (
            _day(MONDAY, _allocation(fixed, MONDAY), _allocation(movable, MONDAY)),
            _day(TUESDAY),
            _day(WEDNESDAY),
        ),
        (),
        (),
    )

    result = route_itinerary(
        step1,
        InMemoryTravelTimeProvider({}),
        weather_by_date=_weather(MONDAY, TUESDAY, WEDNESDAY),
    )

    assert result.reassignments[0].to_date == WEDNESDAY


def test_itinerary_records_every_failed_reassignment_attempt() -> None:
    future_rule = (TimeRule.from_strings(("08-25", "08-26"), "09:00", "18:00"),)
    fixed = _attraction(1)
    blocked = _attraction(
        2,
        close_days=frozenset({2, 3}),
        time_rules=future_rule,
    )
    step1 = Step1Plan(
        (
            _day(MONDAY, _allocation(fixed, MONDAY), _allocation(blocked, MONDAY)),
            _day(TUESDAY),
            _day(WEDNESDAY),
        ),
        (),
        (),
    )

    result = route_itinerary(
        step1,
        InMemoryTravelTimeProvider({}),
        weather_by_date=_weather(MONDAY, TUESDAY, WEDNESDAY),
    )

    assert len(result.unplaced) == 1
    assert [item.visit_date for item in result.unplaced[0].attempts] == [TUESDAY, WEDNESDAY]
    assert all(
        item.rejection_codes == (RejectionCode.CLOSED_ON_DATE,)
        for item in result.unplaced[0].attempts
    )


def test_itinerary_does_not_move_candidate_by_displacing_existing_target() -> None:
    tuesday_rule = (TimeRule.from_strings(("08-25", "08-25"), "09:00", "18:00"),)
    source_fixed, candidate, target_fixed = (
        _attraction(1),
        _attraction(2, time_rules=tuesday_rule),
        _attraction(3),
    )
    provider = InMemoryTravelTimeProvider({})
    step1 = Step1Plan(
        (
            _day(
                MONDAY,
                _allocation(source_fixed, MONDAY),
                _allocation(candidate, MONDAY),
            ),
            _day(TUESDAY, _allocation(target_fixed, TUESDAY)),
        ),
        (),
        (),
    )

    result = route_itinerary(
        step1,
        provider,
        weather_by_date=_weather(MONDAY, TUESDAY),
    )

    assert len(result.days[0].visits) == 1
    assert len(result.days[1].visits) == 1
    assert result.reassignments == ()
    assert result.unplaced[0].attempts[0].rejection_codes == (
        RejectionCode.REASSIGNMENT_DISPLACES_EXISTING,
    )


def test_itinerary_output_is_deterministic() -> None:
    first, second = _attraction(1), _attraction(2)
    step1 = Step1Plan(
        (
            _day(MONDAY, _allocation(first, MONDAY), _allocation(second, MONDAY)),
            _day(TUESDAY),
        ),
        (),
        (),
    )
    provider = InMemoryTravelTimeProvider({})
    weather = _weather(MONDAY, TUESDAY)

    assert route_itinerary(step1, provider, weather_by_date=weather) == route_itinerary(
        step1,
        provider,
        weather_by_date=weather,
    )


def test_itinerary_preserves_step1_unplaced_attraction() -> None:
    attraction = _attraction(1)
    step1 = Step1Plan(
        (_day(MONDAY),),
        (
            UnplacedAttraction(
                attraction,
                MONDAY,
                RejectionCode.NO_AVAILABLE_DATE,
            ),
        ),
        (),
    )

    result = route_itinerary(
        step1,
        InMemoryTravelTimeProvider({}),
        weather_by_date=_weather(MONDAY),
    )

    assert result.unplaced[0].attraction.id == 1
    assert result.unplaced[0].rejection_code is RejectionCode.NO_AVAILABLE_DATE
