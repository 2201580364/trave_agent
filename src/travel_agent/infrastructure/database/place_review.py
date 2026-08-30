"""SQLAlchemy persistence for append-only place review workflow."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, String, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from travel_agent.domain.place_catalog import (
    PlaceReviewDecision,
    PlaceReviewTask,
    PlaceRevision,
)

from .place_catalog import PlaceRevisionRow, _revision_from_row, _revision_values
from .planning import Base


class PlaceReviewTaskRow(Base):
    __tablename__ = "place_review_tasks"

    review_task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    place_revision_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    assigned_reviewer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))


class PlaceReviewDecisionRow(Base):
    __tablename__ = "place_review_decisions"

    review_decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    review_task_id: Mapped[str] = mapped_column(String(64), index=True)
    place_revision_id: Mapped[str] = mapped_column(String(64), index=True)
    actor_id: Mapped[str] = mapped_column(String(64), index=True)
    actor_role: Mapped[str] = mapped_column(String(40), index=True)
    decision_kind: Mapped[str] = mapped_column(String(32), index=True)
    reason_code: Mapped[str] = mapped_column(String(64), index=True)
    reason_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), index=True)


class SqlAlchemyPlaceReviewRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_task(self, task_id: str) -> PlaceReviewTask | None:
        row = self._session.get(PlaceReviewTaskRow, task_id)
        return _task_from_row(row) if row is not None else None

    def list_decisions(self, task_id: str) -> tuple[PlaceReviewDecision, ...]:
        rows = self._session.scalars(
            select(PlaceReviewDecisionRow)
            .where(PlaceReviewDecisionRow.review_task_id == task_id)
            .order_by(
                PlaceReviewDecisionRow.created_at.asc(),
                PlaceReviewDecisionRow.review_decision_id.asc(),
            )
        )
        return tuple(_decision_from_row(row) for row in rows)

    def get_revision(self, revision_id: str) -> PlaceRevision | None:
        row = self._session.get(PlaceRevisionRow, revision_id)
        if row is None:
            return None
        return _revision_from_row(row)

    def get_latest_revision(self, place_id: str) -> PlaceRevision | None:
        row = self._session.scalar(
            select(PlaceRevisionRow)
            .where(PlaceRevisionRow.place_id == place_id)
            .order_by(PlaceRevisionRow.revision_number.desc())
            .limit(1)
        )
        return _revision_from_row(row) if row is not None else None

    def add_revision(self, revision: PlaceRevision) -> None:
        self._session.add(PlaceRevisionRow(**_revision_values(revision)))
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise ValueError("place revision already exists") from exc

    def update_revision(
        self,
        revision: PlaceRevision,
        *,
        expected_revision_number: int,
        expected_revision_version: int,
    ) -> None:
        result = self._session.execute(
            update(PlaceRevisionRow)
            .where(
                PlaceRevisionRow.place_revision_id == revision.place_revision_id,
                PlaceRevisionRow.revision_number == expected_revision_number,
                PlaceRevisionRow.revision_version == expected_revision_version,
                PlaceRevisionRow.lifecycle_status == "candidate",
            )
            .values(**_revision_values(revision))
        )
        if result.rowcount != 1:
            raise ValueError("candidate revision version conflict")

    def list_revisions(
        self, *, lifecycle_status: str | None, limit: int, offset: int
    ) -> tuple[PlaceRevision, ...]:
        statement = select(PlaceRevisionRow)
        if lifecycle_status is not None:
            statement = statement.where(
                PlaceRevisionRow.lifecycle_status == lifecycle_status
            )
        rows = self._session.scalars(
            statement.order_by(
                PlaceRevisionRow.created_at.desc(),
                PlaceRevisionRow.place_revision_id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return tuple(_revision_from_row(row) for row in rows)

    def count_revisions(self, *, lifecycle_status: str | None) -> int:
        statement = select(func.count()).select_from(PlaceRevisionRow)
        if lifecycle_status is not None:
            statement = statement.where(
                PlaceRevisionRow.lifecycle_status == lifecycle_status
            )
        return int(self._session.scalar(statement) or 0)

    def get_open_task_for_revision(self, revision_id: str) -> PlaceReviewTask | None:
        row = self._session.scalar(
            select(PlaceReviewTaskRow)
            .where(
                PlaceReviewTaskRow.place_revision_id == revision_id,
                PlaceReviewTaskRow.status.in_(
                    ("ready_for_review", "in_review", "changes_requested")
                ),
            )
            .order_by(PlaceReviewTaskRow.created_at.desc())
        )
        return _task_from_row(row) if row is not None else None

    def list_tasks(
        self, *, status: str | None, limit: int, offset: int
    ) -> tuple[PlaceReviewTask, ...]:
        statement = select(PlaceReviewTaskRow)
        if status is not None:
            statement = statement.where(PlaceReviewTaskRow.status == status)
        rows = self._session.scalars(
            statement.order_by(
                PlaceReviewTaskRow.updated_at.desc(),
                PlaceReviewTaskRow.review_task_id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return tuple(_task_from_row(row) for row in rows)

    def add_task(self, task: PlaceReviewTask) -> None:
        self._session.add(
            PlaceReviewTaskRow(
                review_task_id=task.review_task_id,
                place_revision_id=task.place_revision_id,
                status=task.status,
                assigned_reviewer_id=task.assigned_reviewer_id,
                version=task.version,
                created_by=task.created_by,
                created_at=task.created_at.isoformat(),
                updated_at=task.updated_at.isoformat(),
            )
        )
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise ValueError("review task already exists") from exc

    def add_decision(self, decision: PlaceReviewDecision) -> None:
        self._session.add(
            PlaceReviewDecisionRow(
                review_decision_id=decision.review_decision_id,
                review_task_id=decision.review_task_id,
                place_revision_id=decision.place_revision_id,
                actor_id=decision.actor_id,
                actor_role=decision.actor_role,
                decision_kind=decision.decision_kind,
                reason_code=decision.reason_code,
                reason_text=decision.reason_text,
                created_at=decision.created_at.isoformat(),
            )
        )
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise ValueError("review decision already exists") from exc

    def advance_task(
        self,
        task: PlaceReviewTask,
        *,
        expected_version: int,
        status: str,
        now: datetime,
    ) -> None:
        result = self._session.execute(
            update(PlaceReviewTaskRow)
            .where(
                PlaceReviewTaskRow.review_task_id == task.review_task_id,
                PlaceReviewTaskRow.version == expected_version,
            )
            .values(status=status, version=task.version + 1, updated_at=now.isoformat())
        )
        if result.rowcount != 1:
            raise ValueError("review task version conflict")

    def approve_revision(self, revision_id: str, *, reviewed_at: datetime) -> None:
        result = self._session.execute(
            update(PlaceRevisionRow)
            .where(
                PlaceRevisionRow.place_revision_id == revision_id,
                PlaceRevisionRow.lifecycle_status == "candidate",
            )
            .values(lifecycle_status="human_verified", reviewed_at=reviewed_at.isoformat())
        )
        if result.rowcount != 1:
            raise ValueError("candidate revision is not approvable")


def _task_from_row(row: PlaceReviewTaskRow) -> PlaceReviewTask:
    return PlaceReviewTask(
        row.review_task_id,
        row.place_revision_id,
        row.status,
        row.assigned_reviewer_id,
        row.version,
        row.created_by,
        datetime.fromisoformat(row.created_at),
        datetime.fromisoformat(row.updated_at),
    )


def _decision_from_row(row: PlaceReviewDecisionRow) -> PlaceReviewDecision:
    return PlaceReviewDecision(
        row.review_decision_id,
        row.review_task_id,
        row.place_revision_id,
        row.actor_id,
        row.actor_role,
        row.decision_kind,
        row.reason_code,
        row.reason_text,
        datetime.fromisoformat(row.created_at),
    )
