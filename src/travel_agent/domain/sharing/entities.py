"""M1 plan-sharing entities kept separate from trip retrospectives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PlanShare:
    plan_share_id: str
    plan_share_intent_id: str
    principal_id: str
    trip_id: str
    revision_id: str
    status: str
    template: str
    public_token_hash: str
    share_schema_version: str
    share_snapshot: dict[str, object]
    share_snapshot_hash: str
    created_at: datetime
    published_at: datetime
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        required = (
            self.plan_share_id,
            self.plan_share_intent_id,
            self.principal_id,
            self.trip_id,
            self.revision_id,
            self.public_token_hash,
            self.share_schema_version,
            self.share_snapshot_hash,
        )
        if any(not item for item in required):
            raise ValueError("plan share identity and snapshot fields are required")
        if self.status not in {"published", "revoked"}:
            raise ValueError("plan share status is invalid")
        if self.template != "simple":
            raise ValueError("plan share template is not supported")
        if self.created_at.tzinfo is None or self.published_at.tzinfo is None:
            raise ValueError("plan share timestamps must be timezone-aware")
        if self.revoked_at is not None and self.revoked_at.tzinfo is None:
            raise ValueError("plan share revoked_at must be timezone-aware")
        if self.status == "revoked" and self.revoked_at is None:
            raise ValueError("revoked plan share requires revoked_at")


@dataclass(frozen=True, slots=True)
class PublishedPlanShare:
    plan_share_id: str
    template: str
    share_snapshot: dict[str, object]
    published_at: datetime
