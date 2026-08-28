"""A6-9.3 immutable plan-share application tests."""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from travel_agent.application.common.errors import PlanShareIntentConflictError
from travel_agent.application.sharing import (
    CopyPlanShareToDraft,
    CopyPlanShareToDraftHandler,
    CreatePlanShare,
    CreatePlanShareHandler,
    GetPublishedPlanShareHandler,
)
from travel_agent.domain.planning import (
    CompletionKind,
    GenerationIntent,
    GenerationStatus,
    Trip,
    TripDraft,
    TripRevision,
)
from travel_agent.infrastructure.memory import (
    InMemoryPlanningStore,
    InMemoryUnitOfWork,
    SequenceIdGenerator,
)
from travel_agent.infrastructure.sharing import HmacPlanShareTokenCodec

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


class FixedClock:
    def now(self) -> datetime:
        return NOW


def _store() -> InMemoryPlanningStore:
    draft = TripDraft.create(
        draft_id="draft_source",
        principal_id="principal_owner",
        city_id="hangzhou",
        now=NOW,
    ).replace_selection(("attr_west_lake", "attr_fountain_show"), (), now=NOW)
    intent = GenerationIntent(
        "intent_source",
        "principal_owner",
        draft.draft_id,
        draft.draft_version,
        GenerationStatus.COMPLETED,
        "generation-input-v1",
        {"selected_attraction_ids": list(draft.selected_attraction_ids)},
        "a" * 64,
        "hangzhou-v1",
        7,
        NOW,
        NOW,
        "trip_1",
        "revision_1",
    )
    trip = Trip(
        "trip_1",
        "principal_owner",
        "hangzhou",
        draft.draft_id,
        "revision_1",
        NOW,
        NOW,
    )
    revision = TripRevision(
        "revision_1",
        trip.trip_id,
        1,
        intent.generation_intent_id,
        CompletionKind.COMPLETE_SUCCESS,
        False,
        "trip-result-v2",
        {
            "days": [
                {
                    "date": "2026-09-11",
                    "weather": {"condition": "晴", "basis": "forecast"},
                    "nodes": [
                        {
                            "node_id": "private_node_1",
                            "attraction_id": "attr_west_lake",
                            "name": "西湖湖滨",
                            "arrival_min": 570,
                            "leave_min": 720,
                            "planned_duration_min": 150,
                            "transport_mode": "transit",
                            "travel_distance_m": 7200,
                        },
                        {
                            "node_id": "private_node_2",
                            "attraction_id": "attr_fountain_show",
                            "name": "湖滨喷泉灯光秀",
                            "arrival_min": 1110,
                            "leave_min": 1140,
                            "planned_duration_min": 30,
                            "timing_kind": "fixed_event",
                        },
                    ],
                }
            ],
            "unplaced": [],
            "provenance": {"data_snapshot_version": "private-data-version"},
        },
        "b" * 64,
        NOW,
    )
    return InMemoryPlanningStore(
        drafts={draft.draft_id: draft},
        generation_intents={intent.generation_intent_id: intent},
        trips={trip.trip_id: trip},
        trip_revisions={revision.trip_revision_id: revision},
    )


def _tokens() -> HmacPlanShareTokenCodec:
    return HmacPlanShareTokenCodec(
        "test-plan-share-secret-2026-08-28-at-least-32-bytes"
    )


def test_plan_share_is_redacted_immutable_and_idempotent() -> None:
    store = _store()
    ids = SequenceIdGenerator()
    handler = CreatePlanShareHandler(
        InMemoryUnitOfWork(store), FixedClock(), ids, _tokens()
    )
    command = CreatePlanShare(
        "principal_owner", "share_intent_1", "trip_1", "revision_1"
    )

    created = handler.handle(command)
    repeated = handler.handle(command)
    published = GetPublishedPlanShareHandler(
        InMemoryUnitOfWork(store), _tokens()
    ).handle(created.public_token)

    assert created.reused is False
    assert repeated.reused is True
    assert repeated.public_token == created.public_token
    assert published.share_snapshot == created.share.share_snapshot
    assert published.share_snapshot["content_kind"] == "planned_itinerary"
    assert published.share_snapshot["days"][0]["items"][1]["fixed_time"] == (
        "18:30"
    )
    serialized = json.dumps(published.share_snapshot, ensure_ascii=False)
    for forbidden in (
        "principal_id",
        "node_id",
        "attraction_id",
        "transport_mode",
        "travel_distance_m",
        "private-data-version",
        "access_token",
    ):
        assert forbidden not in serialized


def test_plan_share_intent_cannot_be_reused_for_another_revision() -> None:
    store = _store()
    handler = CreatePlanShareHandler(
        InMemoryUnitOfWork(store), FixedClock(), SequenceIdGenerator(), _tokens()
    )
    handler.handle(
        CreatePlanShare(
            "principal_owner", "share_intent_1", "trip_1", "revision_1"
        )
    )

    with pytest.raises(PlanShareIntentConflictError):
        handler.handle(
            CreatePlanShare(
                "principal_owner", "share_intent_1", "trip_1", "revision_other"
            )
        )


def test_reference_copy_keeps_attractions_but_drops_private_travel_facts() -> None:
    store = _store()
    ids = SequenceIdGenerator()
    created = CreatePlanShareHandler(
        InMemoryUnitOfWork(store), FixedClock(), ids, _tokens()
    ).handle(
        CreatePlanShare(
            "principal_owner", "share_intent_1", "trip_1", "revision_1"
        )
    )
    store.drafts["draft_source"] = store.drafts["draft_source"].replace_selection(
        ("attr_changed_after_revision",),
        (),
        now=NOW,
    )

    copied = CopyPlanShareToDraftHandler(
        InMemoryUnitOfWork(store), FixedClock(), ids, _tokens()
    ).handle(CopyPlanShareToDraft("principal_visitor", created.public_token))

    assert copied.draft.principal_id == "principal_visitor"
    assert copied.draft.city_id == "hangzhou"
    assert copied.draft.selected_attraction_ids == (
        "attr_fountain_show",
        "attr_west_lake",
    )
    assert copied.draft.travel_facts is None
    assert copied.draft.visit_period_preferences == ()
