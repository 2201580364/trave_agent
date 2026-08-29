"""Human review workflow values for candidate place revisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

REVIEW_TASK_STATUSES = frozenset(
    {"draft", "ready_for_review", "in_review", "changes_requested", "approved", "closed"}
)
REVIEW_DECISION_KINDS = frozenset({"approve", "request_changes", "cancel"})


def _required(*values: str) -> None:
    if any(not value.strip() for value in values):
        raise ValueError("review identity fields are required")


def _aware(value: datetime, field: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class PlaceReviewTask:
    review_task_id: str
    place_revision_id: str
    status: str
    assigned_reviewer_id: str | None
    version: int
    created_by: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _required(self.review_task_id, self.place_revision_id, self.created_by)
        if self.status not in REVIEW_TASK_STATUSES:
            raise ValueError("review task status is invalid")
        if self.version <= 0:
            raise ValueError("review task version must be positive")
        _aware(self.created_at, "review task created_at")
        _aware(self.updated_at, "review task updated_at")


@dataclass(frozen=True, slots=True)
class PlaceReviewDecision:
    review_decision_id: str
    review_task_id: str
    place_revision_id: str
    actor_id: str
    actor_role: str
    decision_kind: str
    reason_code: str
    reason_text: str | None
    created_at: datetime

    def __post_init__(self) -> None:
        _required(
            self.review_decision_id,
            self.review_task_id,
            self.place_revision_id,
            self.actor_id,
            self.actor_role,
            self.reason_code,
        )
        if self.decision_kind not in REVIEW_DECISION_KINDS:
            raise ValueError("review decision kind is invalid")
        if self.reason_text is not None and len(self.reason_text) > 500:
            raise ValueError("review decision reason_text is too long")
        _aware(self.created_at, "review decision created_at")
