"""Core models for solver input gating and C1/C2 availability.

Traceability: H2, H3, C1, C2, C4, C5, C6, S1, S2, ADR-0002, ADR-0004.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
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
    CLOSED_ON_DATE = "CLOSED_ON_DATE"
    EXTREME_WEATHER_OUTDOOR = "EXTREME_WEATHER_OUTDOOR"
    NO_WEATHER_SAFE_DATE = "NO_WEATHER_SAFE_DATE"
    WEATHER_DATA_MISSING = "WEATHER_DATA_MISSING"
    OD_DATA_MISSING = "OD_DATA_MISSING"
    TRANSIT_INFEASIBLE = "TRANSIT_INFEASIBLE"
    EMPTY_DAY_WINDOW = "EMPTY_DAY_WINDOW"
    DAY_CAPACITY_EXCEEDED = "DAY_CAPACITY_EXCEEDED"
    ROUTING_UNPLACED = "ROUTING_UNPLACED"
    NO_FEASIBLE_ROUTE = "NO_FEASIBLE_ROUTE"
    ANCHOR_VIOLATION = "ANCHOR_VIOLATION"
    VISIT_DURATION_INSUFFICIENT = "VISIT_DURATION_INSUFFICIENT"
    REASSIGNMENT_DISPLACES_EXISTING = "REASSIGNMENT_DISPLACES_EXISTING"


class AnchorRejectionCode(StrEnum):
    EMPTY_DAY_WINDOW = "EMPTY_DAY_WINDOW"


class WeatherBasis(StrEnum):
    FORECAST = "forecast"
    CLIMATE = "climate"


class WeatherSeverity(StrEnum):
    NORMAL = "normal"
    ADVISORY = "advisory"
    EXTREME = "extreme"


class ODBasis(StrEnum):
    APPROXIMATE = "approximate"
    GAODE = "gaode"


class TravelMode(StrEnum):
    SPEED = "speed"
    NORMAL = "normal"
    LEISURE = "leisure"


class PaceLevel(StrEnum):
    RELAXED = "relaxed"
    BALANCED = "balanced"
    TIGHT = "tight"


@dataclass(frozen=True, slots=True)
class Coordinate:
    lat: float
    lng: float

    def __post_init__(self) -> None:
        if not -90 <= self.lat <= 90:
            raise ValueError("latitude must be within -90..90")
        if not -180 <= self.lng <= 180:
            raise ValueError("longitude must be within -180..180")


@dataclass(frozen=True, slots=True)
class TravelTimeResult:
    origin_id: int
    destination_id: int
    travel_min: int
    basis: ODBasis
    data_version: str
    fetched_at: datetime

    def __post_init__(self) -> None:
        if self.travel_min < 0:
            raise ValueError("travel_min must be non-negative")
        if self.origin_id == self.destination_id and self.travel_min != 0:
            raise ValueError("same-node travel must be zero")
        if self.origin_id != self.destination_id and self.travel_min == 0:
            raise ValueError("travel_min must be positive for different nodes")
        if not self.data_version:
            raise ValueError("data_version is required")
        if self.fetched_at.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ConnectionEvaluation:
    feasible: bool
    travel: TravelTimeResult | None
    buffered_travel_min: int | None = None
    earliest_next_arrival_min: int | None = None
    slack_min: int | None = None
    rejection_code: RejectionCode | None = None

    def __post_init__(self) -> None:
        if self.feasible == (self.rejection_code is not None):
            raise ValueError("connection evaluation result is inconsistent")


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
    """Minimum production attraction model needed by G5-C1/C2/C5.

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
    is_indoor: bool = False
    energy_level: int = 1
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
        if not 1 <= self.energy_level <= 5:
            raise ValueError("energy_level must be within 1..5")


@dataclass(frozen=True, slots=True)
class RejectedAttraction:
    attraction: Attraction
    code: RejectionCode


@dataclass(frozen=True, slots=True)
class SolverInputBatch:
    eligible: tuple[Attraction, ...]
    rejected: tuple[RejectedAttraction, ...]


@dataclass(frozen=True, slots=True)
class DateRejection:
    visit_date: date
    reasons: tuple[RejectionCode, ...]


@dataclass(frozen=True, slots=True)
class DateAssignment:
    attraction: Attraction
    preferred_date: date
    assigned_date: date | None
    rejection_code: RejectionCode | None = None
    date_rejections: tuple[DateRejection, ...] = ()

    def __post_init__(self) -> None:
        has_assignment = self.assigned_date is not None
        has_rejection = self.rejection_code is not None
        if has_assignment == has_rejection:
            raise ValueError("date assignment must contain exactly one result")


