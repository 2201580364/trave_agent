"""Offline tests for the opt-in Gaode OD snapshot command."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.build_gaode_od_snapshot import (
    _load_coordinates,
    _serialize_pairs,
    main,
)
from travel_agent.solver import (
    Coordinate,
    InMemoryTravelTimeProvider,
    ODBasis,
    ODTravelMode,
    TravelTimeResult,
)

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


def test_snapshot_command_requires_explicit_live_acknowledgement(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_gaode_od_snapshot.py",
            "--input",
            "unused.json",
            "--output",
            "unused-output.json",
            "--data-version",
            "test-v1",
        ],
    )

    with pytest.raises(SystemExit) as raised:
        main()

    assert raised.value.code == 2


def test_load_coordinates_accepts_published_gate6_fixture() -> None:
    coordinates = _load_coordinates(
        Path("tests/data/hangzhou_attractions_snapshot.json")
    )

    assert len(coordinates) == 7
    assert coordinates[14] == Coordinate(30.2525, 120.1495)


def test_load_coordinates_rejects_records_outside_publication_gate(
    tmp_path,
) -> None:
    source = tmp_path / "invalid.json"
    source.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "id": 1,
                        "lat": 30.25,
                        "lng": 120.16,
                        "data_verified": False,
                        "conflict": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="publication data gate"):
        _load_coordinates(source)


def test_serialize_pairs_preserves_real_mode_distance_and_missing_edges() -> None:
    coordinates = {
        1: Coordinate(30.25, 120.16),
        2: Coordinate(30.26, 120.17),
    }
    provider = InMemoryTravelTimeProvider(
        {
            (1, 2): TravelTimeResult(
                1,
                2,
                18,
                ODBasis.GAODE,
                "gaode-test-v1",
                NOW,
                ODTravelMode.TRANSIT,
                4_200,
            )
        }
    )

    pairs = _serialize_pairs(coordinates, provider)

    assert pairs[0] == {
        "origin_id": 1,
        "destination_id": 2,
        "status": "available",
        "travel_min": 18,
        "travel_mode": "transit",
        "distance_m": 4_200,
        "basis": "gaode",
        "data_version": "gaode-test-v1",
        "fetched_at": NOW.isoformat(),
        "fallback_reason": None,
    }
    assert pairs[1] == {
        "origin_id": 2,
        "destination_id": 1,
        "status": "missing",
    }
