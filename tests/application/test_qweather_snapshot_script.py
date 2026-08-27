"""Offline tests for the opt-in QWeather snapshot command."""

from __future__ import annotations

import sys

import pytest

from scripts.build_qweather_snapshot import main


def test_qweather_snapshot_command_requires_explicit_live_acknowledgement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_qweather_snapshot.py",
            "--output",
            "unused-output.json",
            "--data-version",
            "weather-test-v1",
        ],
    )

    with pytest.raises(SystemExit) as raised:
        main()

    assert raised.value.code == 2
