"""Structured M1 feedback about itinerary revisions and scheduled nodes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

TRIP_FEEDBACK_RATINGS = frozenset({"reasonable", "neutral", "unreasonable"})
NODE_FEEDBACK_RATINGS = frozenset({"like", "dislike"})
TRIP_FEEDBACK_REASONS = frozenset(
    {
        "route_too_long",
        "time_unreasonable",
        "pace_mismatch",
        "missing_attraction",
        "attraction_data_error",
        "explanation_unclear",
    }
)
NODE_FEEDBACK_REASONS = frozenset(
    {
        "arrangement_good",
        "time_too_tight",
        "travel_too_far",
        "time_period_wrong",
        "duration_wrong",
        "attraction_data_error",
    }
)


def validate_feedback_payload(
    *,
    feedback_scope: str,
    node_id: str | None,
    rating: str,
    reason_codes: tuple[str, ...],
    comment: str | None,
) -> None:
    """Validate normalized feedback content independently from persistence identity."""
    if feedback_scope not in {"trip", "node"}:
        raise ValueError("feedback scope is invalid")
    if feedback_scope == "trip" and node_id is not None:
        raise ValueError("trip feedback cannot reference a node")
    if feedback_scope == "node" and not node_id:
        raise ValueError("node feedback requires a node id")
    if len(set(reason_codes)) != len(reason_codes):
        raise ValueError("feedback reason codes must be unique")
    if comment is not None:
        if comment != comment.strip():
            raise ValueError("feedback comment must be normalized")
        if not comment or len(comment) > 500:
            raise ValueError("feedback comment must contain 1 to 500 characters")

    reasons = set(reason_codes)
    if feedback_scope == "trip":
        if rating not in TRIP_FEEDBACK_RATINGS:
            raise ValueError("trip feedback rating is invalid")
        if not reasons <= TRIP_FEEDBACK_REASONS:
            raise ValueError("trip feedback reason code is invalid")
        if rating == "reasonable" and reasons:
            raise ValueError("reasonable trip feedback cannot contain problems")
    else:
        if rating not in NODE_FEEDBACK_RATINGS:
            raise ValueError("node feedback rating is invalid")
        if not reasons <= NODE_FEEDBACK_REASONS:
            raise ValueError("node feedback reason code is invalid")
        if rating == "like" and reasons - {"arrangement_good"}:
            raise ValueError("liked node feedback contains a negative reason")
        if rating == "dislike" and "arrangement_good" in reasons:
            raise ValueError("disliked node feedback contains a positive reason")


@dataclass(frozen=True, slots=True)
class Feedback:
    feedback_id: str
    feedback_intent_id: str
    principal_id: str
    trip_id: str
    revision_id: str
    feedback_scope: str
    node_id: str | None
    rating: str
    reason_codes: tuple[str, ...]
    comment: str | None
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        required = (
            self.feedback_id,
            self.feedback_intent_id,
            self.principal_id,
            self.trip_id,
            self.revision_id,
        )
        if any(not item for item in required):
            raise ValueError("feedback identity fields are required")
        validate_feedback_payload(
            feedback_scope=self.feedback_scope,
            node_id=self.node_id,
            rating=self.rating,
            reason_codes=self.reason_codes,
            comment=self.comment,
        )
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("feedback timestamps must be timezone-aware")

    @property
    def target_key(self) -> str:
        return "trip" if self.node_id is None else f"node:{self.node_id}"

    def matches_payload(
        self,
        *,
        principal_id: str,
        trip_id: str,
        revision_id: str,
        feedback_scope: str,
        node_id: str | None,
        rating: str,
        reason_codes: tuple[str, ...],
        comment: str | None,
    ) -> bool:
        return (
            self.principal_id == principal_id
            and self.trip_id == trip_id
            and self.revision_id == revision_id
            and self.feedback_scope == feedback_scope
            and self.node_id == node_id
            and self.rating == rating
            and self.reason_codes == reason_codes
            and self.comment == comment
        )
