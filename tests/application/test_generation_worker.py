"""Durable worker behavior for M1-OD-LATENCY-001."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from travel_agent.application.planning.worker import GenerationWorker
from travel_agent.domain.planning import GenerationIntent, GenerationStatus
from travel_agent.infrastructure.memory import InMemoryPlanningStore, InMemoryUnitOfWork

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


class RecordingHandler:
    def __init__(self) -> None:
        self.intent_ids: list[str] = []

    def handle(self, generation_intent_id: str) -> None:
        self.intent_ids.append(generation_intent_id)


class FixedClock:
    def now(self) -> datetime:
        return NOW


def _intent(
    intent_id: str, status: GenerationStatus, updated_at: datetime = NOW
) -> GenerationIntent:
    return GenerationIntent(
        intent_id,
        "principal_1",
        "draft_1",
        1,
        status,
        "generation-input-v1",
        {"city_id": "hangzhou"},
        "a" * 64,
        "hangzhou-v1",
        7,
        NOW,
        updated_at,
    )


def test_worker_claims_queued_intents_in_submission_order() -> None:
    store = InMemoryPlanningStore(
        generation_intents={
            "intent_2": _intent(
                "intent_2", GenerationStatus.QUEUED, NOW + timedelta(seconds=1)
            ),
            "intent_1": _intent("intent_1", GenerationStatus.QUEUED),
        }
    )
    handler = RecordingHandler()
    worker = GenerationWorker(lambda: InMemoryUnitOfWork(store), FixedClock(), handler)

    result = worker.run_batch(max_jobs=2)

    assert result.processed_intent_ids == ("intent_1", "intent_2")
    assert handler.intent_ids == ["intent_1", "intent_2"]


def test_worker_recovers_stale_running_intent_before_processing() -> None:
    stale = NOW - timedelta(seconds=901)
    store = InMemoryPlanningStore(
        generation_intents={
            "intent_1": _intent("intent_1", GenerationStatus.RUNNING, stale)
        }
    )
    handler = RecordingHandler()
    worker = GenerationWorker(lambda: InMemoryUnitOfWork(store), FixedClock(), handler)

    result = worker.run_batch()

    assert result.recovered_count == 1
    assert result.processed_intent_ids == ("intent_1",)
    assert handler.intent_ids == ["intent_1"]
