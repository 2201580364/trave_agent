"""Vendor-neutral AI extraction with source-grounded evidence enforcement."""

from __future__ import annotations

import html
import re
from datetime import date
from typing import Any, Protocol

from travel_agent.application.admin.holiday_calendar_sync import (
    HolidayAnnouncementExtractor,
    HolidayExtractionError,
    OfficialHolidayAnnouncement,
)
from travel_agent.domain.place_catalog.holiday_sync import (
    ExtractedHolidayCalendar,
    HolidayAdjustedWorkday,
    HolidayCalendarPeriod,
)

_SCRIPT_STYLE = re.compile(r"<(script|style)\b[\s\S]*?</\1>", re.IGNORECASE)
_HTML_TAG = re.compile(r"<[^>]+>")


class StructuredHolidayModel(Protocol):
    def extract_holiday_calendar(
        self, *, year: int, source_title: str, source_text: str
    ) -> dict[str, Any]: ...


class AiHolidayAnnouncementExtractor(HolidayAnnouncementExtractor):
    def __init__(self, model: StructuredHolidayModel) -> None:
        self._model = model

    def extract(
        self,
        *,
        announcement: OfficialHolidayAnnouncement,
        content: bytes,
        content_sha256: str,
        year: int,
    ) -> ExtractedHolidayCalendar:
        source_text = _html_text(content)
        if not source_text:
            raise HolidayExtractionError("官方公告正文为空或格式暂不支持")
        try:
            payload = self._model.extract_holiday_calendar(
                year=year,
                source_title=announcement.source_title,
                source_text=source_text,
            )
            periods = _periods(payload.get("periods"), year, source_text)
            workdays = _workdays(payload.get("adjusted_workdays"), year, source_text)
        except (KeyError, TypeError, ValueError) as exc:
            raise HolidayExtractionError(
                f"AI 节假日结构化结果不符合受限格式：{exc}"
            ) from exc
        if payload.get("year") != year or payload.get("region") != "CN":
            raise HolidayExtractionError("AI 抽取的地区或年份与任务不一致")
        return ExtractedHolidayCalendar(
            "CN",
            year,
            announcement.source_url,
            announcement.source_title,
            announcement.source_record_id,
            content_sha256,
            periods,
            workdays,
        )


def _html_text(content: bytes) -> str:
    try:
        raw = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HolidayExtractionError("官方公告不是可识别的 UTF-8 HTML") from exc
    without_scripts = _SCRIPT_STYLE.sub(" ", raw)
    return _normalize_text(html.unescape(_HTML_TAG.sub(" ", without_scripts)))


def _periods(value: object, year: int, source_text: str) -> tuple[HolidayCalendarPeriod, ...]:
    if not isinstance(value, list):
        raise TypeError("periods must be a list")
    result: list[HolidayCalendarPeriod] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise TypeError("period must be an object")
        name = _required_text(item, "name")
        quote = _grounded_quote(item, source_text)
        start = date.fromisoformat(_required_text(item, "start"))
        end = date.fromisoformat(_required_text(item, "end"))
        if start.year != year or end.year != year:
            raise ValueError(
                f"period year mismatch: {start.isoformat()} - {end.isoformat()}"
            )
        result.append(
            HolidayCalendarPeriod(f"extracted-period-{index}", name, start, end, quote, index)
        )
    return tuple(result)


def _workdays(
    value: object, year: int, source_text: str
) -> tuple[HolidayAdjustedWorkday, ...]:
    if not isinstance(value, list):
        raise TypeError("adjusted_workdays must be a list")
    result: list[HolidayAdjustedWorkday] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise TypeError("adjusted workday must be an object")
        service_date = date.fromisoformat(_required_text(item, "date"))
        if service_date.year != year:
            raise ValueError("adjusted workday year mismatch")
        result.append(
            HolidayAdjustedWorkday(
                f"extracted-workday-{index}",
                service_date,
                _required_text(item, "holiday_name"),
                _grounded_quote(item, source_text),
            )
        )
    return tuple(result)


def _required_text(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value.strip()


def _grounded_quote(item: dict[str, Any], source_text: str) -> str:
    quote = _required_text(item, "evidence_quote")
    if _normalize_text(quote) not in source_text:
        raise ValueError("evidence quote is not present in official source")
    return quote


def _normalize_text(value: str) -> str:
    return " ".join(value.split())
