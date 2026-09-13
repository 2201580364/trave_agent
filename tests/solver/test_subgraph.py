from datetime import UTC, datetime

from travel_agent.solver import (
    InMemoryTravelTimeProvider,
    ODBasis,
    ODSubgraphSnapshot,
    ODTravelMode,
    OnDemandODSubgraphBuilder,
    TravelTimeResult,
)

NOW = datetime(2026, 9, 13, tzinfo=UTC)


def test_on_demand_subgraph_is_deterministic_and_keeps_missing_edges_missing() -> None:
    provider = InMemoryTravelTimeProvider(
        {
            (1, 2): TravelTimeResult(
                1, 2, 8, ODBasis.GAODE, "od-v1", NOW, ODTravelMode.WALKING, 500
            ),
            (2, 1): TravelTimeResult(
                2, 1, 9, ODBasis.GAODE, "od-v1", NOW, ODTravelMode.WALKING, 600
            ),
        }
    )
    builder = OnDemandODSubgraphBuilder()
    first = builder.build((2, 1, 3), provider, created_at=NOW)
    second = builder.build((3, 2, 1), provider, created_at=NOW)

    assert first == second
    assert first.snapshot_hash
    assert first.provider().get_travel_time(1, 3) is None
    assert first.provider().get_travel_time(1, 2).travel_min == 8
    assert ODSubgraphSnapshot.from_dict(first.to_dict()) == first


def test_subgraph_rejects_mixed_versions() -> None:
    provider = InMemoryTravelTimeProvider(
        {
            (1, 2): TravelTimeResult(1, 2, 8, ODBasis.GAODE, "od-v1", NOW),
            (2, 1): TravelTimeResult(2, 1, 9, ODBasis.GAODE, "od-v2", NOW),
        }
    )
    try:
        OnDemandODSubgraphBuilder().build((1, 2), provider, created_at=NOW)
    except ValueError as exc:
        assert "data versions" in str(exc)
    else:
        raise AssertionError("mixed OD versions must be rejected")
