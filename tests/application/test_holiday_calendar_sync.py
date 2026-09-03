from datetime import UTC, date, datetime, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from travel_agent.application.admin.holiday_calendar_sync import (
    ChinaHolidayCalendarSyncService,
    HolidayExtractionTemporarilyUnavailable,
    OfficialHolidayAnnouncement,
    OfficialSourceTemporarilyUnavailable,
)
from travel_agent.application.admin.holiday_worker import HolidayCalendarSyncWorker
from travel_agent.domain.place_catalog.holiday_sync import (
    ExtractedHolidayCalendar,
    HolidayAdjustedWorkday,
    HolidayCalendarPeriod,
)
from travel_agent.infrastructure.database import (
    Base,
    SqlAlchemyHolidayCalendarRepository,
    SqlAlchemyHolidayCalendarUnitOfWork,
    SqlAlchemyPublishedHolidayCalendarCatalog,
    ensure_builtin_holiday_calendar_seeds,
)

NOW = datetime(2026, 9, 3, 10, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class SequenceIds:
    def __init__(self) -> None:
        self.value = 0

    def new_id(self, prefix: str) -> str:
        self.value += 1
        return f"{prefix}-{self.value}"


class Discoverer:
    def __init__(self, outcome: OfficialHolidayAnnouncement | None | Exception) -> None:
        self.outcome = outcome

    def discover(self, *, year: int) -> OfficialHolidayAnnouncement | None:
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class Fetcher:
    def fetch(self, announcement: OfficialHolidayAnnouncement) -> bytes:
        return b"official announcement body"


class Extractor:
    def __init__(self) -> None:
        self.revision = 1

    def extract(self, *, announcement, content, content_sha256, year):
        names = ("元旦", "春节", "清明节", "劳动节", "端午节", "中秋节", "国庆节")
        return ExtractedHolidayCalendar(
            "CN",
            year,
            announcement.source_url,
            announcement.source_title,
            announcement.source_record_id,
            content_sha256,
            tuple(
                HolidayCalendarPeriod(
                    f"raw-{index}",
                    name,
                    date(year, index, 1),
                    date(year, index, 1),
                    f"{name}放假（抽取版本 {self.revision}）",
                    index,
                )
                for index, name in enumerate(names, start=1)
            ),
            (HolidayAdjustedWorkday("raw-workday", date(year, 2, 6), "春节", "2月6日上班"),),
        )


def _service(tmp_path, discovery, extractor=None):
    engine = create_engine(f"sqlite:///{tmp_path / 'holiday.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    extractor = extractor or Extractor()
    service = ChinaHolidayCalendarSyncService(
        lambda: SqlAlchemyHolidayCalendarUnitOfWork(sessions),
        FixedClock(),
        SequenceIds(),
        Discoverer(discovery),
        Fetcher(),
        extractor,
    )
    return service, sessions, extractor


def test_sync_publishes_once_then_replays_same_content_as_up_to_date(tmp_path) -> None:
    announcement = OfficialHolidayAnnouncement(
        "https://www.gov.cn/zhengce/content/2026/holiday.htm",
        "国务院办公厅关于2027年部分节假日安排的通知",
        "source-2027",
        NOW,
    )
    service, sessions, _ = _service(tmp_path, announcement)
    first = service.create_job(
        year=2027, mode="sync", operation_intent_id="intent-1", created_by="admin"
    )

    published = service.run(first.job_id)
    second = service.create_job(
        year=2027, mode="sync", operation_intent_id="intent-2", created_by="admin"
    )
    unchanged = service.run(second.job_id)

    assert published.status == "published"
    assert [event["stage"] for event in published.validation_result["execution_events"]] == [
        "discovering",
        "fetching",
        "extracting",
        "validating",
        "publishing",
    ]
    assert published.validation_result["stage"] == "publishing"
    assert unchanged.status == "up_to_date"
    assert unchanged.calendar_id == published.calendar_id
    with sessions() as session:
        repository = SqlAlchemyHolidayCalendarRepository(session)
        calendar = repository.get_published("CN", 2027)
        assert calendar is not None
        assert calendar.version == 1
        assert len(calendar.periods) == 7
        audit_action = session.execute(
            text(
                "SELECT action FROM admin_audit_events "
                "WHERE action = 'HOLIDAY_CALENDAR_PUBLISHED'"
            )
        ).scalar_one()
        assert audit_action == "HOLIDAY_CALENDAR_PUBLISHED"


def test_successful_discovery_without_announcement_is_not_announced(tmp_path) -> None:
    service, _, _ = _service(tmp_path, None)
    job = service.create_job(
        year=2027, mode="sync", operation_intent_id="intent-1", created_by="admin"
    )

    result = service.run(job.job_id)

    assert result.status == "not_announced"


def test_historical_missing_announcement_requires_attention_not_not_announced(tmp_path) -> None:
    service, _, _ = _service(tmp_path, None)
    job = service.create_job(
        year=2024, mode="preview", operation_intent_id="historical-missing", created_by="admin"
    )

    result = service.run(job.job_id)

    assert result.status == "needs_attention"
    assert result.validation_result["reason"] == "historical_announcement_not_found"


def test_network_failure_is_temporarily_unavailable_not_not_announced(tmp_path) -> None:
    service, _, _ = _service(
        tmp_path, OfficialSourceTemporarilyUnavailable("TLS timeout")
    )
    job = service.create_job(
        year=2027, mode="sync", operation_intent_id="intent-1", created_by="admin"
    )

    result = service.run(job.job_id)

    assert result.status == "temporarily_unavailable"
    assert result.validation_result["reason"] == "official_source_unavailable"
    assert result.validation_result["stage"] == "discovering"
    assert result.validation_result["execution_events"][0]["detail"] == "正在中国政府网查找正式公告"


class UnavailableExtractor(Extractor):
    def extract(self, *, announcement, content, content_sha256, year):
        raise HolidayExtractionTemporarilyUnavailable("provider timeout")


def test_ai_provider_failure_is_retryable_and_never_not_announced(tmp_path) -> None:
    announcement = OfficialHolidayAnnouncement(
        "https://www.gov.cn/holiday",
        "国务院办公厅关于2027年部分节假日安排的通知",
        "source-2027",
    )
    service, _, _ = _service(tmp_path, announcement, UnavailableExtractor())
    job = service.create_job(
        year=2027, mode="sync", operation_intent_id="ai-timeout", created_by="admin"
    )

    result = service.run(job.job_id)

    assert result.status == "temporarily_unavailable"
    assert result.validation_result["reason"] == "extraction_service_unavailable"
    assert result.validation_result["stage"] == "extracting"
    assert [event["stage"] for event in result.validation_result["execution_events"]] == [
        "discovering",
        "fetching",
        "extracting",
    ]


def test_operation_intent_is_idempotent_and_rejects_changed_input(tmp_path) -> None:
    service, _, _ = _service(tmp_path, None)
    first = service.create_job(
        year=2027, mode="sync", operation_intent_id="same", created_by="admin"
    )
    replay = service.create_job(
        year=2027, mode="sync", operation_intent_id="same", created_by="admin"
    )

    assert replay.job_id == first.job_id


def test_queued_job_can_be_cancelled_and_is_not_claimed(tmp_path) -> None:
    service, _, _ = _service(tmp_path, None)
    job = service.create_job(
        year=2027, mode="preview", operation_intent_id="cancel-1", created_by="admin"
    )

    cancelled = service.cancel_job(job.job_id, cancelled_by="admin")

    assert cancelled.status == "cancelled"
    assert service.run_next() is None


def test_changed_normalized_content_creates_v2_and_supersedes_v1(tmp_path) -> None:
    announcement = OfficialHolidayAnnouncement(
        "https://www.gov.cn/zhengce/content/2026/holiday.htm",
        "国务院办公厅关于2027年部分节假日安排的通知",
        "source-2027",
        NOW,
    )
    service, sessions, extractor = _service(tmp_path, announcement)
    first_job = service.create_job(
        year=2027, mode="sync", operation_intent_id="v1", created_by="admin"
    )
    first = service.run(first_job.job_id)
    with sessions() as session:
        first_digest = SqlAlchemyHolidayCalendarRepository(session).get_published(
            "CN", 2027
        ).normalized_digest
    extractor.revision = 2
    second_job = service.create_job(
        year=2027, mode="sync", operation_intent_id="v2", created_by="admin"
    )

    second = service.run(second_job.job_id)

    assert second.status == "published"
    assert second.calendar_id != first.calendar_id
    with sessions() as session:
        repository = SqlAlchemyHolidayCalendarRepository(session)
        current = repository.get_published("CN", 2027)
        previous = repository.get_by_digest("CN", 2027, first_digest)
        assert current is not None
        assert current.version == 2
        assert current.supersedes_calendar_id == first.calendar_id
        assert previous is not None
        assert previous.status == "superseded"

    impact = service.get_calendar_impact(second.calendar_id)
    assert impact.compared_calendar_id == first.calendar_id
    assert impact.changed_date_count == 0


class InvalidExtractor(Extractor):
    def extract(self, *, announcement, content, content_sha256, year):
        value = super().extract(
            announcement=announcement,
            content=content,
            content_sha256=content_sha256,
            year=year,
        )
        return ExtractedHolidayCalendar(
            value.region_code,
            value.year,
            value.source_url,
            value.source_title,
            value.source_record_id,
            value.source_content_sha256,
            value.periods[:1],
            value.adjusted_workdays,
        )


def test_invalid_extraction_never_publishes_calendar(tmp_path) -> None:
    announcement = OfficialHolidayAnnouncement(
        "https://www.gov.cn/zhengce/content/2026/holiday.htm",
        "国务院办公厅关于2027年部分节假日安排的通知",
        "source-2027",
        NOW,
    )
    service, sessions, _ = _service(tmp_path, announcement, InvalidExtractor())
    job = service.create_job(
        year=2027, mode="sync", operation_intent_id="invalid", created_by="admin"
    )

    result = service.run(job.job_id)

    assert result.status == "needs_attention"
    assert "holiday_concepts_incomplete" in result.validation_result["errors"]
    with sessions() as session:
        assert SqlAlchemyHolidayCalendarRepository(session).get_published("CN", 2027) is None


def test_preview_reports_validated_without_publishing(tmp_path) -> None:
    announcement = OfficialHolidayAnnouncement(
        "https://www.gov.cn/zhengce/content/2026/holiday.htm",
        "国务院办公厅关于2027年部分节假日安排的通知",
        "source-2027",
        NOW,
    )
    service, sessions, _ = _service(tmp_path, announcement)
    job = service.create_job(
        year=2027, mode="preview", operation_intent_id="preview", created_by="admin"
    )

    result = service.run(job.job_id)

    assert result.status == "validated_preview"
    assert result.validation_result["would_create_version"] == 1
    with sessions() as session:
        assert SqlAlchemyHolidayCalendarRepository(session).get_published("CN", 2027) is None


def test_operator_can_edit_validated_preview_and_publish_idempotently(tmp_path) -> None:
    announcement = OfficialHolidayAnnouncement(
        "https://www.gov.cn/zhengce/content/2026/holiday.htm",
        "国务院办公厅关于2027年部分节假日安排的通知",
        "source-2027",
        NOW,
    )
    service, sessions, _ = _service(tmp_path, announcement)
    queued = service.create_job(
        year=2027, mode="preview", operation_intent_id="preview-edit", created_by="admin"
    )
    preview = service.run(queued.job_id)
    periods = list(preview.validation_result["preview_periods"])
    periods[0] = {**periods[0], "evidence_quote": "元旦放假（人工核对修正）"}

    published = service.confirm_preview(
        job_id=preview.job_id,
        periods=periods,
        adjusted_workdays=list(
            preview.validation_result["preview_adjusted_workdays"]
        ),
        operation_intent_id="confirm-preview-edit",
        confirmed_by="reviewer",
    )
    replay = service.confirm_preview(
        job_id=preview.job_id,
        periods=periods,
        adjusted_workdays=list(
            preview.validation_result["preview_adjusted_workdays"]
        ),
        operation_intent_id="confirm-preview-edit",
        confirmed_by="reviewer",
    )

    assert published.status == "published"
    assert replay.calendar_id == published.calendar_id
    with sessions() as session:
        calendar = SqlAlchemyHolidayCalendarRepository(session).get_published("CN", 2027)
        assert calendar is not None
        assert calendar.periods[0].evidence_quote == "元旦放假（人工核对修正）"
        assert calendar.version == 1


class FailingAuditUnitOfWork(SqlAlchemyHolidayCalendarUnitOfWork):
    def __enter__(self):
        result = super().__enter__()
        self.audits = FailingAudits(self.audits)
        return result


class FailingAudits:
    def __init__(self, inner) -> None:
        self.inner = inner

    def add(self, event) -> None:
        if event.action == "HOLIDAY_CALENDAR_PUBLISHED":
            raise RuntimeError("audit storage unavailable")
        self.inner.add(event)


def test_audit_failure_rolls_back_calendar_publication(tmp_path) -> None:
    announcement = OfficialHolidayAnnouncement(
        "https://www.gov.cn/zhengce/content/2026/holiday.htm",
        "国务院办公厅关于2027年部分节假日安排的通知",
        "source-2027",
        NOW,
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'audit-failure.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    service = ChinaHolidayCalendarSyncService(
        lambda: FailingAuditUnitOfWork(sessions),
        FixedClock(),
        SequenceIds(),
        Discoverer(announcement),
        Fetcher(),
        Extractor(),
    )
    job = service.create_job(
        year=2027, mode="sync", operation_intent_id="audit-failure", created_by="admin"
    )

    try:
        service.run(job.job_id)
    except RuntimeError as exc:
        assert str(exc) == "audit storage unavailable"
    else:
        raise AssertionError("audit failure should fail closed")

    with sessions() as session:
        assert SqlAlchemyHolidayCalendarRepository(session).get_published("CN", 2027) is None


def test_builtin_calendars_are_idempotently_seeded_and_read_from_published_rows(
    tmp_path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'seeds.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)

    ensure_builtin_holiday_calendar_seeds(sessions)
    ensure_builtin_holiday_calendar_seeds(sessions)
    catalog = SqlAlchemyPublishedHolidayCalendarCatalog(sessions)

    calendars = catalog.list_calendars()
    assert {item.calendar_id for item in calendars} == {
        "cn-mainland-2025",
        "cn-mainland-2026",
    }
    assert catalog.get_calendar("cn-mainland-2026").periods[0].start.year == 2026


def test_repository_allows_only_one_running_job_per_region_and_year(tmp_path) -> None:
    service, sessions, _ = _service(tmp_path, None)
    first = service.create_job(
        year=2027, mode="sync", operation_intent_id="lock-1", created_by="admin"
    )
    second = service.create_job(
        year=2027, mode="sync", operation_intent_id="lock-2", created_by="admin"
    )

    with sessions() as session:
        repository = SqlAlchemyHolidayCalendarRepository(session)
        claimed = repository.claim_job(first.job_id, now=NOW)
        session.commit()
        assert claimed is not None
    with sessions() as session:
        repository = SqlAlchemyHolidayCalendarRepository(session)
        blocked = repository.claim_job(second.job_id, now=NOW)
        assert blocked is None


def test_worker_recovers_expired_running_lease_and_increments_attempt(tmp_path) -> None:
    service, sessions, _ = _service(tmp_path, None)
    job = service.create_job(
        year=2027, mode="sync", operation_intent_id="stale", created_by="admin"
    )
    with sessions() as session:
        repository = SqlAlchemyHolidayCalendarRepository(session)
        first = repository.claim_job(job.job_id, now=NOW)
        session.commit()
        assert first is not None and first.attempt_count == 1

    recovered_at = NOW + timedelta(minutes=16)
    with sessions() as session:
        repository = SqlAlchemyHolidayCalendarRepository(session)
        recovered = repository.claim_next(
            now=recovered_at,
            stale_before=recovered_at - timedelta(minutes=15),
        )
        session.commit()

    assert recovered is not None
    assert recovered.job_id == job.job_id
    assert recovered.status == "running"
    assert recovered.attempt_count == 2


def test_temporary_failure_records_exponential_retry_time(tmp_path) -> None:
    service, _, _ = _service(
        tmp_path, OfficialSourceTemporarilyUnavailable("timeout")
    )
    job = service.create_job(
        year=2027, mode="sync", operation_intent_id="retry", created_by="admin"
    )

    result = service.run(job.job_id)

    assert result.status == "temporarily_unavailable"
    assert result.next_retry_at == NOW + timedelta(minutes=1)


def test_worker_processes_queued_jobs_until_idle(tmp_path) -> None:
    service, _, _ = _service(tmp_path, None)
    job = service.create_job(
        year=2027, mode="sync", operation_intent_id="worker", created_by="admin"
    )

    result = HolidayCalendarSyncWorker(service).run_batch(max_jobs=5)

    assert result.processed_job_ids == (job.job_id,)
    assert service.get_job(job.job_id).status == "not_announced"
