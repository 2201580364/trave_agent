"""A6 planning use-case tests.

Traceability: IF-02, IF-03, IF-04, IF-05, A5-API-01..03.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from travel_agent.application.common.errors import (
    DraftNotReadyError,
    DraftVersionConflictError,
    GenerationIntentConflictError,
    ResourceNotFoundError,
)
from travel_agent.application.planning import (
    CreateDraft,
    CreateDraftHandler,
    ReplaceAttractionSelection,
    ReplaceAttractionSelectionHandler,
    SubmitGeneration,
    SubmitGenerationHandler,
    UpdateTravelFacts,
    UpdateTravelFactsHandler,
)
from travel_agent.domain.planning import (
    ConfirmationStatus,
    CrowdType,
    TransportType,
    TravelFacts,
    TravelMode,
    VisitPeriodPreferenceInput,
)
from travel_agent.infrastructure.memory import (
    FixedDataSnapshotVersionProvider,
    InMemoryGenerationExecutor,
    InMemoryPlanningStore,
    InMemoryUnitOfWork,
    SequenceIdGenerator,
)


class FixedClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


def _clock() -> FixedClock:
    return FixedClock(datetime(2026, 8, 24, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")))


def _facts() -> TravelFacts:
    timezone = ZoneInfo("Asia/Shanghai")
    return TravelFacts(
        start_date=datetime(2026, 9, 1, tzinfo=timezone).date(),
        end_date=datetime(2026, 9, 3, tzinfo=timezone).date(),
        arrival_transport_type=TransportType.HIGH_SPEED_RAIL,
        arrival_confirmation=ConfirmationStatus.CONFIRMED,
        arrival_at=datetime(2026, 9, 1, 14, 0, tzinfo=timezone),
        station_to_city_min=45,
        station_to_city_source="system_default",
        departure_transport_type=TransportType.HIGH_SPEED_RAIL,
        departure_confirmation=ConfirmationStatus.CONFIRMED_BY_INHERITANCE,
        departure_at=datetime(2026, 9, 3, 18, 0, tzinfo=timezone),
        station_early_min=45,
        station_early_source="system_default",
        last_visit_to_station_min=40,
        last_visit_to_station_source="od_snapshot",
        travel_mode=TravelMode.NORMAL,
        crowd_type=CrowdType.UNSPECIFIED,
    )


def _create_draft(
    store: InMemoryPlanningStore,
    clock: FixedClock,
    *,
    principal_id: str = "principal_1",
) -> str:
    result = CreateDraftHandler(
        InMemoryUnitOfWork(store),
        clock,
        SequenceIdGenerator(),
    ).handle(CreateDraft(principal_id, "hangzhou"))
    return result.draft.draft_id


def _ready_draft(
    store: InMemoryPlanningStore,
    clock: FixedClock,
    *,
    principal_id: str = "principal_1",
) -> tuple[str, int]:
    draft_id = _create_draft(store, clock, principal_id=principal_id)
    travel_result = UpdateTravelFactsHandler(
        InMemoryUnitOfWork(store), clock
    ).handle(UpdateTravelFacts(principal_id, draft_id, 1, _facts()))
    selection_result = ReplaceAttractionSelectionHandler(
        InMemoryUnitOfWork(store), clock
    ).handle(
        ReplaceAttractionSelection(
            principal_id,
            draft_id,
            travel_result.draft.draft_version,
            ("attr_2", "attr_1"),
            (
                VisitPeriodPreferenceInput(
                    "attr_2",
                    "evening",
                    ("afternoon",),
                ),
            ),
        )
    )
    return draft_id, selection_result.draft.draft_version


def test_create_and_update_draft_uses_monotonic_versions() -> None:
    store = InMemoryPlanningStore()
    clock = _clock()
    draft_id = _create_draft(store, clock)

    updated = UpdateTravelFactsHandler(InMemoryUnitOfWork(store), clock).handle(
        UpdateTravelFacts("principal_1", draft_id, 1, _facts())
    )

    assert updated.draft.draft_version == 2
    assert store.drafts[draft_id].travel_facts == _facts()


def test_stale_draft_version_does_not_overwrite_current_state() -> None:
    store = InMemoryPlanningStore()
    clock = _clock()
    draft_id = _create_draft(store, clock)
    handler = UpdateTravelFactsHandler(InMemoryUnitOfWork(store), clock)
    handler.handle(UpdateTravelFacts("principal_1", draft_id, 1, _facts()))

    with pytest.raises(DraftVersionConflictError) as raised:
        handler.handle(UpdateTravelFacts("principal_1", draft_id, 1, _facts()))

    assert raised.value.details == {"expected_version": 1, "current_version": 2}
    assert store.drafts[draft_id].draft_version == 2


def test_selection_is_normalized_and_preferences_require_selected_attraction() -> None:
    store = InMemoryPlanningStore()
    clock = _clock()
    draft_id = _create_draft(store, clock)
    handler = ReplaceAttractionSelectionHandler(InMemoryUnitOfWork(store), clock)

    result = handler.handle(
        ReplaceAttractionSelection(
            "principal_1",
            draft_id,
            1,
            ("attr_2", "attr_1", "attr_2"),
            (VisitPeriodPreferenceInput("attr_2", "evening"),),
        )
    )

    assert result.draft.selected_attraction_ids == ("attr_1", "attr_2")

    with pytest.raises(ValueError, match="selected attraction"):
        handler.handle(
            ReplaceAttractionSelection(
                "principal_1",
                draft_id,
                2,
                ("attr_1",),
                (VisitPeriodPreferenceInput("attr_3", "morning"),),
            )
        )
    assert store.drafts[draft_id].draft_version == 2


def test_submit_generation_is_idempotent_and_submits_executor_once() -> None:
    store = InMemoryPlanningStore()
    clock = _clock()
    draft_id, version = _ready_draft(store, clock)
    executor = InMemoryGenerationExecutor()
    handler = SubmitGenerationHandler(
        InMemoryUnitOfWork(store),
        clock,
        FixedDataSnapshotVersionProvider({"hangzhou": "hangzhou-2026-08-24"}),
        executor,
    )
    command = SubmitGeneration("principal_1", "gen_1", draft_id, version)

    first = handler.handle(command)
    second = handler.handle(command)

    assert first.reused is False
    assert second.reused is True
    assert first.data_snapshot_version == "hangzhou-2026-08-24"
    assert executor.submitted == ["gen_1"]
    assert len(store.generation_intents) == 1


def test_existing_intent_cannot_be_reused_for_other_draft_version() -> None:
    store = InMemoryPlanningStore()
    clock = _clock()
    draft_id, version = _ready_draft(store, clock)
    handler = SubmitGenerationHandler(
        InMemoryUnitOfWork(store),
        clock,
        FixedDataSnapshotVersionProvider({"hangzhou": "snapshot_1"}),
        InMemoryGenerationExecutor(),
    )
    handler.handle(SubmitGeneration("principal_1", "gen_1", draft_id, version))

    with pytest.raises(GenerationIntentConflictError):
        handler.handle(SubmitGeneration("principal_1", "gen_1", draft_id, version + 1))


def test_unready_draft_is_not_persisted_as_generation_intent() -> None:
    store = InMemoryPlanningStore()
    clock = _clock()
    draft_id = _create_draft(store, clock)
    executor = InMemoryGenerationExecutor()
    handler = SubmitGenerationHandler(
        InMemoryUnitOfWork(store),
        clock,
        FixedDataSnapshotVersionProvider({"hangzhou": "snapshot_1"}),
        executor,
    )

    with pytest.raises(DraftNotReadyError) as raised:
        handler.handle(SubmitGeneration("principal_1", "gen_1", draft_id, 1))

    assert raised.value.details == {
        "issues": ("travel_facts_missing", "attraction_selection_empty")
    }
    assert store.generation_intents == {}
    assert executor.submitted == []


def test_other_principal_cannot_read_draft_through_write_use_case() -> None:
    store = InMemoryPlanningStore()
    clock = _clock()
    draft_id = _create_draft(store, clock)

    with pytest.raises(ResourceNotFoundError):
        UpdateTravelFactsHandler(InMemoryUnitOfWork(store), clock).handle(
            UpdateTravelFacts("principal_2", draft_id, 1, _facts())
        )
