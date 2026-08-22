"""G5 Step 1 integration tests. Traceability: H2, H3, C1, C2, C4, C5, S2."""

from datetime import date
from typing import Any

from travel_agent.solver import (
    Attraction,
    AttractionPreference,
    DailyWeather,
    PaceLevel,
    RejectionCode,
    TimeRule,
    TravelMode,
    TripTimeAnchors,
    WeatherBasis,
    WeatherSeverity,
    assign_days,
)


MONDAY = date(2026, 8, 24)
TUESDAY = date(2026, 8, 25)
WEDNESDAY = date(2026, 8, 26)
ALL_DAY = (TimeRule.from_strings(("01-01", "12-31"), "09:00", "21:00"),)
ANCHORS = TripTimeAnchors(9 * 60, 0, 21 * 60, 0, 0)


def _weather(
    day: date,
    severity: WeatherSeverity = WeatherSeverity.NORMAL,
) -> DailyWeather:
    return DailyWeather(day, WeatherBasis.FORECAST, severity)


def _attraction(
    attraction_id: int,
    *,
    duration: int = 120,
    energy: int = 1,
    **kwargs: Any,
) -> Attraction:
    time_rules = kwargs.pop("time_rules", ALL_DAY)
    return Attraction(
        attraction_id,
        f"景点 {attraction_id}",
        suggested_duration=duration,
        energy_level=energy,
        time_rules=time_rules,
        data_verified=True,
        **kwargs,
    )


def test_step1_runs_data_gate_before_assignment() -> None:
    valid = _attraction(1)
    unverified = Attraction(2, "未验证", time_rules=ALL_DAY)
    result = assign_days(
        [AttractionPreference(valid, MONDAY), AttractionPreference(unverified, MONDAY)],
        trip_dates=[MONDAY],
        weather_by_date={MONDAY: _weather(MONDAY)},
        anchors=ANCHORS,
    )

    assert [item.attraction.id for item in result.days[0].allocations] == [1]
    assert result.data_rejected[0].code is RejectionCode.DATA_UNVERIFIED


def test_step1_combines_closure_and_weather_then_reassigns() -> None:
    attraction = _attraction(1, close_days=frozenset({1}))
    result = assign_days(
        [AttractionPreference(attraction, MONDAY)],
        trip_dates=[MONDAY, TUESDAY, WEDNESDAY],
        weather_by_date={
            MONDAY: _weather(MONDAY),
            TUESDAY: _weather(TUESDAY, WeatherSeverity.EXTREME),
            WEDNESDAY: _weather(WEDNESDAY),
        },
        anchors=ANCHORS,
    )

    assert result.days[2].allocations[0].attraction.id == 1
    assert result.unplaced == ()


def test_step1_rebalances_to_day_with_remaining_time_capacity() -> None:
    first = _attraction(1, duration=700)
    second = _attraction(2, duration=700)
    result = assign_days(
        [AttractionPreference(first, MONDAY), AttractionPreference(second, MONDAY)],
        trip_dates=[MONDAY, TUESDAY],
        weather_by_date={MONDAY: _weather(MONDAY), TUESDAY: _weather(TUESDAY)},
        anchors=ANCHORS,
    )

    assert [[item.attraction.id for item in day.allocations] for day in result.days] == [[1], [2]]


def test_step1_never_silently_drops_capacity_overflow() -> None:
    attractions = [_attraction(index, duration=1200) for index in range(1, 4)]
    result = assign_days(
        [AttractionPreference(item, MONDAY) for item in attractions],
        trip_dates=[MONDAY],
        weather_by_date={MONDAY: _weather(MONDAY)},
        anchors=ANCHORS,
    )

    assert len(result.days[0].allocations) == 1
    assert [item.rejection_code for item in result.unplaced] == [
        RejectionCode.DAY_CAPACITY_EXCEEDED,
        RejectionCode.DAY_CAPACITY_EXCEEDED,
    ]


def test_step1_c2_window_must_overlap_day_anchor_window() -> None:
    morning_only = _attraction(
        1,
        time_rules=(TimeRule.from_strings(("01-01", "12-31"), "09:00", "12:00"),),
    )
    late_arrival = TripTimeAnchors(13 * 60, 0, 24 * 60, 0, 0)
    result = assign_days(
        [AttractionPreference(morning_only, MONDAY)],
        trip_dates=[MONDAY],
        weather_by_date={MONDAY: _weather(MONDAY)},
        anchors=late_arrival,
    )

    assert result.unplaced[0].rejection_code is RejectionCode.NO_AVAILABLE_DATE
    assert (
        RejectionCode.ARRIVAL_AFTER_LATEST_ARRIVAL
        in result.unplaced[0].date_rejections[0].reasons
    )


def test_step1_leisure_mode_spreads_high_energy_attractions() -> None:
    first = _attraction(1, energy=4)
    second = _attraction(2, energy=4)
    result = assign_days(
        [AttractionPreference(first, MONDAY), AttractionPreference(second, MONDAY)],
        trip_dates=[MONDAY, TUESDAY],
        weather_by_date={MONDAY: _weather(MONDAY), TUESDAY: _weather(TUESDAY)},
        anchors=ANCHORS,
        travel_mode=TravelMode.LEISURE,
    )

    assert [[item.attraction.id for item in day.allocations] for day in result.days] == [[1], [2]]


def test_step1_energy_is_soft_and_emits_tight_pace_notice() -> None:
    attractions = [_attraction(index, energy=5, duration=60) for index in range(1, 4)]
    result = assign_days(
        [AttractionPreference(item, MONDAY) for item in attractions],
        trip_dates=[MONDAY],
        weather_by_date={MONDAY: _weather(MONDAY)},
        anchors=ANCHORS,
        travel_mode=TravelMode.LEISURE,
    )

    assert len(result.days[0].allocations) == 3
    assert result.days[0].pace is PaceLevel.TIGHT
    assert result.days[0].pace_notice == "本日节奏偏紧"


def test_step1_rejects_duplicate_ids_and_out_of_trip_preference() -> None:
    attraction = _attraction(1)
    try:
        assign_days(
            [AttractionPreference(attraction, MONDAY), AttractionPreference(attraction, MONDAY)],
            trip_dates=[MONDAY],
            weather_by_date={MONDAY: _weather(MONDAY)},
            anchors=ANCHORS,
        )
    except ValueError as exc:
        assert "duplicate attraction id" in str(exc)
    else:
        raise AssertionError("duplicate attraction id must be rejected")

    try:
        assign_days(
            [AttractionPreference(attraction, TUESDAY)],
            trip_dates=[MONDAY],
            weather_by_date={MONDAY: _weather(MONDAY)},
            anchors=ANCHORS,
        )
    except ValueError as exc:
        assert "preferred_date" in str(exc)
    else:
        raise AssertionError("out-of-trip preferred date must be rejected")
