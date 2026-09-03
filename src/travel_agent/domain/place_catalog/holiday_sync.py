"""Deterministic domain model for annual China holiday synchronization."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

CALENDAR_STATUSES = frozenset({"published", "superseded"})
SYNC_JOB_MODES = frozenset({"preview", "sync"})
SYNC_JOB_STATUSES = frozenset(
    {
        "queued",
        "running",
        "not_announced",
        "temporarily_unavailable",
        "needs_attention",
        "validated_preview",
        "published",
        "up_to_date",
        "cancelled",
    }
)
TERMINAL_SYNC_JOB_STATUSES = SYNC_JOB_STATUSES - {"queued", "running"}
REQUIRED_HOLIDAY_CONCEPTS = frozenset(
    {"元旦", "春节", "清明", "劳动节", "端午", "中秋", "国庆"}
)


@dataclass(frozen=True, slots=True)
class HolidayCalendarPeriod:
    period_id: str
    name: str
    start: date
    end: date
    evidence_quote: str
    display_order: int


@dataclass(frozen=True, slots=True)
class HolidayAdjustedWorkday:
    adjusted_workday_id: str
    service_date: date
    holiday_name: str
    evidence_quote: str


@dataclass(frozen=True, slots=True)
class HolidayCalendarVersion:
    calendar_id: str
    region_code: str
    year: int
    version: int
    status: str
    display_name: str
    source_record_id: str
    source_content_sha256: str
    normalized_digest: str
    periods: tuple[HolidayCalendarPeriod, ...]
    adjusted_workdays: tuple[HolidayAdjustedWorkday, ...]
    supersedes_calendar_id: str | None
    published_at: datetime
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.region_code != "CN":
            raise ValueError("only China mainland holiday calendars are supported")
        if self.version < 1:
            raise ValueError("holiday calendar version must be positive")
        if self.status not in CALENDAR_STATUSES:
            raise ValueError("holiday calendar status is invalid")
        if not self.periods:
            raise ValueError("holiday calendar periods are required")


@dataclass(frozen=True, slots=True)
class HolidayCalendarSyncJob:
    job_id: str
    region_code: str
    year: int
    mode: str
    status: str
    validation_result: dict[str, Any]
    attempt_count: int
    operation_intent_id: str
    operation_digest: str
    created_by: str
    created_at: datetime
    source_url: str | None = None
    source_title: str | None = None
    source_published_at: datetime | None = None
    source_content_sha256: str | None = None
    calendar_id: str | None = None
    next_retry_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.region_code != "CN":
            raise ValueError("only China mainland holiday calendars are supported")
        if self.mode not in SYNC_JOB_MODES:
            raise ValueError("holiday calendar sync mode is invalid")
        if self.status not in SYNC_JOB_STATUSES:
            raise ValueError("holiday calendar sync status is invalid")
        if self.attempt_count < 0:
            raise ValueError("holiday calendar sync attempt count is invalid")

    def transition(self, status: str, *, at: datetime, **changes: Any) -> HolidayCalendarSyncJob:
        if status not in SYNC_JOB_STATUSES:
            raise ValueError("holiday calendar sync status is invalid")
        allowed = {
            "queued": {"running", "cancelled"},
            "running": TERMINAL_SYNC_JOB_STATUSES,
            "temporarily_unavailable": {"running", "cancelled"},
            "validated_preview": {"published"},
        }
        if status not in allowed.get(self.status, set()):
            raise ValueError(f"invalid holiday sync transition: {self.status} -> {status}")
        return replace(
            self,
            status=status,
            started_at=at if status == "running" else self.started_at,
            finished_at=at if status in TERMINAL_SYNC_JOB_STATUSES else None,
            **changes,
        )


@dataclass(frozen=True, slots=True)
class ExtractedHolidayCalendar:
    region_code: str
    year: int
    source_url: str
    source_title: str
    source_record_id: str
    source_content_sha256: str
    periods: tuple[HolidayCalendarPeriod, ...]
    adjusted_workdays: tuple[HolidayAdjustedWorkday, ...]


@dataclass(frozen=True, slots=True)
class HolidayCalendarValidation:
    valid: bool
    errors: tuple[str, ...]
    normalized_digest: str | None


def validate_extracted_calendar(
    value: ExtractedHolidayCalendar,
    *,
    requested_year: int,
    official_domains: frozenset[str] = frozenset({"gov.cn", "www.gov.cn"}),
) -> HolidayCalendarValidation:
    errors: list[str] = []
    host = (urlparse(value.source_url).hostname or "").lower()
    if host not in official_domains and not any(
        host.endswith(f".{item}") for item in official_domains
    ):
        errors.append("source_domain_not_allowed")
    if value.region_code != "CN":
        errors.append("region_not_supported")
    if value.year != requested_year or str(requested_year) not in value.source_title:
        errors.append("calendar_year_mismatch")
    if re.fullmatch(r"[0-9a-f]{64}", value.source_content_sha256) is None:
        errors.append("source_content_sha256_invalid")
    if not value.periods:
        errors.append("holiday_periods_missing")

    holiday_dates: set[date] = set()
    concepts: set[str] = set()
    for period in value.periods:
        if period.start > period.end:
            errors.append("holiday_period_range_invalid")
        if period.start.year != requested_year or period.end.year != requested_year:
            errors.append("holiday_period_year_mismatch")
        if not period.evidence_quote.strip():
            errors.append("holiday_period_evidence_missing")
        concepts.update(item for item in REQUIRED_HOLIDAY_CONCEPTS if item in period.name)
        current = period.start
        while current <= period.end:
            if current in holiday_dates:
                errors.append("holiday_periods_overlap")
            holiday_dates.add(current)
            current += timedelta(days=1)

    adjusted_dates: set[date] = set()
    for item in value.adjusted_workdays:
        if item.service_date.year != requested_year:
            errors.append("adjusted_workday_year_mismatch")
        if not item.evidence_quote.strip():
            errors.append("adjusted_workday_evidence_missing")
        if item.service_date in adjusted_dates:
            errors.append("adjusted_workday_duplicate")
        if item.service_date in holiday_dates:
            errors.append("holiday_adjusted_workday_conflict")
        adjusted_dates.add(item.service_date)
    if concepts != REQUIRED_HOLIDAY_CONCEPTS:
        errors.append("holiday_concepts_incomplete")

    unique_errors = tuple(dict.fromkeys(errors))
    return HolidayCalendarValidation(
        not unique_errors,
        unique_errors,
        None if unique_errors else normalized_calendar_digest(value),
    )


def normalized_calendar_digest(value: ExtractedHolidayCalendar) -> str:
    payload = {
        "region_code": value.region_code,
        "year": value.year,
        "periods": [
            {
                "name": item.name.strip(),
                "start": item.start.isoformat(),
                "end": item.end.isoformat(),
                "evidence_quote": " ".join(item.evidence_quote.split()),
            }
            for item in sorted(value.periods, key=lambda item: (item.start, item.end, item.name))
        ],
        "adjusted_workdays": [
            {
                "date": item.service_date.isoformat(),
                "holiday_name": item.holiday_name.strip(),
                "evidence_quote": " ".join(item.evidence_quote.split()),
            }
            for item in sorted(value.adjusted_workdays, key=lambda item: item.service_date)
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
