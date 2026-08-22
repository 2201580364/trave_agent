"""C4 tests. Traceability: H3, H7, trip-solver S4, ADR-0004."""

import pytest

from travel_agent.solver import (
    AnchorRejectionCode,
    TripTimeAnchors,
    resolve_day_time_bounds,
)


def _anchors() -> TripTimeAnchors:
    return TripTimeAnchors(
        arrival_min=14 * 60,
        station_to_city_min=90,
        departure_min=16 * 60,
        station_early_min=90,
        last_visit_to_station_min=30,
    )


def test_c4_first_day_starts_after_arrival_and_city_transfer() -> None:
    resolution = resolve_day_time_bounds(day_index=1, total_days=3, anchors=_anchors())

    assert resolution.bounds is not None
    assert resolution.bounds.start_min == 15 * 60 + 30
    assert resolution.bounds.end_min == 21 * 60


def test_c4_last_day_reserves_return_transfer_and_station_early_time() -> None:
    resolution = resolve_day_time_bounds(day_index=3, total_days=3, anchors=_anchors())

    assert resolution.bounds is not None
    assert resolution.bounds.start_min == 9 * 60
    assert resolution.bounds.end_min == 14 * 60


def test_c4_middle_day_uses_normal_day_window() -> None:
    resolution = resolve_day_time_bounds(day_index=2, total_days=3, anchors=_anchors())

    assert resolution.bounds is not None
    assert resolution.bounds.start_min == 9 * 60
    assert resolution.bounds.end_min == 21 * 60


def test_c4_single_day_combines_arrival_and_departure_anchors() -> None:
    resolution = resolve_day_time_bounds(day_index=1, total_days=1, anchors=_anchors())

    assert resolution.bounds is None
    assert resolution.rejection_code is AnchorRejectionCode.EMPTY_DAY_WINDOW


def test_c4_single_day_returns_valid_combined_window_when_transport_allows() -> None:
    anchors = TripTimeAnchors(
        arrival_min=8 * 60,
        station_to_city_min=60,
        departure_min=21 * 60,
        station_early_min=60,
        last_visit_to_station_min=30,
    )

    resolution = resolve_day_time_bounds(day_index=1, total_days=1, anchors=anchors)

    assert resolution.bounds is not None
    assert resolution.bounds.start_min == 9 * 60
    assert resolution.bounds.end_min == 19 * 60 + 30


def test_c4_rejects_invalid_day_index() -> None:
    with pytest.raises(ValueError, match="day_index"):
        resolve_day_time_bounds(day_index=0, total_days=3, anchors=_anchors())


def test_c4_rejects_negative_anchor_duration() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        TripTimeAnchors(
            arrival_min=8 * 60,
            station_to_city_min=-1,
            departure_min=21 * 60,
            station_early_min=60,
            last_visit_to_station_min=30,
        )

