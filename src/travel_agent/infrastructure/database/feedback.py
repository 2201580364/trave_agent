"""SQLAlchemy persistence for structured M1 itinerary feedback."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from travel_agent.application.common.errors import FeedbackIntentConflictError
from travel_agent.domain.feedback import Feedback

from .planning import Base


class FeedbackRow(Base):
    __tablename__ = "feedbacks"
    __table_args__ = (
        UniqueConstraint(
            "principal_id",
            "revision_id",
            "target_key",
            name="uq_feedbacks_principal_revision_target",
        ),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_0900_ai_ci",
        },
    )

    feedback_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    feedback_intent_id: Mapped[str] = mapped_column(String(64), unique=True)
    principal_id: Mapped[str] = mapped_column(String(64), index=True)
    trip_id: Mapped[str] = mapped_column(String(64), index=True)
    revision_id: Mapped[str] = mapped_column(String(64), index=True)
    feedback_scope: Mapped[str] = mapped_column(String(20), index=True)
    target_key: Mapped[str] = mapped_column(String(96))
    node_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rating: Mapped[str] = mapped_column(String(20), index=True)
    reason_codes: Mapped[list[str]] = mapped_column(JSON)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))


class SqlAlchemyFeedbackRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, feedback_id: str) -> Feedback | None:
        row = self._session.get(FeedbackRow, feedback_id)
        return _feedback_from_row(row) if row is not None else None

    def get_by_intent(self, feedback_intent_id: str) -> Feedback | None:
        row = self._session.scalar(
            select(FeedbackRow).where(
                FeedbackRow.feedback_intent_id == feedback_intent_id
            )
        )
        return _feedback_from_row(row) if row is not None else None

    def get_by_target(
        self,
        principal_id: str,
        revision_id: str,
        target_key: str,
    ) -> Feedback | None:
        row = self._session.scalar(
            select(FeedbackRow).where(
                FeedbackRow.principal_id == principal_id,
                FeedbackRow.revision_id == revision_id,
                FeedbackRow.target_key == target_key,
            )
        )
        return _feedback_from_row(row) if row is not None else None

    def add(self, feedback: Feedback) -> None:
        self._session.add(FeedbackRow(**_feedback_values(feedback)))
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise FeedbackIntentConflictError from exc


def _feedback_values(feedback: Feedback) -> dict[str, Any]:
    return {
        "feedback_id": feedback.feedback_id,
        "feedback_intent_id": feedback.feedback_intent_id,
        "principal_id": feedback.principal_id,
        "trip_id": feedback.trip_id,
        "revision_id": feedback.revision_id,
        "feedback_scope": feedback.feedback_scope,
        "target_key": feedback.target_key,
        "node_id": feedback.node_id,
        "rating": feedback.rating,
        "reason_codes": list(feedback.reason_codes),
        "comment": feedback.comment,
        "created_at": feedback.created_at.isoformat(),
        "updated_at": feedback.updated_at.isoformat(),
    }


def _feedback_from_row(row: FeedbackRow) -> Feedback:
    from datetime import datetime

    return Feedback(
        row.feedback_id,
        row.feedback_intent_id,
        row.principal_id,
        row.trip_id,
        row.revision_id,
        row.feedback_scope,
        row.node_id,
        row.rating,
        tuple(row.reason_codes),
        row.comment,
        datetime.fromisoformat(row.created_at),
        datetime.fromisoformat(row.updated_at),
    )
