"""A6-8.1 QWeather forecast acquisition tests without live credentials."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from travel_agent.infrastructure.weather import (
    QWeatherFailureCode,
    QWeatherForecastClient,
    QWeatherForecastError,
    QWeatherSettings,
    classify_qweather_severity,
    qweather_snapshot_content_hash,
)
from travel_agent.solver import WeatherBasis, WeatherSeverity

NOW = datetime(2026, 8, 27, 8, 0, tzinfo=UTC)


class FakeTransport:
    def __init__(self, payload: Mapping[str, object]) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict[str, str], float]] = []

    def get_json(
        self,
        path: str,
        *,
        params: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        self.calls.append((path, dict(params), timeout_seconds))
        return self.payload


def _payload(
    *,
    code: str = "200",
    daily: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "updateTime": "2026-08-27T14:35+08:00",
        "daily": daily
        or [
            {
                "fxDate": "2026-08-27",
                "textDay": "晴",
                "textNight": "多云",
                "iconDay": "100",
                "iconNight": "150",
            },
            {
                "fxDate": "2026-08-28",
                "textDay": "小雨",
                "textNight": "中雨",
                "iconDay": "305",
                "iconNight": "306",
            },
            {
                "fxDate": "2026-08-29",
                "textDay": "暴雨",
                "textNight": "大暴雨",
                "iconDay": "310",
                "iconNight": "311",
            },
        ],
    }


def test_qweather_settings_load_env_without_exposing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRAVEL_AGENT_QWEATHER_API_KEY", "weather-secret")
    monkeypatch.setenv("TRAVEL_AGENT_QWEATHER_LOCATION_ID", "101210101")
    monkeypatch.setenv("TRAVEL_AGENT_QWEATHER_TIMEOUT_SECONDS", "3.5")
    monkeypatch.setenv("TRAVEL_AGENT_QWEATHER_DATA_VERSION", "weather-test-v1")
    monkeypatch.setenv("TRAVEL_AGENT_QWEATHER_BASE_URL", "https://api.example.test")

    settings = QWeatherSettings.from_env(load_dotenv_file=False)

    assert settings.location_id == "101210101"
    assert settings.timeout_seconds == 3.5
    assert settings.data_version == "weather-test-v1"
    assert settings.base_url == "https://api.example.test"
    assert "weather-secret" not in repr(settings)


def test_qweather_settings_require_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRAVEL_AGENT_QWEATHER_API_KEY", raising=False)

    with pytest.raises(ValueError, match="QWEATHER_API_KEY"):
        QWeatherSettings.from_env(load_dotenv_file=False)


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        ("晴转多云", WeatherSeverity.NORMAL),
        ("小雨转中雨", WeatherSeverity.ADVISORY),
        ("雷阵雨", WeatherSeverity.ADVISORY),
        ("暴雨转大暴雨", WeatherSeverity.EXTREME),
        ("台风", WeatherSeverity.EXTREME),
        ("雷阵雨伴有冰雹", WeatherSeverity.EXTREME),
    ],
)
def test_classify_qweather_severity(
    condition: str,
    expected: WeatherSeverity,
) -> None:
    assert classify_qweather_severity(condition) is expected


def test_qweather_client_parses_three_day_forecast_with_provenance() -> None:
    transport = FakeTransport(_payload())
    settings = QWeatherSettings(
        "weather-secret",
        timeout_seconds=4,
        data_version="qweather-hangzhou-2026-08-27-v1",
    )
    client = QWeatherForecastClient(settings, lambda: NOW, transport=transport)

    snapshot = client.fetch_three_day(city_id="hangzhou")

    assert snapshot.city_id == "hangzhou"
    assert snapshot.provider_update_time == "2026-08-27T14:35+08:00"
    assert [item.basis for item in snapshot.days] == [WeatherBasis.FORECAST] * 3
    assert [item.severity for item in snapshot.days] == [
        WeatherSeverity.NORMAL,
        WeatherSeverity.ADVISORY,
        WeatherSeverity.EXTREME,
    ]
    assert snapshot.days[0].condition == "晴转多云"
    assert snapshot.days[0].condition_code == "100/150"
    assert snapshot.days[0].source_ref == (
        "qweather:101210101:qweather-hangzhou-2026-08-27-v1:2026-08-27"
    )
    assert snapshot.days[0].fetched_at == NOW
    assert transport.calls == [
        (
            "/v7/weather/3d",
            {"location": "101210101", "key": "weather-secret"},
            4,
        )
    ]
    serialized = snapshot.to_dict()
    assert serialized["provider"] == "qweather"
    assert "weather-secret" not in str(serialized)
    assert len(qweather_snapshot_content_hash(serialized)) == 64


def test_qweather_client_classifies_api_rate_limit() -> None:
    client = QWeatherForecastClient(
        QWeatherSettings("secret"),
        lambda: NOW,
        transport=FakeTransport(_payload(code="429")),
    )

    with pytest.raises(QWeatherForecastError) as raised:
        client.fetch_three_day(city_id="hangzhou")

    assert raised.value.code is QWeatherFailureCode.RATE_LIMITED
    assert raised.value.provider_code == "429"


def test_qweather_client_rejects_incomplete_forecast() -> None:
    payload = _payload()
    payload["daily"] = payload["daily"][:2]
    client = QWeatherForecastClient(
        QWeatherSettings("secret"),
        lambda: NOW,
        transport=FakeTransport(payload),
    )

    with pytest.raises(QWeatherForecastError) as raised:
        client.fetch_three_day(city_id="hangzhou")

    assert raised.value.code is QWeatherFailureCode.INVALID_RESPONSE


def test_qweather_client_rejects_non_consecutive_days() -> None:
    payload = _payload()
    payload["daily"][2]["fxDate"] = "2026-08-30"
    client = QWeatherForecastClient(
        QWeatherSettings("secret"),
        lambda: NOW,
        transport=FakeTransport(payload),
    )

    with pytest.raises(QWeatherForecastError) as raised:
        client.fetch_three_day(city_id="hangzhou")

    assert raised.value.code is QWeatherFailureCode.INVALID_RESPONSE


def test_qweather_client_requires_timezone_aware_clock() -> None:
    client = QWeatherForecastClient(
        QWeatherSettings("secret"),
        lambda: datetime(2026, 8, 27, 8, 0),
        transport=FakeTransport(_payload()),
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        client.fetch_three_day(city_id="hangzhou")
