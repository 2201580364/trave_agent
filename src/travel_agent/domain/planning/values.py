"""Planning value objects and business facts.

Traceability: A5 API V2.0, functions 1.3.*, IF-03, ADR-0009.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class ConfirmationStatus(StrEnum):
    UNRESOLVED = "unresolved"
    SUGGESTED = "suggested"
    CONFIRMED = "confirmed"
    CONFIRMED_BY_INHERITANCE = "confirmed_by_inheritance"
    OVERRIDDEN = "overridden"

    @property
    def permits_generation(self) -> bool:
        return self in {
            ConfirmationStatus.CONFIRMED,
            ConfirmationStatus.CONFIRMED_BY_INHERITANCE,
            ConfirmationStatus.OVERRIDDEN,
        }


class TransportType(StrEnum):
    FLIGHT = "flight"
    HIGH_SPEED_RAIL = "high_speed_rail"
    TRAIN = "train"
    SELF_DRIVE = "self_drive"
    LONG_DISTANCE_BUS = "long_distance_bus"
    ALREADY_IN_DESTINATION = "already_in_destination"
    OTHER = "other"


class TravelMode(StrEnum):
    SPEED = "speed"
    NORMAL = "normal"
    LEISURE = "leisure"


class CrowdType(StrEnum):
    UNSPECIFIED = "unspecified"
    SOLO = "solo"
    COUPLE = "couple"
    FRIENDS = "friends"
    FAMILY_WITH_CHILDREN = "family_with_children"
    WITH_ELDERLY = "with_elderly"


class GenerationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_TERMINAL = "failed_terminal"


class CompletionKind(StrEnum):
    COMPLETE_SUCCESS = "complete_success"
    PARTIAL_SUCCESS = "partial_success"


@dataclass(frozen=True, slots=True)
class TravelFacts:
    start_date: date
    end_date: date
    arrival_transport_type: TransportType
    arrival_confirmation: ConfirmationStatus
    arrival_at: datetime
    station_to_city_min: int
    station_to_city_source: str
    departure_transport_type: TransportType
    departure_confirmation: ConfirmationStatus
    departure_at: datetime
    station_early_min: int
    station_early_source: str
    last_visit_to_station_min: int
    last_visit_to_station_source: str
    travel_mode: TravelMode = TravelMode.NORMAL
    crowd_type: CrowdType = CrowdType.UNSPECIFIED

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        if self.arrival_at.tzinfo is None or self.departure_at.tzinfo is None:
            raise ValueError("arrival_at and departure_at must be timezone-aware")
        if self.arrival_at >= self.departure_at:
            raise ValueError("arrival_at must be before departure_at")
        if not self.start_date <= self.arrival_at.date() <= self.end_date:
            raise ValueError("arrival_at must fall within the trip date range")
        if not self.start_date <= self.departure_at.date() <= self.end_date:
            raise ValueError("departure_at must fall within the trip date range")
        reserves = (
            self.station_to_city_min,
            self.station_early_min,
            self.last_visit_to_station_min,
        )
        if any(item < 0 for item in reserves):
            raise ValueError("time reserves must be non-negative")
        sources = (
            self.station_to_city_source,
            self.station_early_source,
            self.last_visit_to_station_source,
        )
        if any(not item.strip() for item in sources):
            raise ValueError("time reserve sources are required")
        if self.arrival_confirmation is ConfirmationStatus.CONFIRMED_BY_INHERITANCE:
            raise ValueError("arrival transport cannot be confirmed by inheritance")
        if (
            self.departure_confirmation is ConfirmationStatus.CONFIRMED_BY_INHERITANCE
            and self.departure_transport_type is not self.arrival_transport_type
        ):
            raise ValueError("inherited departure transport must equal arrival transport")
        if (
            self.arrival_transport_type is not TransportType.ALREADY_IN_DESTINATION
            and self.station_to_city_min == 0
        ):
            raise ValueError("station_to_city_min cannot be zero for arrival transport")

    @property
    def ready_for_generation(self) -> bool:
        return (
            self.arrival_confirmation.permits_generation
            and self.departure_confirmation.permits_generation
        )


@dataclass(frozen=True, slots=True)
class VisitPeriodPreferenceInput:
    attraction_id: str
    preferred_bucket: str
    acceptable_buckets: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        allowed = {"morning", "afternoon", "evening"}
        if not self.attraction_id.strip():
            raise ValueError("attraction_id is required")
        if self.preferred_bucket not in allowed:
            raise ValueError("preferred_bucket is invalid")
        if any(item not in allowed for item in self.acceptable_buckets):
            raise ValueError("acceptable bucket is invalid")
        if self.preferred_bucket in self.acceptable_buckets:
            raise ValueError("preferred bucket cannot also be acceptable")
        if len(set(self.acceptable_buckets)) != len(self.acceptable_buckets):
            raise ValueError("acceptable buckets must be unique")
