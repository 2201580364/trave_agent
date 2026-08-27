"""Weather acquisition adapters used only while published snapshots are built."""

from .qweather import (
    HttpxQWeatherTransport,
    QWeatherFailureCode,
    QWeatherForecastClient,
    QWeatherForecastError,
    QWeatherForecastSnapshot,
    QWeatherSettings,
    QWeatherSnapshotDay,
    classify_qweather_severity,
    qweather_snapshot_content_hash,
)

__all__ = [
    "HttpxQWeatherTransport",
    "QWeatherFailureCode",
    "QWeatherForecastClient",
    "QWeatherForecastError",
    "QWeatherForecastSnapshot",
    "QWeatherSettings",
    "QWeatherSnapshotDay",
    "classify_qweather_severity",
    "qweather_snapshot_content_hash",
]
