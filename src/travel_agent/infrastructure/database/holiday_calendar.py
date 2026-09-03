"""SQLAlchemy persistence for immutable annual holiday calendar versions."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Date,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    and_,
    func,
    or_,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from travel_agent.domain.place_catalog.holiday_calendar import (
    HolidayCalendar,
    HolidayPeriod,
)
from travel_agent.domain.place_catalog.holiday_calendar import (
    list_holiday_calendars as list_builtin_holiday_calendars,
)
from travel_agent.domain.place_catalog.holiday_sync import (
    HolidayAdjustedWorkday,
    HolidayCalendarPeriod,
    HolidayCalendarSyncJob,
    HolidayCalendarVersion,
)

from .place_catalog import PlaceDateExceptionRow, PlaceRevisionRow
from .planning import Base

MYSQL_TABLE_ARGS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


class HolidayCalendarRow(Base):
    __tablename__ = "holiday_calendars"
    __table_args__ = (
        UniqueConstraint(
            "region_code", "calendar_year", "version", name="uq_holiday_calendar_version"
        ),
        UniqueConstraint(
            "region_code", "calendar_year", "normalized_digest", name="uq_holiday_calendar_content"
        ),
        MYSQL_TABLE_ARGS,
    )

    holiday_calendar_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    region_code: Mapped[str] = mapped_column(String(16), index=True)
    calendar_year: Mapped[int] = mapped_column(Integer, index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    source_record_id: Mapped[str] = mapped_column(String(64))
    source_content_sha256: Mapped[str] = mapped_column(String(64))
    normalized_digest: Mapped[str] = mapped_column(String(64))
    supersedes_calendar_id: Mapped[str | None] = mapped_column(
        ForeignKey("holiday_calendars.holiday_calendar_id"), nullable=True
    )
    published_at: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))


class HolidayPeriodRow(Base):
    __tablename__ = "holiday_periods"
    __table_args__ = (
        UniqueConstraint("holiday_calendar_id", "display_order", name="uq_holiday_period_order"),
        MYSQL_TABLE_ARGS,
    )

    holiday_period_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    holiday_calendar_id: Mapped[str] = mapped_column(
        ForeignKey("holiday_calendars.holiday_calendar_id"), index=True
    )
    holiday_name: Mapped[str] = mapped_column(String(80))
    start_date: Mapped[Any] = mapped_column(Date)
    end_date: Mapped[Any] = mapped_column(Date)
    evidence_quote: Mapped[str] = mapped_column(String(1000))
    display_order: Mapped[int] = mapped_column(Integer)


class HolidayAdjustedWorkdayRow(Base):
    __tablename__ = "holiday_adjusted_workdays"
    __table_args__ = (
        UniqueConstraint(
            "holiday_calendar_id", "service_date", name="uq_holiday_adjusted_workday_date"
        ),
        MYSQL_TABLE_ARGS,
    )

    adjusted_workday_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    holiday_calendar_id: Mapped[str] = mapped_column(
        ForeignKey("holiday_calendars.holiday_calendar_id"), index=True
    )
    service_date: Mapped[Any] = mapped_column(Date)
    holiday_name: Mapped[str] = mapped_column(String(80))
    evidence_quote: Mapped[str] = mapped_column(String(1000))


class HolidayCalendarSyncJobRow(Base):
    __tablename__ = "holiday_calendar_sync_jobs"
    __table_args__ = MYSQL_TABLE_ARGS

    sync_job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    region_code: Mapped[str] = mapped_column(String(16), index=True)
    calendar_year: Mapped[int] = mapped_column(Integer, index=True)
    mode: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32), index=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    source_published_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validation_result: Mapped[dict[str, Any]] = mapped_column(JSON)
    calendar_id: Mapped[str | None] = mapped_column(
        ForeignKey("holiday_calendars.holiday_calendar_id"), nullable=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer)
    next_retry_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    operation_intent_id: Mapped[str] = mapped_column(String(64), unique=True)
    operation_digest: Mapped[str] = mapped_column(String(64))
    run_lock_key: Mapped[str | None] = mapped_column(String(40), nullable=True, unique=True)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String(40))
    started_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    finished_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class SqlAlchemyHolidayCalendarRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_job(self, job: HolidayCalendarSyncJob) -> None:
        self._session.add(HolidayCalendarSyncJobRow(**_job_values(job)))
        self._session.flush()

    def update_job(self, job: HolidayCalendarSyncJob) -> None:
        row = self._session.get(HolidayCalendarSyncJobRow, job.job_id)
        if row is None:
            raise ValueError("holiday calendar sync job not found")
        for key, value in _job_values(job).items():
            if key != "sync_job_id":
                setattr(row, key, value)
        if job.status != "running":
            row.run_lock_key = None
        self._session.flush()

    def get_job(self, job_id: str) -> HolidayCalendarSyncJob | None:
        row = self._session.get(HolidayCalendarSyncJobRow, job_id)
        return None if row is None else _job_from_row(row)

    def get_job_by_operation_intent(
        self, operation_intent_id: str
    ) -> HolidayCalendarSyncJob | None:
        row = self._session.execute(
            select(HolidayCalendarSyncJobRow).where(
                HolidayCalendarSyncJobRow.operation_intent_id == operation_intent_id
            )
        ).scalar_one_or_none()
        return None if row is None else _job_from_row(row)

    def list_jobs(
        self,
        *,
        region_code: str = "CN",
        year: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[HolidayCalendarSyncJob, ...]:
        statement = select(HolidayCalendarSyncJobRow).where(
            HolidayCalendarSyncJobRow.region_code == region_code
        )
        if year is not None:
            statement = statement.where(HolidayCalendarSyncJobRow.calendar_year == year)
        if status is not None:
            statement = statement.where(HolidayCalendarSyncJobRow.status == status)
        rows = self._session.execute(
            statement.order_by(HolidayCalendarSyncJobRow.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).scalars().all()
        return tuple(_job_from_row(row) for row in rows)

    def claim_job(self, job_id: str, *, now: datetime) -> HolidayCalendarSyncJob | None:
        now_value = now.isoformat()
        eligible = or_(
            HolidayCalendarSyncJobRow.status == "queued",
            and_(
                HolidayCalendarSyncJobRow.status == "temporarily_unavailable",
                HolidayCalendarSyncJobRow.next_retry_at.is_not(None),
                HolidayCalendarSyncJobRow.next_retry_at <= now_value,
            ),
        )
        try:
            result = self._session.execute(
                update(HolidayCalendarSyncJobRow)
                .where(HolidayCalendarSyncJobRow.sync_job_id == job_id, eligible)
                .values(
                    status="running",
                    attempt_count=HolidayCalendarSyncJobRow.attempt_count + 1,
                    started_at=now_value,
                    finished_at=None,
                    next_retry_at=None,
                    run_lock_key=self._run_lock_key(job_id),
                )
            )
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            return None
        if result.rowcount != 1:
            return None
        return self.get_job(job_id)

    def claim_next(
        self, *, now: datetime, stale_before: datetime
    ) -> HolidayCalendarSyncJob | None:
        self._session.execute(
            update(HolidayCalendarSyncJobRow)
            .where(
                HolidayCalendarSyncJobRow.status == "running",
                HolidayCalendarSyncJobRow.started_at.is_not(None),
                HolidayCalendarSyncJobRow.started_at < stale_before.isoformat(),
            )
            .values(
                status="queued",
                started_at=None,
                run_lock_key=None,
                validation_result={"recovered": True, "reason": "worker_lease_expired"},
            )
        )
        now_value = now.isoformat()
        row = self._session.execute(
            select(HolidayCalendarSyncJobRow)
            .where(
                or_(
                    HolidayCalendarSyncJobRow.status == "queued",
                    and_(
                        HolidayCalendarSyncJobRow.status == "temporarily_unavailable",
                        HolidayCalendarSyncJobRow.next_retry_at.is_not(None),
                        HolidayCalendarSyncJobRow.next_retry_at <= now_value,
                    ),
                )
            )
            .order_by(HolidayCalendarSyncJobRow.created_at)
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            return None
        return self.claim_job(row.sync_job_id, now=now)

    def _run_lock_key(self, job_id: str) -> str:
        row = self._session.get(HolidayCalendarSyncJobRow, job_id)
        if row is None:
            raise ValueError("holiday calendar sync job not found")
        return f"{row.region_code}:{row.calendar_year}"

    def get_published(self, region_code: str, year: int) -> HolidayCalendarVersion | None:
        row = self._session.execute(
            select(HolidayCalendarRow)
            .where(
                HolidayCalendarRow.region_code == region_code,
                HolidayCalendarRow.calendar_year == year,
                HolidayCalendarRow.status == "published",
            )
            .order_by(HolidayCalendarRow.version.desc())
        ).scalars().first()
        return None if row is None else self._calendar_from_row(row)

    def get_calendar(self, calendar_id: str) -> HolidayCalendarVersion | None:
        row = self._session.get(HolidayCalendarRow, calendar_id)
        return None if row is None else self._calendar_from_row(row)

    def list_published(self, region_code: str = "CN") -> tuple[HolidayCalendarVersion, ...]:
        rows = self._session.execute(
            select(HolidayCalendarRow)
            .where(
                HolidayCalendarRow.region_code == region_code,
                HolidayCalendarRow.status == "published",
            )
            .order_by(HolidayCalendarRow.calendar_year, HolidayCalendarRow.version)
        ).scalars().all()
        return tuple(self._calendar_from_row(row) for row in rows)

    def get_by_digest(
        self, region_code: str, year: int, digest: str
    ) -> HolidayCalendarVersion | None:
        row = self._session.execute(
            select(HolidayCalendarRow).where(
                HolidayCalendarRow.region_code == region_code,
                HolidayCalendarRow.calendar_year == year,
                HolidayCalendarRow.normalized_digest == digest,
            )
        ).scalar_one_or_none()
        return None if row is None else self._calendar_from_row(row)

    def next_version(self, region_code: str, year: int) -> int:
        row = self._session.execute(
            select(HolidayCalendarRow.version)
            .where(
                HolidayCalendarRow.region_code == region_code,
                HolidayCalendarRow.calendar_year == year,
            )
            .order_by(HolidayCalendarRow.version.desc())
        ).scalars().first()
        return 1 if row is None else row + 1

    def publish(self, calendar: HolidayCalendarVersion) -> None:
        if calendar.status != "published":
            raise ValueError("new holiday calendar must be published")
        current = self.get_published(calendar.region_code, calendar.year)
        if current is not None and current.calendar_id != calendar.supersedes_calendar_id:
            raise ValueError("holiday calendar supersedes target is stale")
        if current is not None:
            self._session.execute(
                update(HolidayCalendarRow)
                .where(
                    HolidayCalendarRow.holiday_calendar_id == current.calendar_id,
                    HolidayCalendarRow.status == "published",
                )
                .values(status="superseded", updated_at=calendar.published_at.isoformat())
            )
        self._session.add(HolidayCalendarRow(**_calendar_values(calendar)))
        self._session.add_all(
            HolidayPeriodRow(
                holiday_period_id=item.period_id,
                holiday_calendar_id=calendar.calendar_id,
                holiday_name=item.name,
                start_date=item.start,
                end_date=item.end,
                evidence_quote=item.evidence_quote,
                display_order=item.display_order,
            )
            for item in calendar.periods
        )
        self._session.add_all(
            HolidayAdjustedWorkdayRow(
                adjusted_workday_id=item.adjusted_workday_id,
                holiday_calendar_id=calendar.calendar_id,
                service_date=item.service_date,
                holiday_name=item.holiday_name,
                evidence_quote=item.evidence_quote,
            )
            for item in calendar.adjusted_workdays
        )
        self._session.flush()

    def list_materialized_places(
        self, calendar_ids: tuple[str, ...]
    ) -> tuple[tuple[str, str, str, int], ...]:
        if not calendar_ids:
            return ()
        rows = self._session.execute(
            select(
                PlaceRevisionRow.place_revision_id,
                PlaceRevisionRow.canonical_name,
                PlaceRevisionRow.admin_area,
                func.count(PlaceDateExceptionRow.date_exception_id),
            )
            .join(
                PlaceDateExceptionRow,
                PlaceDateExceptionRow.place_revision_id
                == PlaceRevisionRow.place_revision_id,
            )
            .where(
                PlaceDateExceptionRow.holiday_calendar_id.in_(calendar_ids),
                PlaceDateExceptionRow.active.is_(True),
            )
            .group_by(
                PlaceRevisionRow.place_revision_id,
                PlaceRevisionRow.canonical_name,
                PlaceRevisionRow.admin_area,
            )
            .order_by(PlaceRevisionRow.canonical_name)
        ).all()
        return tuple((row[0], row[1], row[2], int(row[3])) for row in rows)

    def _calendar_from_row(self, row: HolidayCalendarRow) -> HolidayCalendarVersion:
        periods = self._session.execute(
            select(HolidayPeriodRow)
            .where(HolidayPeriodRow.holiday_calendar_id == row.holiday_calendar_id)
            .order_by(HolidayPeriodRow.display_order)
        ).scalars().all()
        workdays = self._session.execute(
            select(HolidayAdjustedWorkdayRow)
            .where(HolidayAdjustedWorkdayRow.holiday_calendar_id == row.holiday_calendar_id)
            .order_by(HolidayAdjustedWorkdayRow.service_date)
        ).scalars().all()
        return HolidayCalendarVersion(
            row.holiday_calendar_id,
            row.region_code,
            row.calendar_year,
            row.version,
            row.status,
            row.display_name,
            row.source_record_id,
            row.source_content_sha256,
            row.normalized_digest,
            tuple(
                HolidayCalendarPeriod(
                    item.holiday_period_id,
                    item.holiday_name,
                    item.start_date,
                    item.end_date,
                    item.evidence_quote,
                    item.display_order,
                )
                for item in periods
            ),
            tuple(
                HolidayAdjustedWorkday(
                    item.adjusted_workday_id,
                    item.service_date,
                    item.holiday_name,
                    item.evidence_quote,
                )
                for item in workdays
            ),
            row.supersedes_calendar_id,
            datetime.fromisoformat(row.published_at),
            datetime.fromisoformat(row.created_at),
            datetime.fromisoformat(row.updated_at),
        )


class SqlAlchemyHolidayCalendarUnitOfWork:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def __enter__(self) -> SqlAlchemyHolidayCalendarUnitOfWork:
        from .admin_identity import SqlAlchemyAdminAuditRepository

        self._session = self._sessions()
        self.calendars = SqlAlchemyHolidayCalendarRepository(self._session)
        self.audits = SqlAlchemyAdminAuditRepository(self._session)
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if exc_type is not None:
            self._session.rollback()
        self._session.close()

    def commit(self) -> None:
        self._session.commit()


def _calendar_values(calendar: HolidayCalendarVersion) -> dict[str, Any]:
    return {
        "holiday_calendar_id": calendar.calendar_id,
        "region_code": calendar.region_code,
        "calendar_year": calendar.year,
        "version": calendar.version,
        "status": calendar.status,
        "display_name": calendar.display_name,
        "source_record_id": calendar.source_record_id,
        "source_content_sha256": calendar.source_content_sha256,
        "normalized_digest": calendar.normalized_digest,
        "supersedes_calendar_id": calendar.supersedes_calendar_id,
        "published_at": calendar.published_at.isoformat(),
        "created_at": calendar.created_at.isoformat(),
        "updated_at": calendar.updated_at.isoformat(),
    }


def _job_values(job: HolidayCalendarSyncJob) -> dict[str, Any]:
    return {
        "sync_job_id": job.job_id,
        "region_code": job.region_code,
        "calendar_year": job.year,
        "mode": job.mode,
        "status": job.status,
        "source_url": job.source_url,
        "source_title": job.source_title,
        "source_published_at": _iso(job.source_published_at),
        "source_content_sha256": job.source_content_sha256,
        "validation_result": job.validation_result,
        "calendar_id": job.calendar_id,
        "attempt_count": job.attempt_count,
        "next_retry_at": _iso(job.next_retry_at),
        "operation_intent_id": job.operation_intent_id,
        "operation_digest": job.operation_digest,
        "created_by": job.created_by,
        "created_at": job.created_at.isoformat(),
        "started_at": _iso(job.started_at),
        "finished_at": _iso(job.finished_at),
    }


def _job_from_row(row: HolidayCalendarSyncJobRow) -> HolidayCalendarSyncJob:
    return HolidayCalendarSyncJob(
        row.sync_job_id,
        row.region_code,
        row.calendar_year,
        row.mode,
        row.status,
        row.validation_result,
        row.attempt_count,
        row.operation_intent_id,
        row.operation_digest,
        row.created_by,
        datetime.fromisoformat(row.created_at),
        row.source_url,
        row.source_title,
        _datetime(row.source_published_at),
        row.source_content_sha256,
        row.calendar_id,
        _datetime(row.next_retry_at),
        _datetime(row.started_at),
        _datetime(row.finished_at),
    )


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _datetime(value: str | None) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value)


class SqlAlchemyPublishedHolidayCalendarCatalog:
    """Expose only database-published versions through the stable O05 value shape."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def list_calendars(self) -> tuple[HolidayCalendar, ...]:
        with self._sessions() as session:
            versions = SqlAlchemyHolidayCalendarRepository(session).list_published()
            return tuple(_legacy_calendar(item) for item in versions)

    def get_calendar(self, calendar_id: str) -> HolidayCalendar:
        with self._sessions() as session:
            version = SqlAlchemyHolidayCalendarRepository(session).get_calendar(calendar_id)
            if version is None or version.status != "published":
                raise ValueError(f"unknown published holiday calendar: {calendar_id}")
            return _legacy_calendar(version)


