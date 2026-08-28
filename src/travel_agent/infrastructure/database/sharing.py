"""SQLAlchemy persistence for immutable M1 plan-share snapshots."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from travel_agent.application.common.errors import PlanShareIntentConflictError
from travel_agent.domain.sharing import PlanShare

from .planning import Base


class PlanShareRow(Base):
    __tablename__ = "plan_shares"

    plan_share_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    plan_share_intent_id: Mapped[str] = mapped_column(String(64), unique=True)
    principal_id: Mapped[str] = mapped_column(String(64), index=True)
    trip_id: Mapped[str] = mapped_column(String(64), index=True)
    revision_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    template: Mapped[str] = mapped_column(String(20))
    public_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    share_schema_version: Mapped[str] = mapped_column(String(32))
    share_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    share_snapshot_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String(40))
    published_at: Mapped[str] = mapped_column(String(40))
    revoked_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class SqlAlchemyPlanShareRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, plan_share_id: str) -> PlanShare | None:
        row = self._session.get(PlanShareRow, plan_share_id)
        return _share_from_row(row) if row is not None else None

    def get_by_intent(self, plan_share_intent_id: str) -> PlanShare | None:
        row = self._session.scalar(
            select(PlanShareRow).where(
                PlanShareRow.plan_share_intent_id == plan_share_intent_id
            )
        )
        return _share_from_row(row) if row is not None else None

    def get_by_public_token_hash(self, public_token_hash: str) -> PlanShare | None:
        row = self._session.scalar(
            select(PlanShareRow).where(
                PlanShareRow.public_token_hash == public_token_hash
            )
        )
        return _share_from_row(row) if row is not None else None

    def add(self, share: PlanShare) -> None:
        self._session.add(PlanShareRow(**_share_values(share)))
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise PlanShareIntentConflictError from exc


def _share_values(share: PlanShare) -> dict[str, Any]:
    return {
        "plan_share_id": share.plan_share_id,
        "plan_share_intent_id": share.plan_share_intent_id,
        "principal_id": share.principal_id,
        "trip_id": share.trip_id,
        "revision_id": share.revision_id,
        "status": share.status,
        "template": share.template,
        "public_token_hash": share.public_token_hash,
        "share_schema_version": share.share_schema_version,
        "share_snapshot": share.share_snapshot,
        "share_snapshot_hash": share.share_snapshot_hash,
        "created_at": share.created_at.isoformat(),
        "published_at": share.published_at.isoformat(),
        "revoked_at": share.revoked_at.isoformat() if share.revoked_at else None,
    }


def _share_from_row(row: PlanShareRow) -> PlanShare:
    from datetime import datetime

    return PlanShare(
        row.plan_share_id,
        row.plan_share_intent_id,
        row.principal_id,
        row.trip_id,
        row.revision_id,
        row.status,
        row.template,
        row.public_token_hash,
        row.share_schema_version,
        row.share_snapshot,
        row.share_snapshot_hash,
        datetime.fromisoformat(row.created_at),
        datetime.fromisoformat(row.published_at),
        datetime.fromisoformat(row.revoked_at) if row.revoked_at else None,
    )
