"""Structured daily file logging split by severity bucket.

Traceability: H3, ADR-0005 D1-D3.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

from .archive import archive_completed_months
from .file_lock import InterProcessFileLock

ALLOWED_CONTEXT_FIELDS = (
    "event",
    "request_id",
    "task_id",
    "trip_id",
    "solve_run_id",
    "duration_ms",
    "error_code",
)


class LevelBucketFilter(logging.Filter):
    def __init__(self, minimum: int, maximum_exclusive: int | None = None) -> None:
        super().__init__()
        self.minimum = minimum
        self.maximum_exclusive = maximum_exclusive

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno < self.minimum:
            return False
        return self.maximum_exclusive is None or record.levelno < self.maximum_exclusive


class JsonLineFormatter(logging.Formatter):
    """Serialize an allowlisted logging record as one UTF-8 JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field_name in ALLOWED_CONTEXT_FIELDS:
            value = getattr(record, field_name, None)
            if value is not None:
                payload[field_name] = value
        if record.exc_info is not None:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class MonthlyArchiveCoordinator:
    """Run completed-month archival once per observed calendar month."""

    def __init__(self, log_root: Path) -> None:
        self.log_root = log_root
        self._last_checked_month: str | None = None
        self._lock = threading.Lock()

    def check(self, current_date: date) -> None:
        month = current_date.strftime("%Y-%m")
        if self._last_checked_month == month:
            return
        with self._lock:
            if self._last_checked_month == month:
                return
            archive_completed_months(self.log_root, today=current_date)
            self._last_checked_month = month


class DailyFileHandler(logging.Handler):
    """Append one locked JSON line to the current date file."""

    def __init__(
        self,
        directory: Path,
        *,
        date_provider: Callable[[], date],
        archive_coordinator: MonthlyArchiveCoordinator,
    ) -> None:
        super().__init__()
        self.directory = directory
        self.date_provider = date_provider
        self.archive_coordinator = archive_coordinator

    def emit(self, record: logging.LogRecord) -> None:
        try:
            current_date = self.date_provider()
            self.archive_coordinator.check(current_date)
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self.directory / f"{current_date.isoformat()}.log"
            with InterProcessFileLock(self.directory / ".write.lock"):
                with path.open(mode="a", encoding="utf-8", newline="") as stream:
                    stream.write(self.format(record) + "\n")
                    stream.flush()
        except Exception:
            self.handleError(record)


def configure_file_logging(
    log_root: Path,
    *,
    component: str,
    logger_name: str = "travel_agent",
    enable_console: bool = False,
    date_provider: Callable[[], date] = date.today,
) -> logging.Logger:
    """Configure module-level daily JSON files for debug/info/error buckets."""

    safe_component = _safe_path_segment(component)
    component_root = log_root / safe_component
    coordinator = MonthlyArchiveCoordinator(log_root)
    formatter = JsonLineFormatter()

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    for existing_handler in logger.handlers[:]:
        existing_handler.close()
        logger.removeHandler(existing_handler)

    bucket_settings = (
        ("debug", logging.DEBUG, logging.INFO),
        ("info", logging.INFO, logging.ERROR),
        ("error", logging.ERROR, None),
    )
    for bucket, minimum, maximum in bucket_settings:
        handler = DailyFileHandler(
            component_root / bucket,
            date_provider=date_provider,
            archive_coordinator=coordinator,
        )
        handler.setLevel(minimum)
        handler.addFilter(LevelBucketFilter(minimum, maximum))
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    if enable_console:
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        console.setFormatter(formatter)
        logger.addHandler(console)

    return logger


def _safe_path_segment(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-.")
    if not normalized:
        raise ValueError("component identifier must contain safe characters")
    return normalized