def ensure_builtin_holiday_calendar_seeds(sessions: sessionmaker[Session]) -> None:
    """Idempotently migrate the reviewed 2025/2026 code catalog into published rows."""
    now = datetime(2026, 9, 3, tzinfo=UTC)
    with sessions() as session:
        repository = SqlAlchemyHolidayCalendarRepository(session)
        try:
            for builtin in list_builtin_holiday_calendars():
                year = builtin.periods[0].start.year
                if repository.get_published("CN", year) is not None:
                    continue
                digest = hashlib.sha256(
                    "|".join(
                        f"{item.name}:{item.start.isoformat()}:{item.end.isoformat()}"
                        for item in builtin.periods
                    ).encode("utf-8")
                ).hexdigest()
                repository.publish(
                    HolidayCalendarVersion(
                        builtin.calendar_id,
                        "CN",
                        year,
                        1,
                        "published",
                        builtin.display_name,
                        f"legacy_verified_cn_holiday_{year}",
                        hashlib.sha256(
                            builtin.source_note.encode("utf-8")
                        ).hexdigest(),
                        digest,
                        tuple(
                            HolidayCalendarPeriod(
                                f"{builtin.calendar_id}-period-{index}",
                                item.name,
                                item.start,
                                item.end,
                                builtin.source_note,
                                index,
                            )
                            for index, item in enumerate(builtin.periods, start=1)
                        ),
                        (),
                        None,
                        now,
                        now,
                        now,
                    )
                )
            session.commit()
        except OperationalError:
            session.rollback()
            # Composition may be built solely to expose readiness while the
            # database is still on an older revision. Migration remains the
            # only supported way to create these tables.
            return


def _legacy_calendar(version: HolidayCalendarVersion) -> HolidayCalendar:
    return HolidayCalendar(
        version.calendar_id,
        version.display_name,
        tuple(HolidayPeriod(item.name, item.start, item.end) for item in version.periods),
        f"数据库已发布第 {version.version} 版；来源记录：{version.source_record_id}",
        version.source_record_id,
    )
