"""QWeather three-day forecast acquisition for immutable publication snapshots.

Network I/O is restricted to snapshot construction. The solver consumes only
versioned ``DailyWeather`` values embedded in published solver data.

Traceability: C5, ADR-0003, A6-8.1.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from os import PathLike
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from travel_agent.runtime_config import load_runtime_environment
from travel_agent.solver import WeatherBasis, WeatherSeverity

_EXTREME_KEYWORDS = (
    "特大暴雨",
    "大暴雨",
    "暴雨",
    "特大暴雪",
    "大暴雪",
    "暴雪",
    "台风",
    "龙卷风",
    "冰雹",
    "雷暴大风",
    "强沙尘暴",
)
_ADVISORY_KEYWORDS = (
    "雨",
    "雪",
    "雷",
    "雾",
    "霾",
    "沙",
    "尘",
)


class QWeatherFailureCode(StrEnum):
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    HTTP_ERROR = "http_error"
    API_ERROR = "api_error"
    INVALID_RESPONSE = "invalid_response"


class QWeatherForecastError(RuntimeError):
    def __init__(
        self,
        code: QWeatherFailureCode,
        message: str,
        *,
        provider_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.provider_code = provider_code


@dataclass(frozen=True, slots=True)
class QWeatherSettings:
    api_key: str = field(repr=False)
    base_url: str = ""
    location_id: str = "101210101"
    timeout_seconds: float = 5.0
    data_version: str = "qweather-forecast-v1"

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("QWeather api_key is required")
        if not self.location_id.strip():
            raise ValueError("QWeather location_id is required")
        if self.timeout_seconds <= 0:
            raise ValueError("QWeather timeout_seconds must be positive")
        if not self.data_version.strip():
            raise ValueError("QWeather data_version is required")
        parsed_base_url = urlsplit(self.base_url)
        if (
            parsed_base_url.scheme != "https"
            or not parsed_base_url.netloc
            or parsed_base_url.path not in {"", "/"}
            or parsed_base_url.query
            or parsed_base_url.fragment
            or parsed_base_url.username is not None
            or parsed_base_url.password is not None
        ):
            raise ValueError("QWeather base_url must be a credential-free HTTPS host")

    @classmethod
    def from_env(
        cls,
        *,
        dotenv_path: str | PathLike[str] | None = None,
        load_dotenv_file: bool = True,
    ) -> QWeatherSettings:
        if load_dotenv_file:
            load_runtime_environment(dotenv_path)
        key = os.environ.get("TRAVEL_AGENT_QWEATHER_API_KEY", "").strip()
        if not key:
            raise ValueError("TRAVEL_AGENT_QWEATHER_API_KEY is required")
        base_url = os.environ.get("TRAVEL_AGENT_QWEATHER_BASE_URL", "").strip()
        if not base_url:
            raise ValueError("TRAVEL_AGENT_QWEATHER_BASE_URL is required")
        return cls(
            api_key=key,
            base_url=base_url,
            location_id=os.environ.get(
                "TRAVEL_AGENT_QWEATHER_LOCATION_ID",
                "101210101",
            ).strip(),
            timeout_seconds=float(
                os.environ.get("TRAVEL_AGENT_QWEATHER_TIMEOUT_SECONDS", "5")
            ),
            data_version=os.environ.get(
                "TRAVEL_AGENT_QWEATHER_DATA_VERSION",
                "qweather-forecast-v1",
            ).strip(),
        )


@dataclass(frozen=True, slots=True)
class QWeatherSnapshotDay:
    day: date
    basis: WeatherBasis
    severity: WeatherSeverity
    condition: str
    condition_code: str
    source_ref: str
    fetched_at: datetime

    def __post_init__(self) -> None:
        if self.basis is not WeatherBasis.FORECAST:
            raise ValueError("QWeather snapshot days must use forecast basis")
        if not self.condition or not self.condition_code or not self.source_ref:
            raise ValueError("QWeather snapshot provenance is required")
        if self.fetched_at.tzinfo is None:
            raise ValueError("QWeather fetched_at must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "date": self.day.isoformat(),
            "basis": self.basis.value,
            "severity": self.severity.value,
            "condition": self.condition,
            "condition_code": self.condition_code,
            "source_ref": self.source_ref,
            "fetched_at": self.fetched_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class QWeatherForecastSnapshot:
    city_id: str
    location_id: str
    data_version: str
    provider_update_time: str
    fetched_at: datetime
    days: tuple[QWeatherSnapshotDay, ...]

    def __post_init__(self) -> None:
        if not self.city_id or not self.location_id or not self.data_version:
            raise ValueError("QWeather snapshot identity is required")
        if self.fetched_at.tzinfo is None:
            raise ValueError("QWeather snapshot fetched_at must be timezone-aware")
        if len(self.days) != 3:
            raise ValueError("QWeather three-day snapshot must contain exactly three days")
        if len({item.day for item in self.days}) != len(self.days):
            raise ValueError("QWeather snapshot days must be unique")
        expected_days = tuple(
            date.fromordinal(self.days[0].day.toordinal() + offset)
            for offset in range(3)
        )
        if tuple(item.day for item in self.days) != expected_days:
            raise ValueError("QWeather snapshot days must be sorted and consecutive")
        if any(item.fetched_at != self.fetched_at for item in self.days):
            raise ValueError("QWeather snapshot fetched_at must be consistent")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "weather-snapshot-v1",
            "city_id": self.city_id,
            "location_id": self.location_id,
            "data_version": self.data_version,
            "basis": WeatherBasis.FORECAST.value,
            "provider": "qweather",
            "provider_update_time": self.provider_update_time,
            "fetched_at": self.fetched_at.isoformat(),
            "days": [item.to_dict() for item in self.days],
        }


class QWeatherHttpTransport(Protocol):
    def get_json(
        self,
        path: str,
        *,
        params: Mapping[str, str],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, object]: ...


class HttpxQWeatherTransport:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def get_json(
        self,
        path: str,
        *,
        params: Mapping[str, str],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        try:
            response = httpx.get(
                self._base_url + path,
                params=params,
                timeout=timeout_seconds,
                headers={"Accept": "application/json", **headers},
            )
        except httpx.TimeoutException as exc:
            raise QWeatherForecastError(
                QWeatherFailureCode.TIMEOUT,
                "QWeather request timed out",
            ) from exc
        except httpx.HTTPError as exc:
            raise QWeatherForecastError(
                QWeatherFailureCode.HTTP_ERROR,
                "QWeather request failed",
            ) from exc
        if response.status_code == 429:
            raise QWeatherForecastError(
                QWeatherFailureCode.RATE_LIMITED,
                "QWeather rate limited",
                provider_code="429",
            )
        if not response.is_success:
            raise QWeatherForecastError(
                QWeatherFailureCode.HTTP_ERROR,
                "QWeather HTTP error",
                provider_code=str(response.status_code),
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise QWeatherForecastError(
                QWeatherFailureCode.INVALID_RESPONSE,
                "QWeather returned invalid JSON",
            ) from exc
        if not isinstance(payload, dict):
            raise QWeatherForecastError(
                QWeatherFailureCode.INVALID_RESPONSE,
                "QWeather response must be an object",
            )
        return payload


class QWeatherForecastClient:
    def __init__(
        self,
        settings: QWeatherSettings,
        clock: Callable[[], datetime],
        *,
        transport: QWeatherHttpTransport | None = None,
    ) -> None:
        self._settings = settings
        self._clock = clock
        self._transport = transport or HttpxQWeatherTransport(settings.base_url)

    def fetch_three_day(self, *, city_id: str) -> QWeatherForecastSnapshot:
        if not city_id:
            raise ValueError("QWeather city_id is required")
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("QWeather clock must return timezone-aware datetimes")
        payload = self._transport.get_json(
            "/v7/weather/3d",
            params={"location": self._settings.location_id},
            headers={"X-QW-Api-Key": self._settings.api_key},
            timeout_seconds=self._settings.timeout_seconds,
        )
        return _parse_forecast(
            payload,
            settings=self._settings,
            city_id=city_id,
            fetched_at=now,
        )


def classify_qweather_severity(condition: str) -> WeatherSeverity:
    normalized = condition.strip()
    if not normalized:
        raise ValueError("QWeather condition is required")
    if any(keyword in normalized for keyword in _EXTREME_KEYWORDS):
        return WeatherSeverity.EXTREME
    if any(keyword in normalized for keyword in _ADVISORY_KEYWORDS):
        return WeatherSeverity.ADVISORY
    return WeatherSeverity.NORMAL


def qweather_snapshot_content_hash(snapshot: Mapping[str, object]) -> str:
    serialized = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _parse_forecast(
    payload: Mapping[str, object],
    *,
    settings: QWeatherSettings,
    city_id: str,
    fetched_at: datetime,
) -> QWeatherForecastSnapshot:
    provider_code = _text(payload.get("code"))
    if provider_code != "200":
        failure = (
            QWeatherFailureCode.RATE_LIMITED
            if provider_code == "429"
            else QWeatherFailureCode.API_ERROR
        )
        raise QWeatherForecastError(
            failure,
            "QWeather API rejected forecast request",
            provider_code=provider_code,
        )
    provider_update_time = _text(payload.get("updateTime"))
    raw_days = payload.get("daily")
    if not isinstance(raw_days, list) or len(raw_days) != 3:
        raise QWeatherForecastError(
            QWeatherFailureCode.INVALID_RESPONSE,
            "QWeather three-day forecast must contain exactly three days",
        )
    days: list[QWeatherSnapshotDay] = []
    for raw in raw_days:
        if not isinstance(raw, dict):
            raise QWeatherForecastError(
                QWeatherFailureCode.INVALID_RESPONSE,
                "QWeather forecast day must be an object",
            )
        try:
            forecast_date = date.fromisoformat(_text(raw.get("fxDate")))
            text_day = _text(raw.get("textDay"))
            text_night = _text(raw.get("textNight"))
            icon_day = _text(raw.get("iconDay"))
            icon_night = _text(raw.get("iconNight"))
        except (TypeError, ValueError) as exc:
            raise QWeatherForecastError(
                QWeatherFailureCode.INVALID_RESPONSE,
                "QWeather forecast day is invalid",
            ) from exc
        condition = text_day if text_day == text_night else f"{text_day}转{text_night}"
        condition_code = (
            icon_day if icon_day == icon_night else f"{icon_day}/{icon_night}"
        )
        source_ref = (
            f"qweather:{settings.location_id}:{settings.data_version}:"
            f"{forecast_date.isoformat()}"
        )
        days.append(
            QWeatherSnapshotDay(
                forecast_date,
                WeatherBasis.FORECAST,
                classify_qweather_severity(condition),
                condition,
                condition_code,
                source_ref,
                fetched_at,
            )
        )
    try:
        return QWeatherForecastSnapshot(
            city_id,
            settings.location_id,
            settings.data_version,
            provider_update_time,
            fetched_at,
            tuple(sorted(days, key=lambda item: item.day)),
        )
    except ValueError as exc:
        raise QWeatherForecastError(
            QWeatherFailureCode.INVALID_RESPONSE,
            "QWeather forecast snapshot is inconsistent",
        ) from exc


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError("expected non-empty string")
    return value.strip()
