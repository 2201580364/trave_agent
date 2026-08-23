"""Repeatable solver benchmarks for the Gate 6 scale targets.

Traceability: H3, C1, C2, C4, C5, C6, Gate 6 performance targets.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from time import perf_counter

from travel_agent.solver import (
    ApproximateTravelTimeProvider,
    Attraction,
    AttractionPreference,
    Coordinate,
    DailyWeather,
    TimeRule,
    TripTimeAnchors,
    WeatherBasis,
    WeatherSeverity,
    assign_days,
    evaluate_solver_quality,
    route_itinerary,
)


BASE_DATE = date(2026, 9, 1)
SNAPSHOT_AT = datetime(2026, 8, 23, tzinfo=UTC)
ALL_DAY = (TimeRule.from_strings(("01-01", "12-31"), "09:00", "21:00"),)


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    attraction_count: int
    day_count: int
    threshold_seconds: float


@dataclass(frozen=True, slots=True)
class BenchmarkSample:
    step1_ms: float
    routing_ms: float
    quality_ms: float
    total_ms: float
    scheduled_count: int
    unplaced_count: int
    hard_constraint_violations: int
    gate_passed: bool
    fingerprint: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    case: BenchmarkCase
    samples: tuple[BenchmarkSample, ...]
    min_ms: float
    mean_ms: float
    p50_ms: float
    p95_ms: float
    max_ms: float
    deterministic: bool
    threshold_passed: bool
    quality_passed: bool
    gate_passed: bool


TYPICAL_CASE = BenchmarkCase("PERF-12-3", 12, 3, 30.0)
UPPER_CASE = BenchmarkCase("PERF-20-7", 20, 7, 120.0)
BENCHMARK_CASES = (TYPICAL_CASE, UPPER_CASE)


def run_benchmark(case: BenchmarkCase, *, repetitions: int = 5) -> BenchmarkResult:
    if repetitions <= 0:
        raise ValueError("repetitions must be positive")
    samples = tuple(_run_once(case) for _ in range(repetitions))
    totals = sorted(sample.total_ms for sample in samples)
    mean_ms = sum(totals) / len(totals)
    deterministic = len({sample.fingerprint for sample in samples}) == 1
    threshold_passed = max(totals) / 1000 < case.threshold_seconds
    quality_passed = all(sample.gate_passed for sample in samples)
    return BenchmarkResult(
        case,
        samples,
        min(totals),
        mean_ms,
        _percentile(totals, 0.50),
        _percentile(totals, 0.95),
        max(totals),
        deterministic,
        threshold_passed,
        quality_passed,
        deterministic and threshold_passed and quality_passed,
    )


def _run_once(case: BenchmarkCase) -> BenchmarkSample:
    dates = tuple(BASE_DATE + timedelta(days=index) for index in range(case.day_count))
    attractions = tuple(_attraction(index + 1) for index in range(case.attraction_count))
    preferences = tuple(
        AttractionPreference(attraction, dates[index % len(dates)])
        for index, attraction in enumerate(attractions)
    )
    weather = {
        visit_date: DailyWeather(
            visit_date,
            WeatherBasis.FORECAST,
            WeatherSeverity.NORMAL,
        )
        for visit_date in dates
    }
    provider = ApproximateTravelTimeProvider(
        {
            attraction.id: _coordinate(index)
            for index, attraction in enumerate(attractions)
        },
        speed_kmh=24,
        detour_ratio=1.35,
        data_version=f"benchmark-{case.case_id}",
        fetched_at=SNAPSHOT_AT,
    )

    total_start = perf_counter()
    step1_start = total_start
    step1 = assign_days(
        preferences,
        trip_dates=dates,
        weather_by_date=weather,
        anchors=TripTimeAnchors(9 * 60, 0, 21 * 60, 0, 0),
    )
    step1_end = perf_counter()
    itinerary = route_itinerary(step1, provider, weather_by_date=weather)
    routing_end = perf_counter()
    quality = evaluate_solver_quality(itinerary, attractions)
    quality_end = perf_counter()
    fingerprint = (
        tuple(
            (
                day.visit_date.isoformat(),
                tuple(
                    (visit.attraction.id, visit.arrival_min, visit.leave_min)
                    for visit in day.visits
                ),
            )
            for day in itinerary.days
        ),
        tuple(
            (item.attraction.id, item.rejection_code.value)
            for item in itinerary.unplaced
        ),
        tuple(
            (
                item.attraction.id,
                item.from_date.isoformat(),
                item.to_date.isoformat(),
            )
            for item in itinerary.reassignments
        ),
        quality.hard_constraint_violations,
    )
    return BenchmarkSample(
        (step1_end - step1_start) * 1000,
        (routing_end - step1_end) * 1000,
        (quality_end - routing_end) * 1000,
        (quality_end - total_start) * 1000,
        quality.accounting.scheduled_count,
        quality.accounting.unplaced_count,
        quality.hard_constraint_violations,
        quality.gate_passed,
        fingerprint,
    )


def _attraction(attraction_id: int) -> Attraction:
    return Attraction(
        attraction_id,
        f"杭州性能景点 {attraction_id}",
        suggested_duration=75 + attraction_id % 4 * 15,
        time_rules=ALL_DAY,
        energy_level=1 + attraction_id % 5,
        data_verified=True,
    )


def _coordinate(index: int) -> Coordinate:
    row, column = divmod(index, 5)
    return Coordinate(30.20 + row * 0.018, 120.10 + column * 0.018)


def _percentile(sorted_values: list[float], percentile: float) -> float:
    rank = max(1, math.ceil(percentile * len(sorted_values)))
    return sorted_values[rank - 1]
