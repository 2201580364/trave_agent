"""C4 first/last-day time-anchor resolution.

Traceability: H3, H7, trip-solver S4, C4, ADR-0004.
"""

from __future__ import annotations

from .models import (
    AnchorRejectionCode,
    DayTimeBounds,
    DayTimeBoundsResolution,
    TripTimeAnchors,
)

DEFAULT_DAY_START_MIN = 9 * 60
DEFAULT_DAY_END_MIN = 21 * 60


def resolve_day_time_bounds(
    *,
    day_index: int,
    total_days: int,
    anchors: TripTimeAnchors,
    default_start_min: int = DEFAULT_DAY_START_MIN,
    default_end_min: int = DEFAULT_DAY_END_MIN,
) -> DayTimeBoundsResolution:
    """Resolve the C4 usable visit window for one itinerary day."""

    if total_days <= 0:
        raise ValueError("total_days must be positive")
    if not 1 <= day_index <= total_days:
        raise ValueError("day_index must be within 1..total_days")
    if not 0 <= default_start_min <= default_end_min:
        raise ValueError("default day bounds are invalid")

    start_min = default_start_min
    end_min = default_end_min
    if day_index == 1:
        start_min = anchors.arrival_min + anchors.station_to_city_min
    if day_index == total_days:
        end_min = (
            anchors.departure_min
            - anchors.station_early_min
            - anchors.last_visit_to_station_min
        )

    if start_min > end_min:
        return DayTimeBoundsResolution(None, AnchorRejectionCode.EMPTY_DAY_WINDOW)
    return DayTimeBoundsResolution(DayTimeBounds(start_min, end_min))

