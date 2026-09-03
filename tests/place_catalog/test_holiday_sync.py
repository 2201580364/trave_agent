from datetime import UTC, date, datetime

from travel_agent.domain.place_catalog.holiday_sync import (
    ExtractedHolidayCalendar,
    HolidayAdjustedWorkday,
    HolidayCalendarPeriod,
    HolidayCalendarSyncJob,
    normalized_calendar_digest,
    validate_extracted_calendar,
)


def _calendar() -> ExtractedHolidayCalendar:
    names = ("元旦", "春节", "清明节", "劳动节", "端午节", "中秋节", "国庆节")
    periods = tuple(
        HolidayCalendarPeriod(
            f"period-{index}",
            name,
            date(2027, index, 1),
            date(2027, index, 1),
            f"{name}：{index}月1日放假。",
            index,
        )
        for index, name in enumerate(names, start=1)
    )
    return ExtractedHolidayCalendar(
        "CN",
        2027,
        "https://www.gov.cn/zhengce/content/2026/holiday.htm",
        "国务院办公厅关于2027年部分节假日安排的通知",
        "source-2027",
        "a" * 64,
        periods,
        (
            HolidayAdjustedWorkday(
                "workday-1", date(2027, 2, 6), "春节", "2月6日上班。"
            ),
        ),
    )


def test_deterministic_validation_accepts_complete_official_calendar() -> None:
    result = validate_extracted_calendar(_calendar(), requested_year=2027)

    assert result.valid
    assert result.errors == ()
    assert result.normalized_digest == normalized_calendar_digest(_calendar())


def test_deterministic_validation_rejects_unofficial_overlap_and_incomplete_calendar() -> None:
    value = _calendar()
    invalid = ExtractedHolidayCalendar(
        value.region_code,
        value.year,
        "https://example.com/holiday",
        value.source_title,
        value.source_record_id,
        value.source_content_sha256,
        (
            value.periods[0],
            HolidayCalendarPeriod("overlap", "元旦", date(2027, 1, 1), date(2027, 1, 2), "重叠", 2),
        ),
        (),
    )

    result = validate_extracted_calendar(invalid, requested_year=2027)

    assert not result.valid
    assert "source_domain_not_allowed" in result.errors
    assert "holiday_periods_overlap" in result.errors
    assert "holiday_concepts_incomplete" in result.errors
    assert result.normalized_digest is None


def test_network_failure_has_distinct_terminal_status() -> None:
    now = datetime(2026, 9, 3, tzinfo=UTC)
    queued = HolidayCalendarSyncJob(
        "job-1", "CN", 2027, "sync", "queued", {}, 0, "intent", "digest", "actor", now
    )

    running = queued.transition("running", at=now, attempt_count=1)
    unavailable = running.transition(
        "temporarily_unavailable",
        at=now,
        validation_result={"reason": "official_source_unavailable"},
    )

    assert unavailable.status == "temporarily_unavailable"
    assert unavailable.finished_at == now
