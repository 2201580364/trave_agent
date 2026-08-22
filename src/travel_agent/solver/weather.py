"""C5 extreme-weather availability and C1+C5 cross-day assignment.

Traceability: H3, trip-solver S5, C1, C5, ADR-0003, ADR-0004.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date

from .availability import is_open_on
from .models import (
    Attraction,
    DailyWeather,
    DateAssignment,
    DateRejection,
    RejectionCode,
    WeatherAvailability,
    WeatherBasis,
    WeatherSeverity,
)


def evaluate_weather_availability(
    attraction: Attraction,
    weather: DailyWeather,
) -> WeatherAvailability:
    """Apply C5 without treating climate baselines as daily forecasts."""

    is_hard_extreme = (
        weather.basis is WeatherBasis.FORECAST
        and weather.severity is WeatherSeverity.EXTREME
    )
    if is_hard_extreme and not attraction.is_indoor:
        return WeatherAvailability(False, RejectionCode.EXTREME_WEATHER_OUTDOOR)
    return WeatherAvailability(True)


def assign_to_nearest_feasible_date(
    attraction: Attraction,
    *,
    preferred_date: date,
    trip_dates: Iterable[date],
    weather_by_date: Mapping[date, DailyWeather],
) -> DateAssignment:
    """Choose the nearest date satisfying both C1 and C5."""

    evaluations: list[DateRejection] = []
    feasible_dates: list[date] = []
    for candidate in sorted(set(trip_dates)):
        reasons: list[RejectionCode] = []
        if not is_open_on(attraction, candidate):
            reasons.append(RejectionCode.CLOSED_ON_DATE)

        weather = weather_by_date.get(candidate)
        if weather is None:
            reasons.append(RejectionCode.WEATHER_DATA_MISSING)
        else:
            if weather.day != candidate:
                raise ValueError("weather mapping key must match DailyWeather.day")
            weather_result = evaluate_weather_availability(attraction, weather)
            if weather_result.rejection_code is not None:
                reasons.append(weather_result.rejection_code)

        if reasons:
            evaluations.append(DateRejection(candidate, tuple(reasons)))
        else:
            feasible_dates.append(candidate)

    if feasible_dates:
        assigned_date = min(
            feasible_dates,
            key=lambda candidate: (abs((candidate - preferred_date).days), candidate),
        )
        return DateAssignment(
            attraction=attraction,
            preferred_date=preferred_date,
            assigned_date=assigned_date,
            date_rejections=tuple(evaluations),
        )

    all_dates_weather_blocked = bool(evaluations) and all(
        RejectionCode.EXTREME_WEATHER_OUTDOOR in evaluation.reasons
        for evaluation in evaluations
    )
    rejection_code = (
        RejectionCode.NO_WEATHER_SAFE_DATE
        if all_dates_weather_blocked
        else RejectionCode.NO_AVAILABLE_DATE
    )
    return DateAssignment(
        attraction=attraction,
        preferred_date=preferred_date,
        assigned_date=None,
        rejection_code=rejection_code,
        date_rejections=tuple(evaluations),
    )

