"""Commands for M1 itinerary-quality feedback."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SubmitTripFeedback:
    principal_id: str
    feedback_intent_id: str
    trip_id: str
    revision_id: str
    rating: str
    problem_types: tuple[str, ...] = ()
    comment: str | None = None


@dataclass(frozen=True, slots=True)
class SubmitNodeFeedback:
    principal_id: str
    feedback_intent_id: str
    trip_id: str
    revision_id: str
    node_id: str
    rating: str
    reason_code: str | None = None
    comment: str | None = None
