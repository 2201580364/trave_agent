from datetime import date, timedelta

import pytest

from travel_agent.domain.place_catalog import get_holiday_calendar, list_holiday_calendars, resolve_holiday_closure_conflicts
from travel_agent.solver.availability import is_open_on
from travel_agent.solver.models import Attraction


def test_calendar_is_versioned_and_expands_inclusive_periods() -> None:
    calendar = get_holiday_calendar("cn-mainland-2026")
    assert calendar.calendar_id == "cn-mainland-2026"
    assert date(2026, 2, 15) in calendar.holiday_dates()
    assert date(2026, 2, 23) in calendar.holiday_dates()
    assert date(2026, 2, 24) not in calendar.holiday_dates()
    assert date(2026, 2, 23) in calendar.period_end_dates()


def test_unknown_calendar_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown holiday calendar"):
        get_holiday_calendar("cn-mainland-2099")


def test_calendar_versions_have_unique_ids() -> None:
    calendars = list_holiday_calendars()
    assert calendars
    assert len({item.calendar_id for item in calendars}) == len(calendars)


def test_holiday_opening_overrides_weekly_monday_closure() -> None:
    calendar = get_holiday_calendar("cn-mainland-2026")
    attraction = Attraction(
        1,
        "浙江省博物馆孤山馆区",
        close_days=frozenset({1}),
        open_on_dates=calendar.holiday_dates(),
        closed_on_dates=frozenset({period.end + timedelta(days=1) for period in calendar.periods}),
        data_verified=True,
    )
    assert is_open_on(attraction, date(2026, 4, 6))
    assert not is_open_on(attraction, date(2026, 4, 7))


def test_policy_only_materializes_real_weekly_closure_conflicts() -> None:
    calendar = get_holiday_calendar("cn-mainland-2026")
    openings, shifted = resolve_holiday_closure_conflicts(
        calendar, frozenset({1}), shift_closure=True
    )
    assert date(2026, 4, 6) in openings  # Qingming holiday Monday overrides closure.
    assert date(2026, 4, 7) in shifted  # Closure moves after that holiday period.
    assert date(2026, 1, 1) not in openings  # Thursday needs no override.
    assert date(2026, 1, 4) not in shifted  # No Monday collision, no shifted closure.
