"""C5 tests. Traceability: H3, trip-solver S5, ADR-0003, ADR-0004."""

from datetime import date

from travel_agent.solver import (
    Attraction,
    DailyWeather,
    RejectionCode,
    WeatherBasis,
    WeatherSeverity,
    assign_to_nearest_feasible_date,
    evaluate_weather_availability,
)


def _weather(
    day: date,
    *,
    basis: WeatherBasis = WeatherBasis.FORECAST,
    severity: WeatherSeverity = WeatherSeverity.NORMAL,
) -> DailyWeather:
    return DailyWeather(day=day, basis=basis, severity=severity)


def test_c5_forecast_extreme_excludes_outdoor_attraction() -> None:
    day = date(2026, 8, 24)
    attraction = Attraction(1, "室外景点", is_indoor=False, data_verified=True)

    result = evaluate_weather_availability(
        attraction,
        _weather(day, severity=WeatherSeverity.EXTREME),
    )

    assert not result.available
    assert result.rejection_code is RejectionCode.EXTREME_WEATHER_OUTDOOR


def test_c5_forecast_extreme_keeps_indoor_attraction_available() -> None:
    day = date(2026, 8, 24)
    attraction = Attraction(1, "室内景点", is_indoor=True, data_verified=True)

    result = evaluate_weather_availability(
        attraction,
        _weather(day, severity=WeatherSeverity.EXTREME),
    )

    assert result.available
    assert result.rejection_code is None


def test_c5_advisory_weather_does_not_hard_block_outdoor_attraction() -> None:
    day = date(2026, 8, 24)
    attraction = Attraction(1, "小雨可游景点", is_indoor=False, data_verified=True)

    result = evaluate_weather_availability(
        attraction,
        _weather(day, severity=WeatherSeverity.ADVISORY),
    )

    assert result.available


def test_c5_climate_basis_never_hard_blocks_a_specific_day() -> None:
    day = date(2026, 9, 20)
    attraction = Attraction(1, "远期室外景点", is_indoor=False, data_verified=True)

    result = evaluate_weather_availability(
        attraction,
        _weather(
            day,
            basis=WeatherBasis.CLIMATE,
            severity=WeatherSeverity.EXTREME,
        ),
    )

    assert result.available


def test_c5_reassigns_outdoor_attraction_to_normal_weather_day() -> None:
    monday = date(2026, 8, 24)
    tuesday = date(2026, 8, 25)
    attraction = Attraction(1, "室外景点", data_verified=True)
    weather_by_date = {
        monday: _weather(monday, severity=WeatherSeverity.EXTREME),
        tuesday: _weather(tuesday),
    }

    result = assign_to_nearest_feasible_date(
        attraction,
        preferred_date=monday,
        trip_dates=[monday, tuesday],
        weather_by_date=weather_by_date,
    )

    assert result.assigned_date == tuesday
    assert result.rejection_code is None
    assert result.date_rejections[0].visit_date == monday
    assert result.date_rejections[0].reasons == (RejectionCode.EXTREME_WEATHER_OUTDOOR,)


def test_c5_returns_no_weather_safe_date_when_all_days_are_extreme() -> None:
    monday = date(2026, 8, 24)
    tuesday = date(2026, 8, 25)
    attraction = Attraction(1, "室外景点", data_verified=True)
    weather_by_date = {
        monday: _weather(monday, severity=WeatherSeverity.EXTREME),
        tuesday: _weather(tuesday, severity=WeatherSeverity.EXTREME),
    }

    result = assign_to_nearest_feasible_date(
        attraction,
        preferred_date=monday,
        trip_dates=[monday, tuesday],
        weather_by_date=weather_by_date,
    )

    assert result.assigned_date is None
    assert result.rejection_code is RejectionCode.NO_WEATHER_SAFE_DATE


def test_c1_and_c5_combination_selects_first_day_passing_both() -> None:
    monday = date(2026, 8, 24)
    tuesday = date(2026, 8, 25)
    wednesday = date(2026, 8, 26)
    attraction = Attraction(
        1,
        "周一闭馆室外景点",
        close_days=frozenset({1}),
        data_verified=True,
    )
    weather_by_date = {
        monday: _weather(monday),
        tuesday: _weather(tuesday, severity=WeatherSeverity.EXTREME),
        wednesday: _weather(wednesday),
    }

    result = assign_to_nearest_feasible_date(
        attraction,
        preferred_date=monday,
        trip_dates=[monday, tuesday, wednesday],
        weather_by_date=weather_by_date,
    )

    assert result.assigned_date == wednesday
    assert result.date_rejections[0].reasons == (RejectionCode.CLOSED_ON_DATE,)
    assert result.date_rejections[1].reasons == (RejectionCode.EXTREME_WEATHER_OUTDOOR,)


def test_c5_nearest_feasible_tie_prefers_earlier_date() -> None:
    monday = date(2026, 8, 24)
    tuesday = date(2026, 8, 25)
    wednesday = date(2026, 8, 26)
    attraction = Attraction(1, "室外景点", data_verified=True)
    weather_by_date = {
        monday: _weather(monday),
        tuesday: _weather(tuesday, severity=WeatherSeverity.EXTREME),
        wednesday: _weather(wednesday),
    }

    result = assign_to_nearest_feasible_date(
        attraction,
        preferred_date=tuesday,
        trip_dates=[wednesday, monday, tuesday],
        weather_by_date=weather_by_date,
    )

    assert result.assigned_date == monday


def test_c5_missing_weather_is_not_assumed_clear() -> None:
    monday = date(2026, 8, 24)
    attraction = Attraction(1, "天气未知景点", data_verified=True)

    result = assign_to_nearest_feasible_date(
        attraction,
        preferred_date=monday,
        trip_dates=[monday],
        weather_by_date={},
    )

    assert result.assigned_date is None
    assert result.rejection_code is RejectionCode.NO_AVAILABLE_DATE
    assert result.date_rejections[0].reasons == (RejectionCode.WEATHER_DATA_MISSING,)

