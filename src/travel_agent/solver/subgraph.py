"""Deterministic, replayable OD subgraphs for on-demand solving (R0.2-06/C6)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from .models import TravelTimeResult
from .transport import InMemoryTravelTimeProvider, TravelTimeProvider


@dataclass(frozen=True, slots=True)
class ODSubgraphSnapshot:
    node_ids: tuple[int, ...]
    entries: tuple[TravelTimeResult, ...]
    data_version: str
    snapshot_hash: str
    created_at: datetime

    def __post_init__(self) -> None:
        if tuple(sorted(set(self.node_ids))) != self.node_ids:
            raise ValueError("OD subgraph node_ids must be sorted and unique")
        if not self.entries:
            raise ValueError("OD subgraph must contain at least one directed edge")
        if len(self.snapshot_hash) != 64:
            raise ValueError("OD subgraph snapshot_hash must be SHA-256")

    def provider(self) -> InMemoryTravelTimeProvider:
        return InMemoryTravelTimeProvider(
            {(item.origin_id, item.destination_id): item for item in self.entries},
            data_version=self.data_version,
            fetched_at=max(item.fetched_at for item in self.entries),
        )


class OnDemandODSubgraphBuilder:
    def build(
        self,
        node_ids: tuple[int, ...] | list[int],
        provider: TravelTimeProvider,
        *,
        created_at: datetime,
    ) -> ODSubgraphSnapshot:
        ordered = tuple(sorted(set(node_ids)))
        if len(ordered) < 2:
            raise ValueError("OD subgraph requires at least two nodes")
        entries = [
            travel
            for origin_id in ordered
            for destination_id in ordered
            if origin_id != destination_id
            for travel in [provider.get_travel_time(origin_id, destination_id)]
            if travel is not None
        ]
        if not entries:
            raise ValueError("OD subgraph has no available directed edges")
        entries.sort(key=lambda item: (item.origin_id, item.destination_id))
        versions = {item.data_version for item in entries}
        if len(versions) != 1:
            raise ValueError("OD subgraph cannot mix data versions")
        payload = [
            {
                "origin_id": item.origin_id,
                "destination_id": item.destination_id,
                "travel_min": item.travel_min,
                "basis": item.basis.value,
                "data_version": item.data_version,
                "fetched_at": item.fetched_at.isoformat(),
                "travel_mode": item.travel_mode.value if item.travel_mode else None,
                "distance_m": item.distance_m,
                "fallback_reason": item.fallback_reason,
            }
            for item in entries
        ]
        serialized = json.dumps(
            {"node_ids": ordered, "entries": payload},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return ODSubgraphSnapshot(
            ordered,
            tuple(entries),
            versions.pop(),
            hashlib.sha256(serialized).hexdigest(),
            created_at,
        )


__all__ = ["ODSubgraphSnapshot", "OnDemandODSubgraphBuilder"]
