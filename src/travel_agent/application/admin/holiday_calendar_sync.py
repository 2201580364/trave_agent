"""Application orchestration for the O17 China holiday calendar sync boundary."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from types import TracebackType
from typing import Protocol, Self

from travel_agent.application.common.clock import Clock
from travel_agent.application.common.errors import ResourceNotFoundError
from travel_agent.application.planning.ports import IdGenerator
from travel_agent.domain.admin import AdminAuditEvent
from travel_agent.domain.place_catalog.holiday_sync import (
    SYNC_JOB_MODES,
    ExtractedHolidayCalendar,
    HolidayAdjustedWorkday,
    HolidayCalendarPeriod,
    HolidayCalendarSyncJob,
    HolidayCalendarVersion,
    validate_extracted_calendar,
)


class HolidayCalendarRepository(Protocol):
    def add_job(self, job: HolidayCalendarSyncJob) -> None: ...
    def update_job(self, job: HolidayCalendarSyncJob) -> None: ...
    def get_job(self, job_id: str) -> HolidayCalendarSyncJob | None: ...
    def get_job_by_operation_intent(
        self, operation_intent_id: str
    ) -> HolidayCalendarSyncJob | None: ...
    def list_jobs(
        self,
        *,
        region_code: str = "CN",
        year: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[HolidayCalendarSyncJob, ...]: ...
    def claim_job(
        self, job_id: str, *, now: datetime
    ) -> HolidayCalendarSyncJob | None: ...
    def claim_next(
        self, *, now: datetime, stale_before: datetime
    ) -> HolidayCalendarSyncJob | None: ...
    def get_published(self, region_code: str, year: int) -> HolidayCalendarVersion | None: ...
    def get_calendar(self, calendar_id: str) -> HolidayCalendarVersion | None: ...
    def get_by_digest(
        self, region_code: str, year: int, digest: str
    ) -> HolidayCalendarVersion | None: ...
    def next_version(self, region_code: str, year: int) -> int: ...
    def publish(self, calendar: HolidayCalendarVersion) -> None: ...
    def list_materialized_places(
        self, calendar_ids: tuple[str, ...]
    ) -> tuple[tuple[str, str, str, int], ...]: ...


class HolidayCalendarAuditRepository(Protocol):
    def add(self, event: AdminAuditEvent) -> None: ...


class HolidayCalendarUnitOfWork(Protocol):
    calendars: HolidayCalendarRepository
    audits: HolidayCalendarAuditRepository

    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...
    def commit(self) -> None: ...


@dataclass(frozen=True, slots=True)
class OfficialHolidayAnnouncement:
    source_url: str
    source_title: str
    source_record_id: str
    published_at: datetime | None = None


class OfficialAnnouncementDiscoverer(Protocol):
    def discover(self, *, year: int) -> OfficialHolidayAnnouncement | None: ...


class OfficialAnnouncementFetcher(Protocol):
    def fetch(self, announcement: OfficialHolidayAnnouncement) -> bytes: ...


class HolidayAnnouncementExtractor(Protocol):
    def extract(
        self,
        *,
        announcement: OfficialHolidayAnnouncement,
        content: bytes,
        content_sha256: str,
        year: int,
    ) -> ExtractedHolidayCalendar: ...


class OfficialSourceTemporarilyUnavailable(RuntimeError):
    """Discovery or retrieval failed; this must never become not_announced."""


class HolidayExtractionError(RuntimeError):
    pass


class HolidayExtractionTemporarilyUnavailable(RuntimeError):
    """The configured structured extraction provider cannot currently respond."""


@dataclass(frozen=True, slots=True)
class HolidayCalendarImpact:
    calendar_id: str
    compared_calendar_id: str | None
    added_holiday_dates: tuple[date, ...]
    removed_holiday_dates: tuple[date, ...]
    added_adjusted_workdays: tuple[date, ...]
    removed_adjusted_workdays: tuple[date, ...]
    affected_places: tuple[tuple[str, str, str, int], ...]

    @property
    def changed_date_count(self) -> int:
        return len(
            set(self.added_holiday_dates)
            | set(self.removed_holiday_dates)
            | set(self.added_adjusted_workdays)
            | set(self.removed_adjusted_workdays)
        )


@dataclass(frozen=True, slots=True)
class HolidayCalendarPeriodInput:
    name: str
    start: date
    end: date
    evidence_quote: str

    @staticmethod
    def to_domain(item: HolidayCalendarPeriodInput) -> HolidayCalendarPeriod:
        return HolidayCalendarPeriod(
            "preview", item.name, item.start, item.end, item.evidence_quote, 0
        )


@dataclass(frozen=True, slots=True)
class HolidayWorkdayInput:
    service_date: date
    holiday_name: str
    evidence_quote: str

    @staticmethod
    def to_domain(item: HolidayWorkdayInput) -> HolidayAdjustedWorkday:
        return HolidayAdjustedWorkday(
            "preview", item.service_date, item.holiday_name, item.evidence_quote
        )


class ChinaHolidayCalendarSyncService:
    def __init__(
        self,
        uow_factory: Callable[[], HolidayCalendarUnitOfWork],
        clock: Clock,
        ids: IdGenerator,
        discoverer: OfficialAnnouncementDiscoverer | None = None,
        fetcher: OfficialAnnouncementFetcher | None = None,
        extractor: HolidayAnnouncementExtractor | None = None,
        worker_available: bool = True,
        job_submission_available: bool = True,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._ids = ids
        self._discoverer = discoverer
        self._fetcher = fetcher
        self._extractor = extractor
        self._worker_available = worker_available
        self._job_submission_available = job_submission_available

    @property
    def execution_available(self) -> bool:
        return (
            self._discoverer is not None
            and self._fetcher is not None
            and self._extractor is not None
            and self._worker_available
        )

    @property
    def job_submission_available(self) -> bool:
        return self._job_submission_available

    def list_jobs(
        self,
        *,
        year: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[HolidayCalendarSyncJob, ...]:
        with self._uow_factory() as uow:
            return uow.calendars.list_jobs(
                year=year, status=status, limit=limit, offset=offset
            )

    def get_job(self, job_id: str) -> HolidayCalendarSyncJob:
        with self._uow_factory() as uow:
            job = uow.calendars.get_job(job_id)
            if job is None:
                raise ResourceNotFoundError
            return job

    def cancel_job(self, job_id: str, *, cancelled_by: str) -> HolidayCalendarSyncJob:
        with self._uow_factory() as uow:
            job = uow.calendars.get_job(job_id)
            if job is None:
                raise ResourceNotFoundError
            if job.status not in {"queued", "temporarily_unavailable"}:
                raise ValueError("当前状态的同步任务无法取消；正在执行的任务会自然完成")
            cancelled = job.transition(
                "cancelled", at=self._clock.now(),
                validation_result={"valid": False, "reason": "cancelled_by_operator"},
                next_retry_at=None,
            )
            uow.calendars.update_job(cancelled)
            uow.audits.add(AdminAuditEvent(
                self._ids.new_id("admin_audit"), cancelled_by, "data_editor",
                "HOLIDAY_CALENDAR_SYNC_CANCELLED", "holiday_calendar_sync_job", job_id,
                None, None, job.operation_digest, "HOLIDAY_SYNC_CANCELLED",
                f"取消 {job.year} 年中国法定节假日历同步任务", job_id,
                job.operation_intent_id, job.operation_digest, "succeeded", None,
                cancelled.finished_at or self._clock.now(),
            ))
            uow.commit()
            return cancelled

    def get_calendar(self, calendar_id: str) -> HolidayCalendarVersion:
        with self._uow_factory() as uow:
            calendar = uow.calendars.get_calendar(calendar_id)
            if calendar is None:
                raise ResourceNotFoundError
            return calendar

    def get_calendar_impact(self, calendar_id: str) -> HolidayCalendarImpact:
        with self._uow_factory() as uow:
            calendar = uow.calendars.get_calendar(calendar_id)
            if calendar is None:
                raise ResourceNotFoundError
            previous = (
                uow.calendars.get_calendar(calendar.supersedes_calendar_id)
                if calendar.supersedes_calendar_id
                else None
            )
            new_holidays = _period_dates(calendar.periods)
            old_holidays = _period_dates(previous.periods) if previous else set()
            new_workdays = {item.service_date for item in calendar.adjusted_workdays}
            old_workdays = (
                {item.service_date for item in previous.adjusted_workdays}
                if previous
                else set()
            )
            provenance_ids = tuple(
                item
                for item in (calendar.calendar_id, calendar.supersedes_calendar_id)
                if item is not None
            )
            return HolidayCalendarImpact(
                calendar.calendar_id,
                previous.calendar_id if previous else None,
                tuple(sorted(new_holidays - old_holidays)),
                tuple(sorted(old_holidays - new_holidays)),
                tuple(sorted(new_workdays - old_workdays)),
                tuple(sorted(old_workdays - new_workdays)),
                uow.calendars.list_materialized_places(provenance_ids),
            )

    def confirm_preview(
        self,
        *,
        job_id: str,
        periods: list[dict[str, object]],
        adjusted_workdays: list[dict[str, object]],
        operation_intent_id: str,
        confirmed_by: str,
    ) -> HolidayCalendarSyncJob:
        """Validate operator-edited preview data and publish it atomically."""
        with self._uow_factory() as uow:
            job = uow.calendars.get_job(job_id)
            if job is None:
                raise ResourceNotFoundError
            if (
                job.status == "published"
                and job.validation_result.get("confirmation_operation_intent_id")
                == operation_intent_id
            ):
                return job
            if job.status != "validated_preview":
                raise ValueError("只有预览校验通过的任务才能确认入库")
            if not job.source_url or not job.source_title or not job.source_content_sha256:
                raise ValueError("预览任务缺少完整的官方来源信息，请重新创建预览任务")
            try:
                parsed_periods = tuple(
                    HolidayCalendarPeriodInput(
                        name=str(item.get("name", "")).strip(),
                        start=date.fromisoformat(str(item.get("start", ""))),
                        end=date.fromisoformat(str(item.get("end", ""))),
                        evidence_quote=str(item.get("evidence_quote", "")).strip(),
                    )
                    for item in periods
                )
                parsed_workdays = tuple(
                    HolidayWorkdayInput(
                        service_date=date.fromisoformat(str(item.get("date", ""))),
                        holiday_name=str(item.get("holiday_name", "")).strip(),
                        evidence_quote=str(item.get("evidence_quote", "")).strip(),
                    )
                    for item in adjusted_workdays
                )
            except (TypeError, ValueError) as exc:
                raise ValueError("预览数据日期格式无效，请使用 YYYY-MM-DD") from exc
            extracted = ExtractedHolidayCalendar(
                "CN",
                job.year,
                job.source_url,
                job.source_title,
                f"holiday_source_{job.source_content_sha256[:24]}",
                job.source_content_sha256,
                tuple(
                    HolidayCalendarPeriodInput.to_domain(item)
                    for item in parsed_periods
                ),
                tuple(HolidayWorkdayInput.to_domain(item) for item in parsed_workdays),
            )
            validation = validate_extracted_calendar(extracted, requested_year=job.year)
            if not validation.valid or validation.normalized_digest is None:
                raise ValueError(
                    "调整后的预览数据未通过确定性校验："
                    + "；".join(_validation_error_text(item) for item in validation.errors)
                )
            existing = uow.calendars.get_by_digest(
                "CN", job.year, validation.normalized_digest
            )
            if existing is not None:
                raise ValueError("调整后的内容与已发布版本相同，无需重复发布")
            current = uow.calendars.get_published("CN", job.year)
            now = self._clock.now()
            calendar_id = self._ids.new_id("holiday_calendar")
            calendar = HolidayCalendarVersion(
                calendar_id,
                "CN",
                job.year,
                uow.calendars.next_version("CN", job.year),
                "published",
                f"中国大陆法定节假日历（{job.year}）",
                extracted.source_record_id,
                extracted.source_content_sha256,
                validation.normalized_digest,
                tuple(
                    HolidayCalendarPeriod(
                        self._ids.new_id("holiday_period"),
                        item.name,
                        item.start,
                        item.end,
                        item.evidence_quote,
                        index,
                    )
                    for index, item in enumerate(extracted.periods, start=1)
                ),
                tuple(
                    HolidayAdjustedWorkday(
                        self._ids.new_id("holiday_workday"),
                        item.service_date,
                        item.holiday_name,
                        item.evidence_quote,
                    )
                    for item in extracted.adjusted_workdays
                ),
                current.calendar_id if current else None,
                now,
                now,
                now,
            )
            finished = job.transition(
                "published",
                at=now,
                validation_result={
                    "valid": True,
                    "errors": [],
                    "confirmed_from_preview": True,
                    "confirmation_operation_intent_id": operation_intent_id,
                },
                calendar_id=calendar_id,
                source_url=extracted.source_url,
                source_title=extracted.source_title,
                source_content_sha256=extracted.source_content_sha256,
            )
            uow.calendars.publish(calendar)
            uow.calendars.update_job(finished)
            uow.audits.add(
                AdminAuditEvent(
                    self._ids.new_id("admin_audit"),
                    confirmed_by,
                    "data_editor",
                    "HOLIDAY_CALENDAR_PREVIEW_CONFIRMED",
                    "holiday_calendar",
                    calendar_id,
                    str(calendar.version),
                    None if current is None else current.normalized_digest,
                    calendar.normalized_digest,
                    "HOLIDAY_CALENDAR_PREVIEW_CONFIRMED",
                    f"确认并发布 {job.year} 年中国法定节假日历",
                    job.job_id,
                    operation_intent_id,
                    validation.normalized_digest,
                    "succeeded",
                    None,
                    now,
                )
            )
            uow.commit()
            return finished

    def create_job(
        self,
        *,
        year: int,
        mode: str,
        operation_intent_id: str,
        created_by: str,
        region_code: str = "CN",
    ) -> HolidayCalendarSyncJob:
        if region_code != "CN":
            raise ValueError("only China mainland holiday calendars are supported")
        if mode not in SYNC_JOB_MODES:
            raise ValueError("holiday calendar sync mode is invalid")
        if year < 2000 or year > 2200:
            raise ValueError("holiday calendar year is invalid")
        digest = _operation_digest(region_code, year, mode)
        with self._uow_factory() as uow:
            existing = uow.calendars.get_job_by_operation_intent(operation_intent_id)
            if existing is not None:
                if existing.operation_digest != digest:
                    raise ValueError("operation intent was already used for different input")
                return existing
            job = HolidayCalendarSyncJob(
                self._ids.new_id("holiday_sync_job"),
                region_code,
                year,
                mode,
                "queued",
                {},
                0,
                operation_intent_id,
                digest,
                created_by,
                self._clock.now(),
            )
            uow.calendars.add_job(job)
            uow.audits.add(
                AdminAuditEvent(
                    self._ids.new_id("admin_audit"),
                    created_by,
                    "data_editor",
                    "HOLIDAY_CALENDAR_SYNC_QUEUED",
                    "holiday_calendar_sync_job",
                    job.job_id,
                    None,
                    None,
                    digest,
                    "HOLIDAY_CALENDAR_SYNC_REQUESTED",
                    f"请求同步 {year} 年中国法定节假日历",
                    job.job_id,
                    None,
                    None,
                    "succeeded",
                    None,
                    job.created_at,
                )
            )
            uow.commit()
            return job

    def run(self, job_id: str) -> HolidayCalendarSyncJob:
        self._ensure_adapters()
        with self._uow_factory() as uow:
            job = uow.calendars.claim_job(job_id, now=self._clock.now())
            if job is None:
                existing = uow.calendars.get_job(job_id)
                if existing is None:
                    raise ResourceNotFoundError
                return existing
            uow.commit()
        return self._execute(job)

    def run_next(
        self, *, stale_after: timedelta = timedelta(minutes=15)
    ) -> HolidayCalendarSyncJob | None:
        self._ensure_adapters()
        now = self._clock.now()
        with self._uow_factory() as uow:
            job = uow.calendars.claim_next(now=now, stale_before=now - stale_after)
            if job is None:
                uow.commit()
                return None
            uow.commit()
        return self._execute(job)

    def _ensure_adapters(self) -> None:
        if self._discoverer is None or self._fetcher is None or self._extractor is None:
            raise RuntimeError("holiday calendar sync adapters are not configured")

    def _execute(self, job: HolidayCalendarSyncJob) -> HolidayCalendarSyncJob:
        assert self._discoverer is not None
        assert self._fetcher is not None
        assert self._extractor is not None
        try:
            job = self._update_progress(job, "discovering", "正在中国政府网查找正式公告")
            announcement = self._discoverer.discover(year=job.year)
            if announcement is None:
                if job.year < self._clock.now().year:
                    return self._finish(
                        job,
                        "needs_attention",
                        {
                            "valid": False,
                            "reason": "historical_announcement_not_found",
                            "detail": "历史年度已过公告发布时间，但官方检索结果未返回匹配公告",
                        },
                    )
                return self._finish(
                    job,
                    "not_announced",
                    {"valid": False, "reason": "official_announcement_not_found"},
                )
            announcement_changes = {
                "source_url": announcement.source_url,
                "source_title": announcement.source_title,
                "source_published_at": announcement.published_at,
            }
            job = self._update_progress(job, "fetching", "已找到公告，正在获取官方正文")
            content = self._fetcher.fetch(announcement)
            content_sha256 = hashlib.sha256(content).hexdigest()
            job = self._update_progress(
                job,
                "extracting",
                "正文已获取，AI 正在提取节假日和调休信息（官方正文较长，可能需要一些时间）",
            )
            extracted = self._extractor.extract(
                announcement=announcement,
                content=content,
                content_sha256=content_sha256,
                year=job.year,
            )
        except OfficialSourceTemporarilyUnavailable as exc:
            return self._finish(
                job,
                "temporarily_unavailable",
                {"valid": False, "reason": "official_source_unavailable", "detail": str(exc)},
                **(announcement_changes if "announcement_changes" in locals() else {}),
            )
        except HolidayExtractionTemporarilyUnavailable as exc:
            return self._finish(
                job,
                "temporarily_unavailable",
                {
                    "valid": False,
                    "reason": "extraction_service_unavailable",
                    "detail": str(exc),
                },
                **(announcement_changes if "announcement_changes" in locals() else {}),
            )
        except (HolidayExtractionError, ValueError) as exc:
            return self._finish(
                job,
                "needs_attention",
                {"valid": False, "reason": "announcement_extraction_failed", "detail": str(exc)},
                **(announcement_changes if "announcement_changes" in locals() else {}),
            )

        source_changes = {
            "source_url": announcement.source_url,
            "source_title": announcement.source_title,
            "source_published_at": announcement.published_at,
            "source_content_sha256": content_sha256,
        }
        if (
            extracted.source_url != announcement.source_url
            or extracted.source_record_id != announcement.source_record_id
            or extracted.source_content_sha256 != content_sha256
        ):
            return self._finish(
                job,
                "needs_attention",
                {"valid": False, "errors": ["extracted_source_binding_mismatch"]},
                **source_changes,
            )
        job = self._update_progress(job, "validating", "正在执行年份、日期、冲突和证据校验")
        validation = validate_extracted_calendar(extracted, requested_year=job.year)
        if not validation.valid or validation.normalized_digest is None:
            return self._finish(
                job,
                "needs_attention",
                {"valid": False, "errors": list(validation.errors)},
                **source_changes,
            )

        with self._uow_factory() as uow:
            same = uow.calendars.get_by_digest(
                job.region_code, job.year, validation.normalized_digest
            )
            if same is not None:
                return self._finish(
                    job,
                    "up_to_date",
                    {"valid": True, "errors": []},
                    calendar_id=same.calendar_id,
                    **source_changes,
                )
            if job.mode == "preview":
                job = self._update_progress(
                    job, "preview_ready", "校验通过，正在生成预览结果"
                )
                return self._finish(
                    job,
                    "validated_preview",
                    {
                        "valid": True,
                        "errors": [],
                        "preview_only": True,
                        "would_create_version": uow.calendars.next_version(
                            job.region_code, job.year
                        ),
                        "preview_periods": [
                            {
                                "name": item.name,
                                "start": item.start.isoformat(),
                                "end": item.end.isoformat(),
                                "evidence_quote": item.evidence_quote,
                            }
                            for item in extracted.periods
                        ],
                        "preview_adjusted_workdays": [
                            {
                                "date": item.service_date.isoformat(),
                                "holiday_name": item.holiday_name,
                                "evidence_quote": item.evidence_quote,
                            }
                            for item in extracted.adjusted_workdays
                        ],
                    },
                    **source_changes,
                )
            job = self._update_progress(
                job, "publishing", "校验通过，正在提交新的年度日历版本"
            )
            current = uow.calendars.get_published(job.region_code, job.year)
            now = self._clock.now()
            calendar_id = self._ids.new_id("holiday_calendar")
            calendar = HolidayCalendarVersion(
                calendar_id,
                job.region_code,
                job.year,
                uow.calendars.next_version(job.region_code, job.year),
                "published",
                f"中国大陆法定节假日历（{job.year}）",
                extracted.source_record_id,
                extracted.source_content_sha256,
                validation.normalized_digest,
                tuple(
                    HolidayCalendarPeriod(
                        self._ids.new_id("holiday_period"),
                        item.name,
                        item.start,
                        item.end,
                        item.evidence_quote,
                        index,
                    )
                    for index, item in enumerate(extracted.periods, start=1)
                ),
                tuple(
                    HolidayAdjustedWorkday(
                        self._ids.new_id("holiday_workday"),
                        item.service_date,
                        item.holiday_name,
                        item.evidence_quote,
                    )
                    for item in extracted.adjusted_workdays
                ),
                None if current is None else current.calendar_id,
                now,
                now,
                now,
            )
            finished = job.transition(
                "published",
                at=now,
                validation_result={
                    "valid": True,
                    "errors": [],
                    "stage": job.validation_result.get("stage", "publishing"),
                    "stage_detail": job.validation_result.get(
                        "stage_detail", "校验通过，正在提交新的年度日历版本"
                    ),
                    "execution_events": job.validation_result.get(
                        "execution_events", []
                    ),
                },
                calendar_id=calendar_id,
                **source_changes,
            )
            uow.calendars.publish(calendar)
            uow.calendars.update_job(finished)
            uow.audits.add(
                AdminAuditEvent(
                    self._ids.new_id("admin_audit"),
                    job.created_by,
                    "data_editor",
                    "HOLIDAY_CALENDAR_PUBLISHED",
                    "holiday_calendar",
                    calendar.calendar_id,
                    str(calendar.version),
                    None if current is None else current.normalized_digest,
                    calendar.normalized_digest,
                    "HOLIDAY_CALENDAR_VALIDATED",
                    f"{job.year} 年中国法定节假日历通过确定性校验并发布",
                    job.job_id,
                    job.operation_intent_id,
                    job.operation_digest,
                    "succeeded",
                    None,
                    now,
                )
            )
            uow.commit()
        return finished

    def _update_progress(
        self, job: HolidayCalendarSyncJob, stage: str, detail: str
    ) -> HolidayCalendarSyncJob:
        events = list(job.validation_result.get("execution_events", []))
        events.append(
            {
                "stage": stage,
                "detail": detail,
                "at": self._clock.now().isoformat(),
            }
        )
        progressed = replace(
            job,
            validation_result={
                **job.validation_result,
                "stage": stage,
                "stage_detail": detail,
                "execution_events": events,
            },
        )
        with self._uow_factory() as uow:
            uow.calendars.update_job(progressed)
            uow.commit()
        return progressed

    def _finish(
        self,
        running_job: HolidayCalendarSyncJob,
        status: str,
        validation_result: dict[str, object],
        **changes: object,
    ) -> HolidayCalendarSyncJob:
        prior_events = list(running_job.validation_result.get("execution_events", []))
        current_stage = running_job.validation_result.get("stage")
        current_detail = running_job.validation_result.get("stage_detail")
        if current_stage and current_detail:
            validation_result = {
                **validation_result,
                "stage": current_stage,
                "stage_detail": current_detail,
            }
        if prior_events:
            validation_result = {
                **validation_result,
                "execution_events": prior_events,
            }
        finished = running_job.transition(
            status,
            at=self._clock.now(),
            validation_result=validation_result,
            next_retry_at=(
                self._clock.now()
                + timedelta(
                    seconds=min(3600, 60 * (2 ** max(0, running_job.attempt_count - 1)))
                )
                if status == "temporarily_unavailable"
                else None
            ),
            **changes,
        )
        with self._uow_factory() as uow:
            uow.calendars.update_job(finished)
            action, reason_code, reason_text = _terminal_audit_fields(finished)
            uow.audits.add(
                AdminAuditEvent(
                    self._ids.new_id("admin_audit"),
                    finished.created_by,
                    "data_editor",
                    action,
                    "holiday_calendar_sync_job",
                    finished.job_id,
                    None,
                    None,
                    finished.source_content_sha256,
                    reason_code,
                    reason_text,
                    finished.job_id,
                    None,
                    None,
                    "succeeded",
                    None,
                    finished.finished_at or self._clock.now(),
                )
            )
            uow.commit()
        return finished


def _operation_digest(region_code: str, year: int, mode: str) -> str:
    raw = json.dumps(
        {"region_code": region_code, "year": year, "mode": mode},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _validation_error_text(code: str) -> str:
    labels = {
        "source_domain_not_allowed": "官方公告来源不是中国政府网",
        "region_not_supported": "仅支持中国大陆节假日历",
        "calendar_year_mismatch": "公告标题或数据年度与目标年度不一致",
        "source_content_sha256_invalid": "官方公告内容指纹无效",
        "holiday_periods_missing": "至少需要一条法定节假日安排",
        "holiday_period_range_invalid": "节假日结束日期早于开始日期",
        "holiday_period_year_mismatch": "节假日日期不属于目标年度",
        "holiday_period_evidence_missing": "节假日缺少官方原文依据",
        "holiday_periods_overlap": "不同节假日的日期范围发生重叠",
        "adjusted_workday_year_mismatch": "调休上班日期不属于目标年度",
        "adjusted_workday_evidence_missing": "调休上班日期缺少官方原文依据",
        "adjusted_workday_duplicate": "调休上班日期重复",
        "holiday_adjusted_workday_conflict": "同一日期同时被标为放假和调休上班",
        "holiday_concepts_incomplete": "元旦、春节、清明、劳动节、端午、中秋、国庆必须完整",
    }
    return labels.get(code, "存在无法识别的数据问题")


def _period_dates(periods: tuple[HolidayCalendarPeriod, ...]) -> set[date]:
    result: set[date] = set()
    for period in periods:
        current = period.start
        while current <= period.end:
            result.add(current)
            current += timedelta(days=1)
    return result


def _terminal_audit_fields(job: HolidayCalendarSyncJob) -> tuple[str, str, str]:
    values = {
        "not_announced": (
            "HOLIDAY_CALENDAR_NOT_ANNOUNCED",
            "OFFICIAL_ANNOUNCEMENT_NOT_FOUND",
            f"{job.year} 年法定节假日安排尚未发布",
        ),
        "temporarily_unavailable": (
            "HOLIDAY_CALENDAR_SYNC_TEMPORARILY_UNAVAILABLE",
            "OFFICIAL_SOURCE_UNAVAILABLE",
            f"暂时无法确认 {job.year} 年官方节假日公告",
        ),
        "needs_attention": (
            "HOLIDAY_CALENDAR_SYNC_NEEDS_ATTENTION",
            "HOLIDAY_CALENDAR_VALIDATION_FAILED",
            f"{job.year} 年节假日公告需要人工关注",
        ),
        "validated_preview": (
            "HOLIDAY_CALENDAR_PREVIEW_VALIDATED",
            "HOLIDAY_CALENDAR_PREVIEW_ONLY",
            f"{job.year} 年节假日历预览校验通过但未发布",
        ),
        "up_to_date": (
            "HOLIDAY_CALENDAR_UP_TO_DATE",
            "HOLIDAY_CALENDAR_CONTENT_UNCHANGED",
            f"{job.year} 年法定节假日历已是最新版本",
        ),
        "cancelled": (
            "HOLIDAY_CALENDAR_SYNC_CANCELLED", "HOLIDAY_SYNC_CANCELLED",
            f"已取消 {job.year} 年法定节假日历同步任务",
        ),
    }
    try:
        return values[job.status]
    except KeyError as exc:
        raise ValueError("holiday calendar terminal audit status is unsupported") from exc
