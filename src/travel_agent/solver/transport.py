"""C6 OD travel-time providers and deterministic connection validation.

Traceability: H3, C6, ADR-0001, ADR-0003, ADR-0004, ADR-0005.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Protocol

from .models import (
    ConnectionEvaluation,
    Coordinate,
    ODBasis,
    RejectionCode,
    TravelTimeResult,
)

DEFAULT_TRANSIT_BUFFER_RATIO = 1.2
EARTH_RADIUS_KM = 6371.0
SYNTHETIC_FETCHED_AT = datetime(1970, 1, 1, tzinfo=UTC)


class TravelTimeProvider(Protocol):
    """Provide pre-fetched or deterministic OD travel times without network I/O."""

    def get_travel_time(
        self,
        origin_id: int,
        destination_id: int,
    ) -> TravelTimeResult | None: ...


class InMemoryTravelTimeProvider:
    def __init__(
        self,
        results: Mapping[tuple[int, int], TravelTimeResult],
        *,
        default_basis: ODBasis = ODBasis.APPROXIMATE,
        data_version: str = "in-memory",
        fetched_at: datetime | None = None,
    ) -> None:
        for key, result in results.items():
            if key != (result.origin_id, result.destination_id):
                raise ValueError("OD mapping key must match TravelTimeResult endpoints")
        self._results = dict(results)
        self.default_basis = default_basis
        self.data_version = data_version
        self.fetched_at = fetched_at

    def get_travel_time(
        self,
        origin_id: int,
        destination_id: int,
    ) -> TravelTimeResult | None:
        if origin_id == destination_id:
            return TravelTimeResult(
                origin_id=origin_id,
                destination_id=destination_id,
                travel_min=0,
                basis=self.default_basis,
                data_version=self.data_version,
                fetched_at=self.fetched_at or SYNTHETIC_FETCHED_AT,
                distance_m=0,
            )
        return self._results.get((origin_id, destination_id))


class ApproximateTravelTimeProvider:
    """Deterministic straight-line fallback explicitly labeled approximate."""

    def __init__(
        self,
        coordinates: Mapping[int, Coordinate],
        *,
        speed_kmh: float = 30.0,
        detour_ratio: float = 1.3,
        minimum_travel_min: int = 1,
        data_version: str,
        fetched_at: datetime,
    ) -> None:
        if speed_kmh <= 0:
            raise ValueError("speed_kmh must be positive")
        if detour_ratio < 1:
            raise ValueError("detour_ratio must be at least 1")
        if minimum_travel_min <= 0:
            raise ValueError("minimum_travel_min must be positive")
        if fetched_at.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware")
        self.coordinates = dict(coordinates)
        self.speed_kmh = speed_kmh
        self.detour_ratio = detour_ratio
        self.minimum_travel_min = minimum_travel_min
        self.data_version = data_version
        self.fetched_at = fetched_at

    def get_travel_time(
        self,
        origin_id: int,
        destination_id: int,
    ) -> TravelTimeResult | None:
        if origin_id == destination_id:
            return TravelTimeResult(
                origin_id=origin_id,
                destination_id=destination_id,
                travel_min=0,
                basis=ODBasis.APPROXIMATE,
                data_version=self.data_version,
                fetched_at=self.fetched_at,
                distance_m=0,
            )
        origin = self.coordinates.get(origin_id)
        destination = self.coordinates.get(destination_id)
        if origin is None or destination is None:
            return None
        distance_km = _haversine_km(origin, destination)
        travel_min = max(
            self.minimum_travel_min,
            math.ceil(distance_km * self.detour_ratio / self.speed_kmh * 60),
        )
        return TravelTimeResult(
            origin_id=origin_id,
            destination_id=destination_id,
            travel_min=travel_min,
            basis=ODBasis.APPROXIMATE,
            data_version=self.data_version,
            fetched_at=self.fetched_at,
            distance_m=max(1, math.ceil(distance_km * self.detour_ratio * 1000)),
        )


def evaluate_connection(
    provider: TravelTimeProvider,
    *,
    origin_id: int,
    destination_id: int,
    previous_leave_min: int,
    next_arrival_min: int,
    buffer_ratio: float = DEFAULT_TRANSIT_BUFFER_RATIO,
) -> ConnectionEvaluation:
    """Validate C6 using leave time plus buffered OD travel.

    ``previous_leave_min`` already includes the origin attraction's service
    duration, so this function must not add attraction duration again.
    """

    if previous_leave_min < 0 or next_arrival_min < 0:
        raise ValueError("connection times must be non-negative")
    if buffer_ratio < 1:
        raise ValueError("buffer_ratio must be at least 1")

    travel = provider.get_travel_time(origin_id, destination_id)
    if travel is None:
        return ConnectionEvaluation(
            feasible=False,
            travel=None,
            rejection_code=RejectionCode.OD_DATA_MISSING,
        )

    buffered_travel = math.ceil(travel.travel_min * buffer_ratio)
    earliest_arrival = previous_leave_min + buffered_travel
    slack = next_arrival_min - earliest_arrival
    if slack < 0:
        return ConnectionEvaluation(
            feasible=False,
            travel=travel,
            buffered_travel_min=buffered_travel,
            earliest_next_arrival_min=earliest_arrival,
            slack_min=slack,
            rejection_code=RejectionCode.TRANSIT_INFEASIBLE,
        )
    return ConnectionEvaluation(
        feasible=True,
        travel=travel,
        buffered_travel_min=buffered_travel,
        earliest_next_arrival_min=earliest_arrival,
        slack_min=slack,
    )


def _haversine_km(origin: Coordinate, destination: Coordinate) -> float:
    lat1 = math.radians(origin.lat)
    lng1 = math.radians(origin.lng)
    lat2 = math.radians(destination.lat)
    lng2 = math.radians(destination.lng)
    delta_lat = lat2 - lat1
    delta_lng = lng2 - lng1
    h = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lng / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))
