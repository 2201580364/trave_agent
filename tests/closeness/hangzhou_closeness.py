"""Hangzhou public-guide-synthesis closeness case.

This is reproducible regression evidence, not a domain-expert gold standard.
Traceability: H3, Gate 6, ADR-0007.
"""

from __future__ import annotations

from dataclasses import dataclass

from travel_agent.solver import (
    AdjacencyExpectation,
    BaselineProvenance,
    ItineraryBaseline,
    SameDayExpectation,
    TimeBucket,
    VisitExpectation,
    evaluate_itinerary_closeness,
)

from tests.golden.hangzhou_cases import (
    MONDAY,
    TUESDAY,
    WEDNESDAY,
    _attraction,
    _provider,
    _rule,
    _weather,
)
from travel_agent.solver import (
    AttractionPreference,
    Coordinate,
    TripTimeAnchors,
    TimeBucket,
    VisitPeriodPreference,
    VisitPeriodPreferenceSource,
    WeatherSeverity,
    assign_days,
    evaluate_solver_quality,
    route_itinerary,
)


@dataclass(frozen=True, slots=True)
class HangzhouClosenessResult:
    report: object
    note: str


def run_hangzhou_closeness_case() -> HangzhouClosenessResult:
    attractions = (
        _attraction(11, "灵隐寺", rules=_rule("07:00", "17:30", "16:30"), duration=180, energy=4),
        _attraction(12, "飞来峰", rules=_rule("07:00", "17:30", "16:30"), duration=120, energy=4),
        _attraction(13, "西湖湖滨", always_open=True, duration=150, energy=3),
        _attraction(
            14,
            "浙江省博物馆",
            rules=_rule("09:00", "17:00", "16:30"),
            duration=120,
            indoor=True,
            close_days=frozenset({1}),
        ),
        _attraction(15, "雷峰塔", rules=_rule("08:00", "19:00", "18:30"), duration=90, energy=3),
        _attraction(16, "河坊街", rules=_rule("09:00", "22:00"), duration=120, energy=2),
        _attraction(17, "湖滨晚间表演", rules=_rule("19:30", "19:50"), duration=20),
    )
    preferred_dates = (MONDAY, MONDAY, MONDAY, MONDAY, TUESDAY, WEDNESDAY, WEDNESDAY)
    visit_periods = {
        11: VisitPeriodPreference(
            frozenset({TimeBucket.MORNING}),
            frozenset({TimeBucket.AFTERNOON}),
            VisitPeriodPreferenceSource.PUBLIC_GUIDE_SYNTHESIS,
            "SRC-LINGYIN-OFFICIAL",
        ),
        16: VisitPeriodPreference(
            frozenset({TimeBucket.EVENING}),
            frozenset({TimeBucket.AFTERNOON}),
            VisitPeriodPreferenceSource.PUBLIC_GUIDE_SYNTHESIS,
            "SRC-WESTLAKE-GUIDE",
        ),
    }
    weather = _weather(
        {
            MONDAY: WeatherSeverity.NORMAL,
            TUESDAY: WeatherSeverity.NORMAL,
            WEDNESDAY: WeatherSeverity.ADVISORY,
        }
    )
    step1 = assign_days(
        tuple(
            AttractionPreference(
                attraction,
                preferred_date,
                visit_periods.get(attraction.id),
            )
            for attraction, preferred_date in zip(attractions, preferred_dates, strict=True)
        ),
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
    baseline = ItineraryBaseline(
        "HZ-PUBLIC-GUIDE-3D-01",
        "1.0.0",
        BaselineProvenance.PUBLIC_GUIDE_SYNTHESIS,
        ("SRC-LINGYIN-OFFICIAL", "SRC-WESTLAKE-GUIDE", "SRC-FOUNTAIN-GUIDE"),
        visit_expectations=(
            VisitExpectation(
                11,
                MONDAY,
                frozenset({TUESDAY}),
                frozenset({TimeBucket.MORNING}),
                frozenset({TimeBucket.AFTERNOON}),
            ),
            VisitExpectation(12, acceptable_days=frozenset({MONDAY, TUESDAY})),
            VisitExpectation(13, MONDAY, frozenset({TUESDAY})),
            VisitExpectation(14, TUESDAY, frozenset({WEDNESDAY})),
            VisitExpectation(15, TUESDAY, frozenset({MONDAY, WEDNESDAY})),
            VisitExpectation(
                16,
                WEDNESDAY,
                frozenset({TUESDAY}),
                preferred_buckets=frozenset({TimeBucket.EVENING}),
                acceptable_buckets=frozenset({TimeBucket.AFTERNOON}),
            ),
            VisitExpectation(
                17,
                WEDNESDAY,
                preferred_buckets=frozenset({TimeBucket.EVENING}),
                fixed_day=True,
                fixed_bucket=True,
            ),
        ),
        same_day_expectations=(SameDayExpectation(frozenset({11, 12}), weight=2),),
        adjacency_expectations=(AdjacencyExpectation(11, 12, weight=2),),
    )
    report = evaluate_itinerary_closeness(itinerary, quality, baseline, threshold=0.75)
    return HangzhouClosenessResult(
        report,
        "Public-guide-synthesis regression evidence; not a domain-expert gold standard.",
    )
