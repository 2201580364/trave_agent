"""Versioned Chinese statutory holiday calendars for O05 date exceptions.

The calendar is deliberately data-only and versioned.  It is not a workday
calculator: every period comes from an official annual announcement and the
day after the period is the museum's explicitly configured shifted closure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True, slots=True)
class HolidayPeriod:
    name: str
    start: date
    end: date


@dataclass(frozen=True, slots=True)
class HolidayCalendar:
    calendar_id: str
    display_name: str
    periods: tuple[HolidayPeriod, ...]
    source_note: str
    source_record_id: str | None = None

    def holiday_dates(self) -> frozenset[date]:
        result: set[date] = set()
        for period in self.periods:
            current = period.start
            while current <= period.end:
                result.add(current)
                current += timedelta(days=1)
        return frozenset(result)

    def period_end_dates(self) -> frozenset[date]:
        return frozenset(period.end for period in self.periods)


# Calendar versions are intentionally explicit.  Update by adding a new
# version after the State Council's annual holiday announcement is verified.
HOLIDAY_CALENDARS: dict[str, HolidayCalendar] = {
    "cn-mainland-2025": HolidayCalendar(
        "cn-mainland-2025",
        "中国大陆法定节假日历（2025）",
        (
            HolidayPeriod("元旦", date(2025, 1, 1), date(2025, 1, 1)),
            HolidayPeriod("春节", date(2025, 1, 28), date(2025, 2, 4)),
            HolidayPeriod("清明节", date(2025, 4, 4), date(2025, 4, 6)),
            HolidayPeriod("劳动节", date(2025, 5, 1), date(2025, 5, 5)),
            HolidayPeriod("端午节", date(2025, 5, 31), date(2025, 6, 2)),
            HolidayPeriod("国庆节、中秋节", date(2025, 10, 1), date(2025, 10, 8)),
        ),
        "国务院办公厅2025年节假日安排公告；调休工作日不作为节假日开放日。",
    ),
    "cn-mainland-2026": HolidayCalendar(
        "cn-mainland-2026",
        "中国大陆法定节假日历（2026）",
        (
            HolidayPeriod("元旦", date(2026, 1, 1), date(2026, 1, 3)),
            HolidayPeriod("春节", date(2026, 2, 15), date(2026, 2, 23)),
            HolidayPeriod("清明节", date(2026, 4, 4), date(2026, 4, 6)),
            HolidayPeriod("劳动节", date(2026, 5, 1), date(2026, 5, 5)),
            HolidayPeriod("端午节", date(2026, 6, 19), date(2026, 6, 21)),
            HolidayPeriod("中秋节", date(2026, 9, 25), date(2026, 9, 27)),
            HolidayPeriod("国庆节", date(2026, 10, 1), date(2026, 10, 7)),
        ),
        "国务院办公厅2026年节假日安排公告；调休工作日不作为节假日开放日。",
    ),
}


def get_holiday_calendar(calendar_id: str) -> HolidayCalendar:
    try:
        return HOLIDAY_CALENDARS[calendar_id]
    except KeyError as exc:
        raise ValueError(f"unknown holiday calendar: {calendar_id}") from exc


def list_holiday_calendars() -> tuple[HolidayCalendar, ...]:
    return tuple(HOLIDAY_CALENDARS.values())


def resolve_holiday_closure_conflicts(
    calendar: HolidayCalendar,
    closure_weekdays: frozenset[int],
    *,
    shift_closure: bool,
) -> tuple[frozenset[date], frozenset[date]]:
    """Return holiday openings and shifted closures caused by real collisions."""
    if any(day < 1 or day > 7 for day in closure_weekdays):
        raise ValueError("closure weekdays must use ISO values 1..7")
    opening_dates: set[date] = set()
    shifted_dates: set[date] = set()
    for period in calendar.periods:
        current = period.start
        collided = False
        while current <= period.end:
            if current.isoweekday() in closure_weekdays:
                opening_dates.add(current)
                collided = True
            current += timedelta(days=1)
        if collided and shift_closure:
            shifted_dates.add(period.end + timedelta(days=1))
    if calendar.holiday_dates().intersection(shifted_dates):
        raise ValueError("shifted closure still falls within a holiday opening date")
    return frozenset(opening_dates), frozenset(shifted_dates)
