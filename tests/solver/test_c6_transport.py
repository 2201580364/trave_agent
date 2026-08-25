"""C6 tests. Traceability: H3, C6, ADR-0001, ADR-0003, ADR-0004."""

from datetime import UTC, datetime

import pytest

from travel_agent.solver import (
    ApproximateTravelTimeProvider,
    Coordinate,
    InMemoryTravelTimeProvider,
    ODBasis,
    RejectionCode,
    TravelTimeResult,
    evaluate_connection,
)

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)


def _result(*, travel_min: int = 25) -> TravelTimeResult:
    return TravelTimeResult(
        origin_id=1,
        destination_id=2,
        travel_min=travel_min,
        basis=ODBasis.GAODE,
        data_version="gaode-2026-08-22",
        fetched_at=NOW,
    )


def test_c6_connection_is_feasible_at_exact_buffered_boundary() -> None:
    provider = InMemoryTravelTimeProvider({(1, 2): _result(travel_min=25)})

    evaluation = evaluate_connection(
        provider,
        origin_id=1,
        destination_id=2,
        previous_leave_min=10 * 60,
        next_arrival_min=10 * 60 + 30,
    )

    assert evaluation.feasible
    assert evaluation.buffered_travel_min == 30
    assert evaluation.earliest_next_arrival_min == 10 * 60 + 30
    assert evaluation.slack_min == 0


def test_c6_connection_rejects_one_minute_shortfall() -> None:
    provider = InMemoryTravelTimeProvider({(1, 2): _result(travel_min=25)})

    evaluation = evaluate_connection(
        provider,
        origin_id=1,
        destination_id=2,
        previous_leave_min=10 * 60,
        next_arrival_min=10 * 60 + 29,
    )

    assert not evaluation.feasible
    assert evaluation.rejection_code is RejectionCode.TRANSIT_INFEASIBLE


def test_c6_missing_od_is_not_assumed_zero() -> None:
    provider = InMemoryTravelTimeProvider({})

    evaluation = evaluate_connection(
        provider,
        origin_id=1,
        destination_id=2,
        previous_leave_min=10 * 60,
        next_arrival_min=11 * 60,
    )

    assert not evaluation.feasible
    assert evaluation.travel is None
    assert evaluation.rejection_code is RejectionCode.OD_DATA_MISSING


def test_c6_same_node_has_zero_travel_time() -> None:
    provider = InMemoryTravelTimeProvider({}, default_basis=ODBasis.GAODE)

    evaluation = evaluate_connection(
        provider,
        origin_id=1,
        destination_id=1,
        previous_leave_min=10 * 60,
        next_arrival_min=10 * 60,
    )

    assert evaluation.feasible
    assert evaluation.travel is not None
    assert evaluation.travel.travel_min == 0
    assert evaluation.buffered_travel_min == 0


def test_c6_rejects_negative_or_zero_invalid_od_values() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        _result(travel_min=-1)

    with pytest.raises(ValueError, match="positive"):
        _result(travel_min=0)


def test_c6_requires_timezone_aware_fetched_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        TravelTimeResult(
            origin_id=1,
            destination_id=2,
            travel_min=20,
            basis=ODBasis.GAODE,
            data_version="gaode-v1",
            fetched_at=datetime(2026, 8, 22, 12, 0),
        )


def test_c6_provider_rejects_key_result_mismatch() -> None:
    with pytest.raises(ValueError, match="mapping key"):
        InMemoryTravelTimeProvider({(2, 1): _result()})


def test_c6_approximate_provider_is_deterministic_and_labeled() -> None:
    provider = ApproximateTravelTimeProvider(
        {
            1: Coordinate(30.2590, 120.1460),
            2: Coordinate(30.2440, 120.1030),
        },
        speed_kmh=30,
        detour_ratio=1.3,
        data_version="approx-hangzhou-v1",
        fetched_at=NOW,
    )

    first = provider.get_travel_time(1, 2)
    second = provider.get_travel_time(1, 2)

    assert first == second
    assert first is not None
    assert first.travel_min > 0
    assert first.basis is ODBasis.APPROXIMATE
    assert first.data_version == "approx-hangzhou-v1"


def test_c6_approximate_provider_returns_missing_for_unknown_coordinate() -> None:
    provider = ApproximateTravelTimeProvider(
        {1: Coordinate(30.2590, 120.1460)},
        data_version="approx-v1",
        fetched_at=NOW,
    )

    assert provider.get_travel_time(1, 2) is None


def test_c6_approximate_provider_applies_configured_minimum_for_short_hops() -> None:
    provider = ApproximateTravelTimeProvider(
        {
            1: Coordinate(30.2590, 120.1650),
            2: Coordinate(30.2591, 120.1651),
        },
        minimum_travel_min=5,
        data_version="approx-v1",
        fetched_at=NOW,
    )

    result = provider.get_travel_time(1, 2)

    assert result is not None
    assert result.travel_min == 5


def test_c6_validates_coordinate_and_provider_parameters() -> None:
    with pytest.raises(ValueError, match="latitude"):
        Coordinate(100, 120)
    with pytest.raises(ValueError, match="longitude"):
        Coordinate(30, 200)
    with pytest.raises(ValueError, match="speed_kmh"):
        ApproximateTravelTimeProvider(
            {1: Coordinate(30, 120)},
            speed_kmh=0,
            data_version="v1",
            fetched_at=NOW,
        )
    with pytest.raises(ValueError, match="detour_ratio"):
        ApproximateTravelTimeProvider(
            {1: Coordinate(30, 120)},
            detour_ratio=0.9,
            data_version="v1",
            fetched_at=NOW,
        )
    with pytest.raises(ValueError, match="minimum_travel_min"):
        ApproximateTravelTimeProvider(
            {1: Coordinate(30, 120)},
            minimum_travel_min=0,
            data_version="v1",
            fetched_at=NOW,
        )


def test_c6_rejects_buffer_ratio_below_one() -> None:
    provider = InMemoryTravelTimeProvider({(1, 2): _result()})

    with pytest.raises(ValueError, match="buffer_ratio"):
        evaluate_connection(
            provider,
            origin_id=1,
            destination_id=2,
            previous_leave_min=10 * 60,
            next_arrival_min=11 * 60,
            buffer_ratio=0.9,
        )
