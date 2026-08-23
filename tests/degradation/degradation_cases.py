"""Executable safe-degradation scenarios.

Traceability: H3, C1, C2, C4, C5, C6, S1, S6, Gate 6.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Callable

from travel_agent.solver import (
    ApproximateTravelTimeProvider,
    Attraction,
    AttractionPreference,
    Coordinate,
    DailyWeather,
    DayAllocation,
    DayPlan,
    DayTimeBounds,
    DegradationCode,
    InMemoryTravelTimeProvider,
    MealStatus,
    ODBasis,
    PaceLevel,
    RejectionCode,
    Step1Plan,
    TimeRule,
    TravelTimeResult,
    TripTimeAnchors,
    WeatherBasis,
    WeatherSeverity,
    assign_days,
    evaluate_itinerary_degradation,
    evaluate_solver_quality,
    route_itinerary,
)


MONDAY = date(2026, 8, 24)
TUESDAY = date(2026, 8, 25)
NOW = datetime(2026, 8, 23, tzinfo=UTC)
ALL_DAY = (TimeRule.from_strings(("01-01", "12-31"), "09:00", "21:00"),)


@dataclass(frozen=True, slots=True)
class DegradationCaseResult:
    case_id: str
    title: str
    passed: bool
    constraints: tuple[str, ...]
    details: dict[str, object]


def _attraction(
    attraction_id: int,
    *,
    name: str | None = None,
    duration: int = 120,
    rules: tuple[TimeRule, ...] = ALL_DAY,
    indoor: bool = False,
    close_days: frozenset[int] = frozenset(),
) -> Attraction:
    return Attraction(
        attraction_id,
        name or f"降级景点 {attraction_id}",
        close_days=close_days,
        suggested_duration=duration,
        time_rules=rules,
        is_indoor=indoor,
        energy_level=1 + attraction_id % 5,
        data_verified=True,
    )


def _weather(
    severities: dict[date, WeatherSeverity],
) -> dict[date, DailyWeather]:
    return {
        day: DailyWeather(day, WeatherBasis.FORECAST, severity)
        for day, severity in severities.items()
    }


def _provider(attractions: tuple[Attraction, ...]) -> ApproximateTravelTimeProvider:
    return ApproximateTravelTimeProvider(
        {
            attraction.id: Coordinate(
                30.20 + (index // 6) * 0.01,
                120.10 + (index % 6) * 0.01,
            )
            for index, attraction in enumerate(attractions)
        },
        speed_kmh=24,
        detour_ratio=1.3,
        data_version="gate6-degradation",
        fetched_at=NOW,
    )


def excessive_selection_is_conserved_and_explained() -> DegradationCaseResult:
    attractions = tuple(_attraction(index, duration=300) for index in range(1, 31))
    weather = _weather(
        {MONDAY: WeatherSeverity.NORMAL, TUESDAY: WeatherSeverity.NORMAL}
    )
    step1 = assign_days(
        tuple(AttractionPreference(item, MONDAY) for item in attractions),
        trip_dates=(MONDAY, TUESDAY),
        weather_by_date=weather,
        anchors=TripTimeAnchors(9 * 60, 0, 21 * 60, 0, 0),
    )
    itinerary = route_itinerary(step1, _provider(attractions), weather_by_date=weather)
    quality = evaluate_solver_quality(itinerary, attractions)
    degradation = evaluate_itinerary_degradation(
        itinerary,
        quality,
        input_count=len(attractions),
        day_count=2,
    )
    codes = {item.code for item in degradation.notices}
    passed = (
        quality.gate_passed
        and quality.accounting.conserved
        and bool(itinerary.unplaced)
        and degradation.explainable
        and DegradationCode.HIGH_ATTRACTION_COUNT in codes
        and DegradationCode.UNPLACED_ATTRACTIONS in codes
    )
    return DegradationCaseResult(
        "DEG-01",
        "30 个景点两天容量不足时不静默丢弃",
        passed,
        ("C2", "C4", "C6", "S6"),
        {
            "scheduled": quality.accounting.scheduled_count,
            "unplaced": quality.accounting.unplaced_count,
            "notice_codes": sorted(item.value for item in codes),
        },
    )


def all_dates_closed_are_traceable() -> DegradationCaseResult:
    attraction = _attraction(31, close_days=frozenset({1, 2}))
    weather = _weather(
        {MONDAY: WeatherSeverity.NORMAL, TUESDAY: WeatherSeverity.NORMAL}
    )
    step1 = assign_days(
        (AttractionPreference(attraction, MONDAY),),
        trip_dates=(MONDAY, TUESDAY),
        weather_by_date=weather,
        anchors=TripTimeAnchors(9 * 60, 0, 21 * 60, 0, 0),
    )
    itinerary = route_itinerary(
        step1,
        InMemoryTravelTimeProvider({}),
        weather_by_date=weather,
    )
    quality = evaluate_solver_quality(itinerary, (attraction,))
    item = itinerary.unplaced[0]
    reasons = [attempt.rejection_codes for attempt in item.attempts]
    passed = (
        quality.gate_passed
        and item.rejection_code is RejectionCode.NO_AVAILABLE_DATE
        and len(reasons) == 2
        and all(reason == (RejectionCode.CLOSED_ON_DATE,) for reason in reasons)
    )
    return DegradationCaseResult(
        "DEG-02",
        "所有日期闭馆时保留逐日 C1 原因",
        passed,
        ("C1",),
        {"final_reason": item.rejection_code.value, "attempt_count": len(reasons)},
    )


def all_dates_extreme_weather_are_traceable() -> DegradationCaseResult:
    attraction = _attraction(32)
    weather = _weather(
        {MONDAY: WeatherSeverity.EXTREME, TUESDAY: WeatherSeverity.EXTREME}
    )
    step1 = assign_days(
        (AttractionPreference(attraction, MONDAY),),
        trip_dates=(MONDAY, TUESDAY),
        weather_by_date=weather,
        anchors=TripTimeAnchors(9 * 60, 0, 21 * 60, 0, 0),
    )
    itinerary = route_itinerary(
        step1,
        InMemoryTravelTimeProvider({}),
        weather_by_date=weather,
    )
    quality = evaluate_solver_quality(itinerary, (attraction,))
    item = itinerary.unplaced[0]
    passed = (
        quality.gate_passed
        and item.rejection_code is RejectionCode.NO_WEATHER_SAFE_DATE
        and len(item.attempts) == 2
        and all(
            attempt.rejection_codes == (RejectionCode.EXTREME_WEATHER_OUTDOOR,)
            for attempt in item.attempts
        )
    )
    return DegradationCaseResult(
        "DEG-03",
        "所有日期极端天气时室外景点安全降级",
        passed,
        ("C5",),
        {"final_reason": item.rejection_code.value},
    )


def missing_od_never_becomes_zero_travel() -> DegradationCaseResult:
    attractions = tuple(_attraction(index) for index in range(33, 36))
    weather = _weather({MONDAY: WeatherSeverity.NORMAL})
    step1 = assign_days(
        tuple(AttractionPreference(item, MONDAY) for item in attractions),
        trip_dates=(MONDAY,),
        weather_by_date=weather,
        anchors=TripTimeAnchors(9 * 60, 0, 21 * 60, 0, 0),
    )
    itinerary = route_itinerary(
        step1,
        InMemoryTravelTimeProvider({}),
        weather_by_date=weather,
    )
    quality = evaluate_solver_quality(itinerary, attractions)
    passed = (
        quality.gate_passed
        and quality.accounting.scheduled_count == 1
        and quality.accounting.unplaced_count == 2
        and itinerary.days[0].total_travel_min == 0
        and all(
            item.rejection_code is RejectionCode.ROUTING_UNPLACED
            for item in itinerary.unplaced
        )
    )
    return DegradationCaseResult(
        "DEG-04",
        "单日大面积 OD 缺失时禁止伪造零耗时串联",
        passed,
        ("C6",),
        {
            "scheduled": quality.accounting.scheduled_count,
            "unplaced": quality.accounting.unplaced_count,
        },
    )


def evening_show_cannot_break_departure_anchor() -> DegradationCaseResult:
    show = _attraction(
        36,
        rules=(TimeRule.from_strings(("01-01", "12-31"), "18:30", "19:00"),),
        duration=30,
    )
    weather = _weather({MONDAY: WeatherSeverity.NORMAL})
    step1 = assign_days(
        (AttractionPreference(show, MONDAY),),
        trip_dates=(MONDAY,),
        weather_by_date=weather,
        anchors=TripTimeAnchors(9 * 60, 0, 19 * 60, 30, 30),
    )
    itinerary = route_itinerary(
        step1,
        InMemoryTravelTimeProvider({}),
        weather_by_date=weather,
    )
    quality = evaluate_solver_quality(itinerary, (show,))
    item = itinerary.unplaced[0]
    passed = (
        quality.gate_passed
        and not itinerary.days[0].visits
        and item.rejection_code is RejectionCode.NO_AVAILABLE_DATE
        and RejectionCode.ARRIVAL_AFTER_LATEST_ARRIVAL
        in item.attempts[0].rejection_codes
    )
    return DegradationCaseResult(
        "DEG-05",
        "晚间固定场次不得突破末日离开锚点",
        passed,
        ("C2", "C4"),
        {"final_reason": item.rejection_code.value},
    )


def no_dinner_slot_keeps_hard_feasible_visits() -> DegradationCaseResult:
    daytime = _attraction(
        37,
        rules=(TimeRule.from_strings(("01-01", "12-31"), "16:59", "17:36"),),
        duration=60,
    )
    show = _attraction(
        38,
        rules=(TimeRule.from_strings(("01-01", "12-31"), "18:30", "19:00"),),
        duration=30,
    )
    allocations = tuple(
        DayAllocation(
            item,
            MONDAY,
            MONDAY,
            math.ceil(item.suggested_duration * 0.6),
        )
        for item in (daytime, show)
    )
    step1 = Step1Plan(
        (
            DayPlan(
                MONDAY,
                DayTimeBounds(17 * 60, 19 * 60 + 30),
                allocations,
                sum(item.required_duration_min for item in allocations),
                2,
                PaceLevel.BALANCED,
                "本日节奏适中",
            ),
        ),
        (),
        (),
    )
    travel = TravelTimeResult(37, 38, 10, ODBasis.GAODE, "fixture", NOW)
    reverse = TravelTimeResult(38, 37, 10, ODBasis.GAODE, "fixture", NOW)
    itinerary = route_itinerary(
        step1,
        InMemoryTravelTimeProvider({(37, 38): travel, (38, 37): reverse}),
        weather_by_date=_weather({MONDAY: WeatherSeverity.NORMAL}),
    )
    quality = evaluate_solver_quality(itinerary, (daytime, show))
    degradation = evaluate_itinerary_degradation(
        itinerary,
        quality,
        input_count=2,
        day_count=1,
    )
    meal = itinerary.segmented_days[0].meal_plan
    passed = (
        quality.gate_passed
        and quality.accounting.scheduled_count == 2
        and meal.status is MealStatus.UNSCHEDULED
        and degradation.explainable
        and any(
            item.code is DegradationCode.DINNER_UNSCHEDULED
            for item in degradation.notices
        )
    )
    return DegradationCaseResult(
        "DEG-06",
        "晚餐无空档时保留硬可行景点并提示",
        passed,
        ("C2", "C4", "C6", "S1"),
        {"meal_status": meal.status.value, "scheduled": 2},
    )


CASES: tuple[Callable[[], DegradationCaseResult], ...] = (
    excessive_selection_is_conserved_and_explained,
    all_dates_closed_are_traceable,
    all_dates_extreme_weather_are_traceable,
    missing_od_never_becomes_zero_travel,
    evening_show_cannot_break_departure_anchor,
    no_dinner_slot_keeps_hard_feasible_visits,
)


def run_degradation_cases() -> tuple[DegradationCaseResult, ...]:
    return tuple(case() for case in CASES)
