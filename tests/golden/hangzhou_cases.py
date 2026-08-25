"""Hangzhou Golden Cases derived from public travel guidance snapshots.

The web sources justify the scenario shape. Exact minutes, weather failures and
missing OD edges are explicit deterministic test normalizations, not live facts.
Traceability: H2, H3, C1, C2, C4, C5, C6, S1, S2, Gate 6.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Callable

from travel_agent.solver import (
    ApproximateTravelTimeProvider,
    Attraction,
    AttractionPreference,
    Coordinate,
    DailyWeather,
    InMemoryTravelTimeProvider,
    MealStatus,
    RejectionCode,
    TimeRule,
    TripTimeAnchors,
    WeatherBasis,
    WeatherSeverity,
    assign_days,
    evaluate_solver_quality,
    route_itinerary,
)


MONDAY = date(2026, 8, 24)
TUESDAY = date(2026, 8, 25)
WEDNESDAY = date(2026, 8, 26)
SNAPSHOT_AT = datetime(2026, 8, 23, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class GoldenCaseResult:
    case_id: str
    title: str
    passed: bool
    constraints: tuple[str, ...]
    evidence: tuple[str, ...]
    details: dict[str, object]


def _rule(open_time: str, close_time: str, last_entry: str | None = None) -> tuple[TimeRule, ...]:
    return (
        TimeRule.from_strings(
            ("01-01", "12-31"),
            open_time,
            close_time,
            last_entry,
        ),
    )


def _attraction(
    attraction_id: int,
    name: str,
    *,
    rules: tuple[TimeRule, ...] | None = None,
    duration: int = 90,
    energy: int = 2,
    indoor: bool = False,
    close_days: frozenset[int] = frozenset(),
    always_open: bool = False,
) -> Attraction:
    return Attraction(
        attraction_id,
        name,
        close_days=close_days,
        suggested_duration=duration,
        time_rules=rules or (),
        is_always_open=always_open,
        is_indoor=indoor,
        energy_level=energy,
        data_verified=True,
    )


def _weather(
    severity_by_date: dict[date, WeatherSeverity],
) -> dict[date, DailyWeather]:
    return {
        day: DailyWeather(day, WeatherBasis.FORECAST, severity, severity.value)
        for day, severity in severity_by_date.items()
    }


def _provider(coordinates: dict[int, Coordinate]) -> ApproximateTravelTimeProvider:
    return ApproximateTravelTimeProvider(
        coordinates,
        speed_kmh=24,
        detour_ratio=1.35,
        data_version="golden-hangzhou-2026-08-23",
        fetched_at=SNAPSHOT_AT,
    )


def _scheduled_dates(itinerary: object) -> dict[int, str]:
    return {
        visit.attraction.id: day.visit_date.isoformat()
        for day in itinerary.days
        for visit in day.visits
    }


def museum_closure_moves_to_tuesday() -> GoldenCaseResult:
    museum = _attraction(
        1,
        "浙江省博物馆（测试归一化）",
        rules=_rule("09:00", "17:00", "16:30"),
        duration=120,
        indoor=True,
        close_days=frozenset({1}),
    )
    west_lake = _attraction(2, "西湖湖滨", always_open=True, duration=120, energy=3)
    attractions = (museum, west_lake)
    weather = _weather({MONDAY: WeatherSeverity.NORMAL, TUESDAY: WeatherSeverity.NORMAL})
    step1 = assign_days(
        (
            AttractionPreference(museum, MONDAY),
            AttractionPreference(west_lake, MONDAY),
        ),
        trip_dates=(MONDAY, TUESDAY),
        weather_by_date=weather,
        anchors=TripTimeAnchors(9 * 60, 0, 21 * 60, 0, 0),
    )
    itinerary = route_itinerary(
        step1,
        _provider({1: Coordinate(30.2525, 120.1495), 2: Coordinate(30.2590, 120.1650)}),
        weather_by_date=weather,
    )
    quality = evaluate_solver_quality(itinerary, attractions)
    dates = _scheduled_dates(itinerary)
    passed = quality.gate_passed and dates[1] == TUESDAY.isoformat()
    return GoldenCaseResult(
        "HZ-GC-01",
        "周一闭馆博物馆自动移至周二",
        passed,
        ("C1", "C2", "C6"),
        ("SRC-MUSEUM-HOURS", "SRC-HANGZHOU-GUIDE"),
        {"scheduled_dates": dates, "quality_gate": quality.gate_passed},
    )


def late_arrival_keeps_morning_site_unplaced() -> GoldenCaseResult:
    morning_site = _attraction(
        3,
        "灵隐寺上午游览",
        rules=_rule("07:00", "17:00", "16:00"),
        duration=180,
        energy=4,
    )
    lakefront = _attraction(4, "湖滨傍晚散步", always_open=True, duration=90)
    attractions = (morning_site, lakefront)
    weather = _weather({MONDAY: WeatherSeverity.NORMAL})
    step1 = assign_days(
        (
            AttractionPreference(morning_site, MONDAY),
            AttractionPreference(lakefront, MONDAY),
        ),
        trip_dates=(MONDAY,),
        weather_by_date=weather,
        anchors=TripTimeAnchors(14 * 60, 90, 22 * 60, 60, 30),
    )
    itinerary = route_itinerary(
        step1,
        _provider({3: Coordinate(30.2409, 120.1022), 4: Coordinate(30.2580, 120.1650)}),
        weather_by_date=weather,
    )
    quality = evaluate_solver_quality(itinerary, attractions)
    unplaced = {item.attraction.id: item.rejection_code.value for item in itinerary.unplaced}
    scheduled = _scheduled_dates(itinerary)
    passed = (
        quality.gate_passed
        and 3 in unplaced
        and unplaced[3] == RejectionCode.NO_AVAILABLE_DATE.value
        and 4 in scheduled
        and itinerary.days[0].visits[0].arrival_min >= 15 * 60 + 30
    )
    return GoldenCaseResult(
        "HZ-GC-02",
        "下午抵达不强塞需要半天的上午景点",
        passed,
        ("C2", "C4"),
        ("SRC-LINGYIN-OFFICIAL", "SRC-HANGZHOU-GUIDE"),
        {"scheduled_dates": scheduled, "unplaced": unplaced},
    )


def extreme_weather_moves_outdoor_but_keeps_indoor() -> GoldenCaseResult:
    boat = _attraction(5, "西湖游船", rules=_rule("08:30", "17:00"), duration=90)
    museum = _attraction(
        6,
        "室内博物馆",
        rules=_rule("09:00", "17:00", "16:30"),
        duration=120,
        indoor=True,
    )
    attractions = (boat, museum)
    weather = _weather({MONDAY: WeatherSeverity.EXTREME, TUESDAY: WeatherSeverity.NORMAL})
    step1 = assign_days(
        (AttractionPreference(boat, MONDAY), AttractionPreference(museum, MONDAY)),
        trip_dates=(MONDAY, TUESDAY),
        weather_by_date=weather,
        anchors=TripTimeAnchors(9 * 60, 0, 21 * 60, 0, 0),
    )
    itinerary = route_itinerary(
        step1,
        _provider({5: Coordinate(30.2510, 120.1500), 6: Coordinate(30.2525, 120.1495)}),
        weather_by_date=weather,
    )
    quality = evaluate_solver_quality(itinerary, attractions)
    dates = _scheduled_dates(itinerary)
    passed = (
        quality.gate_passed
        and dates[5] == TUESDAY.isoformat()
        and dates[6] == MONDAY.isoformat()
    )
    return GoldenCaseResult(
        "HZ-GC-03",
        "极端天气迁移室外项目并保留室内项目",
        passed,
        ("C5", "C6"),
        ("SRC-WESTLAKE-GUIDE",),
        {"scheduled_dates": dates, "weather": {"Monday": "extreme", "Tuesday": "normal"}},
    )


def fixed_evening_show_survives_dinner_block() -> GoldenCaseResult:
    lakefront = _attraction(7, "西湖湖滨日间游览", rules=_rule("09:00", "17:30"), duration=120)
    show = _attraction(8, "湖滨固定晚间表演", rules=_rule("18:30", "19:00"), duration=30)
    attractions = (lakefront, show)
    weather = _weather({MONDAY: WeatherSeverity.NORMAL})
    step1 = assign_days(
        (AttractionPreference(lakefront, MONDAY), AttractionPreference(show, MONDAY)),
        trip_dates=(MONDAY,),
        weather_by_date=weather,
        anchors=TripTimeAnchors(9 * 60, 0, 21 * 60, 0, 0),
    )
    itinerary = route_itinerary(
        step1,
        _provider({7: Coordinate(30.2570, 120.1600), 8: Coordinate(30.2590, 120.1660)}),
        weather_by_date=weather,
    )
    quality = evaluate_solver_quality(itinerary, attractions)
    visits = {visit.attraction.id: visit for visit in itinerary.days[0].visits}
    meal = itinerary.segmented_days[0].meal_plan
    passed = (
        quality.gate_passed
        and visits[8].arrival_min == 18 * 60 + 30
        and meal.status in {MealStatus.FULL, MealStatus.REDUCED}
    )
    return GoldenCaseResult(
        "HZ-GC-04",
        "固定晚间场次不被晚餐留白挤掉",
        passed,
        ("C2", "C4", "C6", "S1"),
        ("SRC-FOUNTAIN-GUIDE",),
        {"show_arrival_min": visits[8].arrival_min, "meal_status": meal.status.value},
    )


def missing_od_enters_cross_day_recovery() -> GoldenCaseResult:
    first = _attraction(9, "西湖西侧景点", rules=_rule("09:00", "18:00"), duration=120)
    second = _attraction(10, "西湖东侧景点", rules=_rule("09:00", "18:00"), duration=120)
    attractions = (first, second)
    weather = _weather({MONDAY: WeatherSeverity.NORMAL, TUESDAY: WeatherSeverity.NORMAL})
    step1 = assign_days(
        (AttractionPreference(first, MONDAY), AttractionPreference(second, MONDAY)),
        trip_dates=(MONDAY, TUESDAY),
        weather_by_date=weather,
        anchors=TripTimeAnchors(9 * 60, 0, 21 * 60, 0, 0),
    )
    itinerary = route_itinerary(
        step1,
        InMemoryTravelTimeProvider({}),
        weather_by_date=weather,
    )
    quality = evaluate_solver_quality(itinerary, attractions)
    day_counts = [len(day.visits) for day in itinerary.days]
    passed = (
        quality.gate_passed
        and day_counts == [1, 1]
        and len(itinerary.reassignments) == 1
        and not itinerary.unplaced
    )
    return GoldenCaseResult(
        "HZ-GC-05",
        "OD 缺失禁止零耗时串联并触发跨天回退",
        passed,
        ("C6",),
        ("SRC-WESTLAKE-GUIDE",),
        {"day_visit_counts": day_counts, "reassignments": len(itinerary.reassignments)},
    )


def three_day_realistic_mix_is_conserved() -> GoldenCaseResult:
    attractions = (
        _attraction(
            11,
            "灵隐寺",
            rules=_rule("07:00", "17:30", "16:30"),
            duration=180,
            energy=4,
        ),
        _attraction(
            12,
            "飞来峰",
            rules=_rule("07:00", "17:30", "16:30"),
            duration=120,
            energy=4,
        ),
        _attraction(13, "西湖湖滨", always_open=True, duration=150, energy=3),
        _attraction(
            14,
            "浙江省博物馆",
            rules=_rule("09:00", "17:00", "16:30"),
            duration=120,
            indoor=True,
            close_days=frozenset({1}),
        ),
        _attraction(
            15,
            "雷峰塔",
            rules=_rule("08:00", "19:00", "18:30"),
            duration=90,
            energy=3,
        ),
        _attraction(16, "河坊街", rules=_rule("09:00", "22:00"), duration=120, energy=2),
        _attraction(17, "湖滨晚间表演", rules=_rule("19:30", "19:50"), duration=20),
    )
    preferences = (
        AttractionPreference(attractions[0], MONDAY),
        AttractionPreference(attractions[1], MONDAY),
        AttractionPreference(attractions[2], MONDAY),
        AttractionPreference(attractions[3], MONDAY),
        AttractionPreference(attractions[4], TUESDAY),
        AttractionPreference(attractions[5], WEDNESDAY),
        AttractionPreference(attractions[6], WEDNESDAY),
    )
    weather = _weather(
        {
            MONDAY: WeatherSeverity.NORMAL,
            TUESDAY: WeatherSeverity.NORMAL,
            WEDNESDAY: WeatherSeverity.ADVISORY,
        }
    )
    step1 = assign_days(
        preferences,
        trip_dates=(MONDAY, TUESDAY, WEDNESDAY),
        weather_by_date=weather,
        anchors=TripTimeAnchors(11 * 60, 60, 22 * 60, 60, 30),
    )
    coordinates = {
        11: Coordinate(30.2409, 120.1022),
        12: Coordinate(30.2417, 120.1040),
        13: Coordinate(30.2590, 120.1650),
        14: Coordinate(30.2525, 120.1495),
        15: Coordinate(30.2301, 120.1484),
        16: Coordinate(30.2420, 120.1690),
        17: Coordinate(30.2590, 120.1660),
    }
    itinerary = route_itinerary(step1, _provider(coordinates), weather_by_date=weather)
    quality = evaluate_solver_quality(itinerary, attractions)
    dates = _scheduled_dates(itinerary)
    passed = (
        quality.gate_passed
        and quality.accounting.scheduled_count == len(attractions)
        and dates[14] != MONDAY.isoformat()
        and dates[17] == WEDNESDAY.isoformat()
    )
    return GoldenCaseResult(
        "HZ-GC-06",
        "三日杭州混合行程端到端守恒",
        passed,
        ("C1", "C2", "C4", "C5", "C6", "S1", "S2"),
        ("SRC-LINGYIN-OFFICIAL", "SRC-WESTLAKE-GUIDE", "SRC-FOUNTAIN-GUIDE"),
        {
            "scheduled_dates": dates,
            "scheduled_count": quality.accounting.scheduled_count,
            "hard_constraint_violations": quality.hard_constraint_violations,
        },
    )


def daytime_visits_are_spread_before_fixed_evening_show() -> GoldenCaseResult:
    museum = _attraction(
        18,
        "浙江省博物馆（日内展开样例）",
        rules=_rule("09:00", "17:00", "16:30"),
        duration=120,
        indoor=True,
    )
    lakefront = _attraction(
        19,
        "西湖湖滨（日内展开样例）",
        rules=_rule("09:00", "17:30"),
        duration=150,
        energy=3,
    )
    show = _attraction(
        20,
        "湖滨喷泉灯光秀（18:30 场次）",
        rules=_rule("18:30", "19:00"),
        duration=30,
    )
    attractions = (museum, lakefront, show)
    weather = _weather({MONDAY: WeatherSeverity.NORMAL})
    step1 = assign_days(
        tuple(AttractionPreference(item, MONDAY) for item in attractions),
        trip_dates=(MONDAY,),
        weather_by_date=weather,
        anchors=TripTimeAnchors(9 * 60, 45, 21 * 60, 0, 0),
    )
    itinerary = route_itinerary(
        step1,
        _provider(
            {
                18: Coordinate(30.2525, 120.1495),
                19: Coordinate(30.2590, 120.1650),
                20: Coordinate(30.2592, 120.1662),
            }
        ),
        weather_by_date=weather,
    )
    quality = evaluate_solver_quality(itinerary, attractions)
    visits = itinerary.days[0].visits
    first, second, fixed_show = visits
    lunch_gap = (
        second.arrival_min
        - second.buffered_travel_from_previous_min
        - first.leave_min
    )
    meal = itinerary.segmented_days[0].meal_plan
    passed = (
        quality.gate_passed
        and {first.attraction.id, second.attraction.id} == {18, 19}
        and first.planned_duration_min == first.attraction.suggested_duration
        and second.planned_duration_min == second.attraction.suggested_duration
        and second.arrival_min >= 13 * 60
        and second.leave_min >= 15 * 60
        and lunch_gap >= 60
        and fixed_show.attraction.id == 20
        and fixed_show.arrival_min == 18 * 60 + 30
        and fixed_show.planned_duration_min == 30
        and meal.status is MealStatus.FULL
    )
    return GoldenCaseResult(
        "HZ-GC-07",
        "两个日间景点覆盖上午和下午，18:30 固定表演与晚餐保留",
        passed,
        ("C2", "C4", "C6", "S1", "LUNCH_BLOCK", "DINNER_BLOCK", "DAY_SPREAD"),
        ("SRC-MUSEUM-HOURS", "SRC-WESTLAKE-GUIDE", "SRC-FOUNTAIN-GUIDE"),
        {
            "visit_times": {
                str(visit.attraction.id): {
                    "arrival_min": visit.arrival_min,
                    "leave_min": visit.leave_min,
                    "planned_duration_min": visit.planned_duration_min,
                }
                for visit in visits
            },
            "lunch_gap_min": lunch_gap,
            "dinner_status": meal.status.value,
            "hard_constraint_violations": quality.hard_constraint_violations,
        },
    )


CASES: tuple[Callable[[], GoldenCaseResult], ...] = (
    museum_closure_moves_to_tuesday,
    late_arrival_keeps_morning_site_unplaced,
    extreme_weather_moves_outdoor_but_keeps_indoor,
    fixed_evening_show_survives_dinner_block,
    missing_od_enters_cross_day_recovery,
    three_day_realistic_mix_is_conserved,
    daytime_visits_are_spread_before_fixed_evening_show,
)


def run_hangzhou_golden_cases() -> tuple[GoldenCaseResult, ...]:
    return tuple(case() for case in CASES)
