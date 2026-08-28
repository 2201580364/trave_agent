"""A6-3 generation execution transaction tests."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from travel_agent.application.common.errors import InvalidStateTransitionError
from travel_agent.application.planning import ExecuteGenerationHandler
from travel_agent.application.planning.ports import (
    SolverExecutionError,
    SolverOutcome,
)
from travel_agent.domain.planning import (
    CompletionKind,
    GenerationIntent,
    GenerationStatus,
    TripDraft,
)
from travel_agent.infrastructure.memory import (
    InMemoryPlanningStore,
    InMemoryUnitOfWork,
    SequenceIdGenerator,
)

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


class FixedClock:
    def now(self) -> datetime:
        return NOW


class FakeGateway:
    def __init__(self, outcome: SolverOutcome | Exception) -> None:
        self.outcome = outcome
        self.calls = 0

    def solve(self, request: object) -> SolverOutcome:
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def _store() -> InMemoryPlanningStore:
    draft = TripDraft.create(
        draft_id="draft_1", principal_id="principal_1", city_id="hangzhou", now=NOW
    )
    intent = GenerationIntent(
        "intent_1", "principal_1", "draft_1", 1, GenerationStatus.QUEUED,
        "generation-input-v1", {"city_id": "hangzhou"}, "a" * 64,
        "hangzhou-2026-08-24-v1", 7, NOW, NOW,
    )
    return InMemoryPlanningStore(
        drafts={draft.draft_id: draft},
        generation_intents={intent.generation_intent_id: intent},
    )


def _outcome(*, gate: bool = True, partial: bool = False) -> SolverOutcome:
    return SolverOutcome(
        CompletionKind.PARTIAL_SUCCESS if partial else CompletionKind.COMPLETE_SUCCESS,
        partial,
        gate,
        "trip-result-v1",
        {"schema_version": "trip-result-v1", "days": [], "node_ids": ["node_1"]},
        "b" * 64,
        "solver-p1-v1",
        "constraints-p1-v1",
        "parameters-p1-2026-08-24",
        {"quality_gate_passed": gate},
    )


def _handler(store: InMemoryPlanningStore, gateway: FakeGateway) -> ExecuteGenerationHandler:
    return ExecuteGenerationHandler(
        InMemoryUnitOfWork(store), FixedClock(), SequenceIdGenerator(), gateway
    )


def test_success_atomically_creates_run_trip_and_immutable_revision() -> None:
    store = _store()
    result = _handler(store, FakeGateway(_outcome(partial=True))).handle("intent_1")

    assert result.status is GenerationStatus.COMPLETED
    assert len(store.solver_runs) == len(store.trips) == len(store.trip_revisions) == 1
    trip = store.trips[result.trip_id]
    revision = store.trip_revisions[result.trip_revision_id]
    assert trip.current_revision_id == revision.trip_revision_id
    assert revision.completion_kind is CompletionKind.PARTIAL_SUCCESS
    assert revision.has_soft_degradation is True
    assert revision.result_snapshot["node_ids"] == ["node_1"]


def test_completed_intent_is_idempotent_and_does_not_call_gateway_again() -> None:
    store = _store()
    gateway = FakeGateway(_outcome())
    handler = _handler(store, gateway)
    first = handler.handle("intent_1")
    second = handler.handle("intent_1")

    assert gateway.calls == 1
    assert second.reused is True
    assert second.trip_revision_id == first.trip_revision_id
    assert len(store.trip_revisions) == 1


def test_revision_intent_appends_to_existing_trip_without_mutating_history() -> None:
    store = _store()
    gateway = FakeGateway(_outcome())
    ids = SequenceIdGenerator()
    handler = ExecuteGenerationHandler(
        InMemoryUnitOfWork(store), FixedClock(), ids, gateway
    )
    first = handler.handle("intent_1")
    old_revision = store.trip_revisions[first.trip_revision_id]
    source = store.drafts["draft_1"]
    replacement_draft = TripDraft(
        "draft_2",
        source.principal_id,
        source.city_id,
        1,
        "editing",
        source.travel_facts,
        ("attr_2",),
        (),
        NOW,
        NOW,
    )
    store.drafts[replacement_draft.draft_id] = replacement_draft
    store.generation_intents["intent_2"] = GenerationIntent(
        "intent_2",
        "principal_1",
        "draft_2",
        1,
        GenerationStatus.QUEUED,
        "generation-input-v1",
        {"city_id": "hangzhou"},
        "c" * 64,
        "hangzhou-2026-08-24-v1",
        9,
        NOW,
        NOW,
        target_trip_id=first.trip_id,
        base_revision_id=first.trip_revision_id,
    )

    second = handler.handle("intent_2")

    assert second.trip_id == first.trip_id
    assert second.trip_revision_id != first.trip_revision_id
    assert len(store.trips) == 1
    assert len(store.trip_revisions) == 2
    assert store.trip_revisions[first.trip_revision_id] == old_revision
    assert store.trip_revisions[second.trip_revision_id].revision_number == 2
    assert store.trips[first.trip_id].current_revision_id == second.trip_revision_id


def test_running_intent_cannot_be_claimed_by_a_second_worker() -> None:
    store = _store()
    store.generation_intents["intent_1"] = store.generation_intents[
        "intent_1"
    ].claim_running(now=NOW)

    with pytest.raises(InvalidStateTransitionError):
        _handler(store, FakeGateway(_outcome())).handle("intent_1")


def test_quality_gate_failure_records_run_without_publishable_revision() -> None:
    store = _store()
    result = _handler(store, FakeGateway(_outcome(gate=False))).handle("intent_1")

    assert result.status is GenerationStatus.FAILED_TERMINAL
    assert len(store.solver_runs) == 1
    assert store.trips == {}
    assert store.trip_revisions == {}
    assert store.generation_intents["intent_1"].failure_code == "quality_gate_failed"


@pytest.mark.parametrize(
    ("retryable", "expected"),
    [
        (True, GenerationStatus.FAILED_RETRYABLE),
        (False, GenerationStatus.FAILED_TERMINAL),
    ],
)
def test_solver_failure_is_classified_without_creating_half_products(
    retryable: bool, expected: GenerationStatus
) -> None:
    store = _store()
    error = SolverExecutionError("solver_unavailable", retryable=retryable)
    result = _handler(store, FakeGateway(error)).handle("intent_1")

    assert result.status is expected
    assert store.solver_runs == {}
    assert store.trips == {}
    assert store.trip_revisions == {}
