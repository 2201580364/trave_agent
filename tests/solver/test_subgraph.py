from datetime import UTC, datetime

import pytest

from travel_agent.solver import (
    InMemoryTravelTimeProvider,
    ODBasis,
    ODSubgraphSnapshot,
    ODTravelMode,
    OnDemandODSubgraphBuilder,
    TravelTimeResult,
)

NOW = datetime(2026, 9, 13, tzinfo=UTC)


def test_single_node_snapshot_replays_without_inventing_missing_edges() -> None:
    """H3/C6: no inter-place route is needed for a one-place trip."""
    snapshot = OnDemandODSubgraphBuilder().build(
        (7,), InMemoryTravelTimeProvider({}), created_at=NOW
    )
    restored = ODSubgraphSnapshot.from_dict(snapshot.to_dict())
    assert restored == snapshot
    assert restored.entries == ()
    assert restored.provider().get_travel_time(7, 8) is None
    payload = snapshot.to_dict()
    payload["data_version"] = "tampered"
    with pytest.raises(ValueError, match="version"):
        ODSubgraphSnapshot.from_dict(payload)


@pytest.mark.parametrize("nodes", [(), (1, 2)])
def test_empty_or_disconnected_multi_node_selection_still_fails(nodes: tuple[int, ...]) -> None:
    with pytest.raises(ValueError):
        OnDemandODSubgraphBuilder().build(nodes, InMemoryTravelTimeProvider({}), created_at=NOW)


def test_subgraph_rejects_duplicate_edges_before_provider_overwrites_them() -> None:
    edge = TravelTimeResult(1, 2, 8, ODBasis.GAODE, "od-v1", NOW)
    with pytest.raises(ValueError, match="duplicate"):
        ODSubgraphSnapshot((1, 2), (edge, edge), "od-v1", "0" * 64, NOW)


@pytest.mark.parametrize(
    "field,value", [("data_version", "tampered"), ("node_ids", [2, 1]), ("snapshot_hash", "0" * 64)]
)
def test_replay_rejects_modified_snapshot_metadata(field: str, value: object) -> None:
    provider = InMemoryTravelTimeProvider(
        {
            (1, 2): TravelTimeResult(1, 2, 8, ODBasis.GAODE, "od-v1", NOW),
        }
    )
    payload = OnDemandODSubgraphBuilder().build((1, 2), provider, created_at=NOW).to_dict()
    payload[field] = value
    with pytest.raises(ValueError):
        ODSubgraphSnapshot.from_dict(payload)


@pytest.mark.parametrize("origin,destination", [(1, 3), (1, 1)])
def test_subgraph_rejects_edges_outside_selected_pairs(origin: int, destination: int) -> None:
    with pytest.raises(ValueError, match="endpoints"):
        ODSubgraphSnapshot(
            (1, 2),
            (
                TravelTimeResult(
                    origin,
                    destination,
                    0 if origin == destination else 8,
                    ODBasis.GAODE,
                    "od-v1",
                    NOW,
                ),
            ),
            "od-v1",
            "0" * 64,
            NOW,
        )


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
    edge = first.provider().get_travel_time(1, 2)
    assert edge is not None
    assert edge.travel_min == 8
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
