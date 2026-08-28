"""Application handlers for revision-scoped structured feedback."""

from __future__ import annotations

from dataclasses import dataclass

from travel_agent.application.common.clock import Clock
from travel_agent.application.common.errors import (
    FeedbackIntentConflictError,
    ResourceNotFoundError,
)
from travel_agent.application.common.unit_of_work import UnitOfWork
from travel_agent.application.planning.ports import IdGenerator
from travel_agent.domain.feedback import Feedback, validate_feedback_payload

from .commands import SubmitNodeFeedback, SubmitTripFeedback


@dataclass(frozen=True, slots=True)
class FeedbackResult:
    feedback: Feedback
    reused: bool
    deduplicated: bool


class SubmitTripFeedbackHandler:
    def __init__(self, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    def handle(self, command: SubmitTripFeedback) -> FeedbackResult:
        reasons = tuple(sorted(set(command.problem_types)))
        comment = _normalize_comment(command.comment)
        return _submit_feedback(
            self._uow,
            self._clock,
            self._ids,
            principal_id=command.principal_id,
            feedback_intent_id=command.feedback_intent_id,
            trip_id=command.trip_id,
            revision_id=command.revision_id,
            feedback_scope="trip",
            node_id=None,
            rating=command.rating,
            reason_codes=reasons,
            comment=comment,
        )


class SubmitNodeFeedbackHandler:
    def __init__(self, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    def handle(self, command: SubmitNodeFeedback) -> FeedbackResult:
        reasons = (command.reason_code,) if command.reason_code else ()
        comment = _normalize_comment(command.comment)
        return _submit_feedback(
            self._uow,
            self._clock,
            self._ids,
            principal_id=command.principal_id,
            feedback_intent_id=command.feedback_intent_id,
            trip_id=command.trip_id,
            revision_id=command.revision_id,
            feedback_scope="node",
            node_id=command.node_id,
            rating=command.rating,
            reason_codes=reasons,
            comment=comment,
        )


def _submit_feedback(
    uow: UnitOfWork,
    clock: Clock,
    ids: IdGenerator,
    *,
    principal_id: str,
    feedback_intent_id: str,
    trip_id: str,
    revision_id: str,
    feedback_scope: str,
    node_id: str | None,
    rating: str,
    reason_codes: tuple[str, ...],
    comment: str | None,
) -> FeedbackResult:
    validate_feedback_payload(
        feedback_scope=feedback_scope,
        node_id=node_id,
        rating=rating,
        reason_codes=reason_codes,
        comment=comment,
    )
    with uow:
        existing = uow.feedbacks.get_by_intent(feedback_intent_id)
        if existing is not None:
            if existing.principal_id != principal_id:
                raise ResourceNotFoundError
            if not existing.matches_payload(
                principal_id=principal_id,
                trip_id=trip_id,
                revision_id=revision_id,
                feedback_scope=feedback_scope,
                node_id=node_id,
                rating=rating,
                reason_codes=reason_codes,
                comment=comment,
            ):
                raise FeedbackIntentConflictError
            return FeedbackResult(existing, reused=True, deduplicated=False)

        trip = uow.trips.get(trip_id)
        revision = uow.trip_revisions.get(revision_id)
        if (
            trip is None
            or trip.principal_id != principal_id
            or revision is None
            or revision.trip_id != trip.trip_id
            or (node_id is not None and not _revision_contains_node(revision, node_id))
        ):
            raise ResourceNotFoundError

        target_key = "trip" if node_id is None else f"node:{node_id}"
        target_feedback = uow.feedbacks.get_by_target(
            principal_id,
            revision_id,
            target_key,
        )
        if target_feedback is not None:
            return FeedbackResult(
                target_feedback,
                reused=True,
                deduplicated=True,
            )

        now = clock.now()
        feedback = Feedback(
            feedback_id=ids.new_id("feedback"),
            feedback_intent_id=feedback_intent_id,
            principal_id=principal_id,
            trip_id=trip_id,
            revision_id=revision_id,
            feedback_scope=feedback_scope,
            node_id=node_id,
            rating=rating,
            reason_codes=reason_codes,
            comment=comment,
            created_at=now,
            updated_at=now,
        )
        uow.feedbacks.add(feedback)
        uow.commit()
    return FeedbackResult(feedback, reused=False, deduplicated=False)


def _revision_contains_node(revision, node_id: str) -> bool:
    raw_days = revision.result_snapshot.get("days")
    if not isinstance(raw_days, list):
        return False
    return any(
        isinstance(node, dict) and node.get("node_id") == node_id
        for day in raw_days
        if isinstance(day, dict)
        for node in (day.get("nodes") if isinstance(day.get("nodes"), list) else [])
    )


def _normalize_comment(comment: str | None) -> str | None:
    if comment is None:
        return None
    normalized = comment.strip()
    return normalized or None
