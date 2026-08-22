"""Core models for solver input gating and C1/C2 availability.

Traceability: H3, C1, C2, S1, ADR-0002, ADR-0004.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum


class RejectionCode(StrEnum):
    """Machine-readable reasons for excluding an attraction from a solve."""

    DATA_UNVERIFIED = "DATA_UNVERIFIED"
    DATA_CONFLICT = "DATA_CONFLICT"
    INACTIVE = "INACTIVE"
    NO_AVAILABLE_DATE = "NO_AVAILABLE_DATE"
    NO_MATCHING_TIME_RULE = "NO_MATCHING_TIME_RULE"
    TIME_RULE_CONFLICT = "TIME_RULE_CONFLICT"
    ARRIVAL_AFTER_LATEST_ARRIVAL = "ARRIVAL_AFTER_LATEST_ARRIVAL"


class AnchorRejectionCode(StrEnum):
    EMPTY_DAY_WINDOW = "EMPTY_DAY_WINDOW"


@dataclass(frozen=True, slots=True)
class TimeRule:
    start_month: int
    start_day: int
    end_month: int
    end_day: int
    open_min: int
    close_min: int
    last_entry_min: int | None = None

    @classmethod
    def from_strings(
        cls,
        date_range: tuple[str, str],
        open_time: str,
        close_time: str,
        last_entry: str | None = None,
        *,
        crosses_midnight: bool = False,
    ) -> TimeRule:
        """Build a validated recurring date-range rule from storage strings."""

        start_month, start_day = _parse_month_day(date_range[0])
        end_month, end_day = _parse_month_day(date_range[1])
        open_min = _parse_clock(open_time)
        close_min = _parse_clock(close_time)
        last_entry_min = _parse_clock(last_entry) if last_entry is not None else None

        if close_min <= open_min:
            if not crosses_midnight:
                raise ValueError("close must be after open unless crosses_midnight=True")
            close_min += 24 * 60
        elif crosses_midnight:
            raise ValueError("crosses_midnight=True requires close time on the next day")

        if last_entry_min is not None and crosses_midnight and last_entry_min < open_min:
            last_entry_min += 24 * 60
        if last_entry_min is not None and not open_min <= last_entry_min <= close_min:
            raise ValueError("last_entry must be between open and close")

        return cls(
            start_month=start_month,
            start_day=start_day,
            end_month=end_month,
            end_day=end_day,
            open_min=open_min,
            close_min=close_min,
            last_entry_min=last_entry_min,
        )

    def matches(self, visit_date: date) -> bool:
        current = visit_date.month * 100 + visit_date.day
        start = self.start_month * 100 + self.start_day
        end = self.end_month * 100 + self.end_day
        if start <= end:
            return start <= current <= end
        return current >= start or current <= end


@dataclass(frozen=True, slots=True)
class Attraction:
    """Minimum production attraction model needed by G5-C1/C2.

    ``open_on_dates`` represents structured exceptions such as a museum opening
    on a public holiday despite its normal weekly closure. ``closed_on_dates``
    represents exceptional one-off closures and takes precedence.
    """

    id: int
    name: str
    close_days: frozenset[int] = field(default_factory=frozenset)
    open_on_dates: frozenset[date] = field(default_factory=frozenset)
    closed_on_dates: frozenset[date] = field(default_factory=frozenset)
    suggested_duration: int = 60
    time_rules: tuple[TimeRule, ...] = ()
    is_always_open: bool = False
    data_verified: bool = False
    conflict: bool = False
    active: bool = True

    def __post_init__(self) -> None:
        invalid_days = self.close_days.difference(range(1, 8))
        if invalid_days:
            raise ValueError(f"close_days must contain ISO weekdays 1..7: {invalid_days}")
        overlapping_dates = self.open_on_dates.intersection(self.closed_on_dates)
        if overlapping_dates:
            raise ValueError(
                "a date cannot be both an opening and closure exception: "
                f"{sorted(overlapping_dates)}"
            )
        if self.suggested_duration <= 0:
            raise ValueError("suggested_duration must be positive")


@dataclass(frozen=True, slots=True)
class RejectedAttraction:
    attraction: Attraction
    code: RejectionCode


@dataclass(frozen=True, slots=True)
class SolverInputBatch:
    eligible: tuple[Attraction, ...]
    rejected: tuple[RejectedAttraction, ...]


@dataclass(frozen=True, slots=True)
class DateAssignment:
    attraction: Attraction
    preferred_date: date
    assigned_date: date | None
    rejection_code: RejectionCode | None = None

    def __post_init__(self) -> None:
        has_assignment = self.assigned_date is not None
        has_rejection = self.rejection_code is not None
        if has_assignment == has_rejection:
            raise ValueError("date assignment must contain exactly one result")


@dataclass(frozen=True, slots=True)
class EffectiveTimeWindow:
    open_min: int
    close_min: int
    last_entry_min: int | None
    latest_arrival_min: int
    is_always_open: bool = False


@dataclass(frozen=True, slots=True)
class TimeWindowResolution:
    window: EffectiveTimeWindow | None
    rejection_code: RejectionCode | None = None

    def __post_init__(self) -> None:
        if (self.window is None) == (self.rejection_code is None):
            raise ValueError("time window resolution must contain exactly one result")


@dataclass(frozen=True, slots=True)
class ArrivalEvaluation:
    permitted: bool
    window: EffectiveTimeWindow | None
    effective_arrival_min: int | None = None
    leave_min: int | None = None
    planned_duration_min: int | None = None
    duration_ratio: float | None = None
    duration_notice: str | None = None
    rejection_code: RejectionCode | None = None


@dataclass(frozen=True, slots=True)
class TripTimeAnchors:
    arrival_min: int
    station_to_city_min: int
    departure_min: int
    station_early_min: int
    last_visit_to_station_min: int

    def __post_init__(self) -> None:
        values = (
            self.arrival_min,
            self.station_to_city_min,
            self.departure_min,
            self.station_early_min,
            self.last_visit_to_station_min,
        )
        if any(value < 0 for value in values):
            raise ValueError("anchor minutes must be non-negative")


@dataclass(frozen=True, slots=True)
class DayTimeBounds:
    start_min: int
    end_min: int


@dataclass(frozen=True, slots=True)
class DayTimeBoundsResolution:
    bounds: DayTimeBounds | None
    rejection_code: AnchorRejectionCode | None = None

    def __post_init__(self) -> None:
        if (self.bounds is None) == (self.rejection_code is None):
            raise ValueError("day bounds resolution must contain exactly one result")


def _parse_month_day(value: str) -> tuple[int, int]:
    try:
        month_text, day_text = value.split("-", maxsplit=1)
        parsed = date(2000, int(month_text), int(day_text))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid month-day value: {value!r}") from exc
    return parsed.month, parsed.day


def _parse_clock(value: str) -> int:
    try:
        hour_text, minute_text = value.split(":", maxsplit=1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid clock value: {value!r}") from exc
    if hour == 24 and minute == 0:
        return 24 * 60
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError(f"invalid clock value: {value!r}")
    return hour * 60 + minute
