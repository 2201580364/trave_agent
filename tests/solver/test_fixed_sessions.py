"""Discrete show sessions preserve one node and C2/C4/C6 (H3, ADR-0025)."""

from dataclasses import replace
from datetime import UTC, date, datetime

from travel_agent.solver import (
    Attraction,
    AttractionPreference,
    DailyWeather,
    InMemoryTravelTimeProvider,
    ODBasis,
    TimeRule,
    TravelTimeResult,
    TripTimeAnchors,
    WeatherBasis,
    WeatherSeverity,
    assign_days,
    evaluate_solver_quality,
    route_itinerary,
)
from travel_agent.solver.models import FixedSession
from travel_agent.solver.routing import validate_routed_day

DAY = date(2026, 9, 10)
WEATHER = {DAY: DailyWeather(DAY, WeatherBasis.FORECAST, WeatherSeverity.NORMAL)}


def solve(attractions, start=720, end=1200, travel=30):
    provider = InMemoryTravelTimeProvider(
        {
            (a.id, b.id): TravelTimeResult(
                a.id, b.id, travel, ODBasis.GAODE, "test", datetime(2026, 9, 10, tzinfo=UTC)
            )
            for a in attractions
            for b in attractions
            if a.id != b.id
        }
    )
    plan = assign_days(
        tuple(AttractionPreference(a, DAY) for a in attractions),
        trip_dates=(DAY,),
        weather_by_date=WEATHER,
        anchors=TripTimeAnchors(start, 0, end, 0, 0),
    )
    result = route_itinerary(plan, provider, weather_by_date=WEATHER)
    assert evaluate_solver_quality(result, attractions).gate_passed
    return result, provider


def test_later_session_selected_after_real_transport_and_full_show_reserved():
    museum = Attraction(
        1,
        "Museum",
        suggested_duration=120,
        data_verified=True,
        time_rules=(TimeRule(1, 1, 12, 31, 720, 840),),
    )
    show = Attraction(
        2,
        "Show",
        suggested_duration=60,
        data_verified=True,
        fixed_sessions=(
            FixedSession("early", 780, 840),
            FixedSession("late", 960, 1050, 950),
        ),
    )
    result, provider = solve((museum, show))
    visits = result.days[0].visits
    assert [v.attraction.id for v in visits] == [1, 2]
    assert (visits[1].arrival_min, visits[1].leave_min) == (950, 1050)
    invalid = replace(
        result.days[0], visits=(visits[0], replace(visits[1], arrival_min=900, leave_min=1000))
    )
    assert not validate_routed_day(invalid, provider, weather_by_date=WEATHER).valid


def test_gap_between_sessions_is_not_a_feasible_day_window():
    show = Attraction(
        1,
        "Show",
        suggested_duration=30,
        data_verified=True,
        fixed_sessions=(
            FixedSession("morning", 600, 630),
            FixedSession("evening", 1080, 1110),
        ),
    )
    result, _ = solve((show,), start=720, end=900)
    assert not any(day.visits for day in result.days)
    assert len(result.unplaced) == 1


def test_weekday_date_range_and_opening_hours_filter_sessions():
    opening = TimeRule(1, 1, 12, 31, 900, 1100)
    show = Attraction(
        1,
        "Show",
        suggested_duration=30,
        data_verified=True,
        fixed_sessions=(
            FixedSession("wrong-weekday", 780, 810, weekdays=frozenset({1})),
            FixedSession("expired", 840, 870, valid_to=date(2026, 9, 9)),
            FixedSession("outside-opening", 870, 900, opening_hours=(opening,)),
            FixedSession("valid", 960, 990, opening_hours=(opening,)),
        ),
    )
    result, _ = solve((show,))
    assert len(result.days[0].visits) == 1
    assert result.days[0].visits[0].arrival_min == 960
    assert result == solve((show,))[0]


def test_two_shows_choose_one_session_each_without_losing_transport_time():
    first = Attraction(
        1,
        "First",
        suggested_duration=60,
        data_verified=True,
        fixed_sessions=(
            FixedSession("a1", 780, 840),
            FixedSession("a2", 1080, 1140),
        ),
    )
    second = Attraction(
        2,
        "Second",
        suggested_duration=60,
        data_verified=True,
        fixed_sessions=(
            FixedSession("b1", 840, 900),
            FixedSession("b2", 960, 1020),
        ),
    )
    result, _ = solve((first, second), end=1050)
    visits = result.days[0].visits
    assert [(v.attraction.id, v.arrival_min, v.leave_min) for v in visits] == [
        (1, 780, 840),
        (2, 960, 1020),
    ]


def test_overnight_show_respects_next_day_minutes_and_return_bound():
    show = Attraction(
        1,
        "Night",
        suggested_duration=60,
        data_verified=True,
        fixed_sessions=(FixedSession("night", 1410, 1470, 1400),),
    )
    result, _ = solve((show,), start=1380, end=1500)
    assert result.days[0].visits[0].leave_min == 1470
    result, _ = solve((show,), start=1380, end=1450)
    assert len(result.unplaced) == 1


def test_sessions_do_not_allow_missing_od_connections():
    first = Attraction(
        1,
        "First",
        suggested_duration=60,
        data_verified=True,
        fixed_sessions=(FixedSession("a", 780, 840),),
    )
    second = Attraction(
        2,
        "Second",
        suggested_duration=60,
        data_verified=True,
        fixed_sessions=(FixedSession("b", 960, 1020),),
    )
    plan = assign_days(
        tuple(AttractionPreference(a, DAY) for a in (first, second)),
        trip_dates=(DAY,),
        weather_by_date=WEATHER,
        anchors=TripTimeAnchors(720, 0, 1200, 0, 0),
    )
    result = route_itinerary(plan, InMemoryTravelTimeProvider({}), weather_by_date=WEATHER)
    assert sum(len(day.visits) for day in result.days) <= 1
    assert result.unplaced
