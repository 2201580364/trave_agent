"""A6-9.4 structured feedback application tests."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from travel_agent.application.common.errors import (
    FeedbackIntentConflictError,
    ResourceNotFoundError,
)
from travel_agent.application.feedback import (
    SubmitNodeFeedback,
    SubmitNodeFeedbackHandler,
    SubmitTripFeedback,
    SubmitTripFeedbackHandler,
)
from travel_agent.domain.planning import CompletionKind, Trip, TripRevision
from travel_agent.infrastructure.memory import (
    InMemoryPlanningStore,
    InMemoryUnitOfWork,
    SequenceIdGenerator,
)

NOW = datetime(2026, 8, 28, 16, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


class FixedClock:
    def now(self) -> datetime:
        return NOW


def _store() -> InMemoryPlanningStore:
    trip = Trip(
        "trip_1",
        "principal_owner",
        "hangzhou",
        "draft_1",
        "revision_1",
        NOW,
        NOW,
    )
    revision = TripRevision(
        "revision_1",
        trip.trip_id,
        1,
        "intent_1",
        CompletionKind.COMPLETE_SUCCESS,
        False,
        "trip-result-v2",
        {
            "days": [
                {
                    "date": "2026-09-11",
                    "nodes": [
                        {
                            "node_id": "node_west_lake",
                            "attraction_id": "attr_west_lake",
                            "name": "西湖湖滨",
                        }
                    ],
                }
            ]
        },
        "a" * 64,
        NOW,
    )
    return InMemoryPlanningStore(
        trips={trip.trip_id: trip},
        trip_revisions={revision.trip_revision_id: revision},
    )


def test_trip_feedback_is_structured_idempotent_and_target_deduplicated() -> None:
    store = _store()
    handler = SubmitTripFeedbackHandler(
        InMemoryUnitOfWork(store),
        FixedClock(),
        SequenceIdGenerator(),
    )
    command = SubmitTripFeedback(
        "principal_owner",
        "feedback_intent_1",
        "trip_1",
        "revision_1",
        "unreasonable",
        ("pace_mismatch", "route_too_long", "pace_mismatch"),
        "  第二天路线有点绕。  ",
    )

    created = handler.handle(command)
    repeated = handler.handle(command)
    deduplicated = handler.handle(
        SubmitTripFeedback(
            "principal_owner",
            "feedback_intent_2",
            "trip_1",
            "revision_1",
            "neutral",
        )
    )

    assert created.reused is False
    assert created.deduplicated is False
    assert created.feedback.reason_codes == ("pace_mismatch", "route_too_long")
    assert created.feedback.comment == "第二天路线有点绕。"
    assert repeated.feedback.feedback_id == created.feedback.feedback_id
    assert repeated.reused is True
    assert repeated.deduplicated is False
    assert deduplicated.feedback.feedback_id == created.feedback.feedback_id
    assert deduplicated.reused is True
    assert deduplicated.deduplicated is True
    assert len(store.feedbacks) == 1


def test_feedback_intent_cannot_be_reused_for_different_payload() -> None:
    store = _store()
    handler = SubmitTripFeedbackHandler(
        InMemoryUnitOfWork(store),
        FixedClock(),
        SequenceIdGenerator(),
    )
    handler.handle(
        SubmitTripFeedback(
            "principal_owner",
            "feedback_intent_1",
            "trip_1",
            "revision_1",
            "reasonable",
        )
    )

    with pytest.raises(FeedbackIntentConflictError):
        handler.handle(
            SubmitTripFeedback(
                "principal_owner",
                "feedback_intent_1",
                "trip_1",
                "revision_1",
                "unreasonable",
                ("route_too_long",),
            )
        )


def test_existing_target_does_not_hide_an_invalid_application_payload() -> None:
    store = _store()
    handler = SubmitTripFeedbackHandler(
        InMemoryUnitOfWork(store),
        FixedClock(),
        SequenceIdGenerator(),
    )
    handler.handle(
        SubmitTripFeedback(
            "principal_owner",
            "feedback_intent_1",
            "trip_1",
            "revision_1",
            "reasonable",
        )
    )

    with pytest.raises(ValueError, match="rating is invalid"):
        handler.handle(
            SubmitTripFeedback(
                "principal_owner",
                "feedback_intent_2",
                "trip_1",
                "revision_1",
                "not-a-rating",
            )
        )


def test_node_feedback_requires_a_node_from_the_exact_revision() -> None:
    store = _store()
    handler = SubmitNodeFeedbackHandler(
        InMemoryUnitOfWork(store),
        FixedClock(),
        SequenceIdGenerator(),
    )

    created = handler.handle(
        SubmitNodeFeedback(
            "principal_owner",
            "feedback_node_1",
            "trip_1",
            "revision_1",
            "node_west_lake",
            "dislike",
            "time_too_tight",
            "希望多留一点时间。",
        )
    )

    assert created.feedback.feedback_scope == "node"
    assert created.feedback.node_id == "node_west_lake"
    assert created.feedback.reason_codes == ("time_too_tight",)

    with pytest.raises(ResourceNotFoundError):
        handler.handle(
            SubmitNodeFeedback(
                "principal_owner",
                "feedback_node_missing",
                "trip_1",
                "revision_1",
                "node_not_in_revision",
                "like",
            )
        )


def test_feedback_hides_other_principals_trip_as_not_found() -> None:
    store = _store()
    handler = SubmitTripFeedbackHandler(
        InMemoryUnitOfWork(store),
        FixedClock(),
        SequenceIdGenerator(),
    )

    with pytest.raises(ResourceNotFoundError):
        handler.handle(
            SubmitTripFeedback(
                "principal_other",
                "feedback_other",
                "trip_1",
                "revision_1",
                "reasonable",
            )
        )