@dataclass(frozen=True, slots=True)
class DailyWeather:
    day: date
    basis: WeatherBasis
    severity: WeatherSeverity
    condition: str | None = None


@dataclass(frozen=True, slots=True)
class WeatherAvailability:
    available: bool
    rejection_code: RejectionCode | None = None

    def __post_init__(self) -> None:
        if self.available == (self.rejection_code is not None):
            raise ValueError("weather availability result is inconsistent")


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

    def __post_init__(self) -> None:
        if self.start_min < 0 or self.end_min < self.start_min:
            raise ValueError("day time bounds are invalid")


@dataclass(frozen=True, slots=True)
class DayTimeBoundsResolution:
    bounds: DayTimeBounds | None
    rejection_code: AnchorRejectionCode | None = None

    def __post_init__(self) -> None:
        if (self.bounds is None) == (self.rejection_code is None):
            raise ValueError("day bounds resolution must contain exactly one result")


@dataclass(frozen=True, slots=True)
class AttractionPreference:
    attraction: Attraction
    preferred_date: date


@dataclass(frozen=True, slots=True)
class DayAllocation:
    attraction: Attraction
    preferred_date: date
    assigned_date: date
    required_duration_min: int

    def __post_init__(self) -> None:
        if self.required_duration_min <= 0:
            raise ValueError("required_duration_min must be positive")


@dataclass(frozen=True, slots=True)
class UnplacedAttraction:
    attraction: Attraction
    preferred_date: date
    rejection_code: RejectionCode
    date_rejections: tuple[DateRejection, ...] = ()


@dataclass(frozen=True, slots=True)
class DayPlan:
    visit_date: date
    bounds: DayTimeBounds
    allocations: tuple[DayAllocation, ...]
    used_duration_min: int
    energy_total: int
    pace: PaceLevel
    pace_notice: str


@dataclass(frozen=True, slots=True)
class Step1Plan:
    days: tuple[DayPlan, ...]
    unplaced: tuple[UnplacedAttraction, ...]
    data_rejected: tuple[RejectedAttraction, ...]
    travel_mode: TravelMode = TravelMode.NORMAL


@dataclass(frozen=True, slots=True)
class RouteVisit:
    attraction: Attraction
    arrival_min: int
    leave_min: int
    planned_duration_min: int
    travel_from_previous: TravelTimeResult | None = None
    buffered_travel_from_previous_min: int = 0
    duration_notice: str | None = None


@dataclass(frozen=True, slots=True)
class RouteUnplaced:
    attraction: Attraction
    rejection_code: RejectionCode


@dataclass(frozen=True, slots=True)
class RoutedDay:
    visit_date: date
    bounds: DayTimeBounds
    visits: tuple[RouteVisit, ...]
    unplaced: tuple[RouteUnplaced, ...]
    total_travel_min: int
    total_buffered_travel_min: int

    def __post_init__(self) -> None:
        if self.total_travel_min < 0 or self.total_buffered_travel_min < 0:
            raise ValueError("route travel totals must be non-negative")


@dataclass(frozen=True, slots=True)
class ConstraintViolation:
    code: RejectionCode
    attraction_id: int | None = None
    previous_attraction_id: int | None = None


@dataclass(frozen=True, slots=True)
class RouteValidation:
    valid: bool
    violations: tuple[ConstraintViolation, ...] = ()

    def __post_init__(self) -> None:
        if self.valid == bool(self.violations):
            raise ValueError("route validation result is inconsistent")


@dataclass(frozen=True, slots=True)
class RoutingAttempt:
    visit_date: date
    rejection_codes: tuple[RejectionCode, ...]

    def __post_init__(self) -> None:
        if not self.rejection_codes:
            raise ValueError("routing attempt must contain at least one rejection code")


@dataclass(frozen=True, slots=True)
class ItineraryUnplaced:
    attraction: Attraction
    preferred_date: date
    rejection_code: RejectionCode
    attempts: tuple[RoutingAttempt, ...] = ()


@dataclass(frozen=True, slots=True)
class ItineraryReassignment:
    attraction: Attraction
    from_date: date
    to_date: date


@dataclass(frozen=True, slots=True)
class ItineraryPlan:
    days: tuple[RoutedDay, ...]
    unplaced: tuple[ItineraryUnplaced, ...]
    data_rejected: tuple[RejectedAttraction, ...]
    reassignments: tuple[ItineraryReassignment, ...]
    validations: tuple[RouteValidation, ...]
    valid: bool

    def __post_init__(self) -> None:
        if self.valid != all(item.valid for item in self.validations):
            raise ValueError("itinerary validation result is inconsistent")


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
