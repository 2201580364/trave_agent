"""C1 tests. Traceability: H3, trip-solver S1, ADR-0002, ADR-0004."""

from datetime import date

import pytest

from travel_agent.solver import (
    Attraction,
    RejectionCode,
    assign_attraction_date,
    assign_to_nearest_available_date,
    is_open_on,
)


def test_c1_supports_multiple_weekly_closed_days() -> None:
    attraction = Attraction(
        1,
        "双闭馆日景点",
        close_days=frozenset({1, 2}),
        data_verified=True,
    )

    assert not is_open_on(attraction, date(2026, 8, 24))  # Monday
    assert not is_open_on(attraction, date(2026, 8, 25))  # Tuesday
    assert is_open_on(attraction, date(2026, 8, 26))  # Wednesday


def test_c1_opening_exception_overrides_weekly_closure() -> None:
    public_holiday_monday = date(2026, 10, 5)
    attraction = Attraction(
        1,
        "节假日开放博物馆",
        close_days=frozenset({1}),
        open_on_dates=frozenset({public_holiday_monday}),
        data_verified=True,
    )

    assert is_open_on(attraction, public_holiday_monday)


def test_c1_explicit_closure_takes_precedence() -> None:
    exceptional_closure = date(2026, 8, 26)
    attraction = Attraction(
        1,
        "临时闭馆景点",
        closed_on_dates=frozenset({exceptional_closure}),
        data_verified=True,
    )

    assert not is_open_on(attraction, exceptional_closure)


def test_c1_reassigns_monday_closed_attraction_to_tuesday() -> None:
    monday = date(2026, 8, 24)
    tuesday = date(2026, 8, 25)
    attraction = Attraction(
        1,
        "周一闭馆博物馆",
        close_days=frozenset({1}),
        data_verified=True,
    )

    assigned = assign_to_nearest_available_date(attraction, monday, [monday, tuesday])

    assert assigned == tuesday


def test_c1_nearest_available_day_tie_prefers_earlier_date() -> None:
    monday = date(2026, 8, 24)
    tuesday = date(2026, 8, 25)
    wednesday = date(2026, 8, 26)
    attraction = Attraction(
        1,
        "周二闭馆景点",
        close_days=frozenset({2}),
        data_verified=True,
    )

    assigned = assign_to_nearest_available_date(
        attraction,
        tuesday,
        [wednesday, monday, tuesday, monday],
    )

    assert assigned == monday


def test_c1_returns_none_when_all_trip_dates_are_closed() -> None:
    monday = date(2026, 8, 24)
    tuesday = date(2026, 8, 25)
    attraction = Attraction(
        1,
        "全程闭馆景点",
        close_days=frozenset({1, 2}),
        data_verified=True,
    )

    assert assign_to_nearest_available_date(attraction, monday, [monday, tuesday]) is None


def test_c1_unplaced_result_has_machine_readable_reason() -> None:
    monday = date(2026, 8, 24)
    tuesday = date(2026, 8, 25)
    attraction = Attraction(
        1,
        "全程闭馆景点",
        close_days=frozenset({1, 2}),
        data_verified=True,
    )

    result = assign_attraction_date(attraction, monday, [monday, tuesday])

    assert result.assigned_date is None
    assert result.rejection_code is RejectionCode.NO_AVAILABLE_DATE


def test_c1_rejects_invalid_weekday_values() -> None:
    with pytest.raises(ValueError, match="ISO weekdays 1..7"):
        Attraction(1, "错误闭馆日", close_days=frozenset({0, 8}), data_verified=True)


def test_c1_rejects_conflicting_date_exceptions() -> None:
    conflicted_date = date(2026, 8, 24)

    with pytest.raises(ValueError, match="both an opening and closure exception"):
        Attraction(
            1,
            "冲突例外",
            open_on_dates=frozenset({conflicted_date}),
            closed_on_dates=frozenset({conflicted_date}),
            data_verified=True,
        )
