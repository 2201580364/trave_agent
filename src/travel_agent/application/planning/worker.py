"""Bounded durable worker for persisted generation intents.

Traceability: H3, C6, M1-OD-LATENCY-001.  Intent claiming remains in the
existing application handler, so multiple worker processes are safe.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from travel_agent.application.common.clock import Clock
from travel_agent.application.common.unit_of_work import UnitOfWork


class GenerationHandler(Protocol):
    def handle(self, generation_intent_id: str) -> object: ...


@dataclass(frozen=True, slots=True)
class GenerationWorkerResult:
    recovered_count: int
    processed_intent_ids: tuple[str, ...]
    failed_intent_id: str | None = None
    error_type: str | None = None


class GenerationWorker:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        clock: Clock,
        handler: GenerationHandler,
        *,
        stale_after_seconds: int = 900,
    ) -> None:
        if stale_after_seconds < 60:
            raise ValueError("stale_after_seconds must be at least 60")
        self._uow_factory = uow_factory
        self._clock = clock
        self._handler = handler
        self._stale_after_seconds = stale_after_seconds

    def run_batch(self, *, max_jobs: int = 1) -> GenerationWorkerResult:
        if max_jobs < 1 or max_jobs > 100:
            raise ValueError("generation worker batch size must be between 1 and 100")
        cutoff = self._clock.now() - timedelta(seconds=self._stale_after_seconds)
        with self._uow_factory() as uow:
            recovered = uow.generation_intents.recover_stale_running(before=cutoff)
            if recovered:
                uow.commit()
            queued = uow.generation_intents.list_queued(limit=max_jobs)

        processed: list[str] = []
        for intent in queued:
            try:
                self._handler.handle(intent.generation_intent_id)
            except Exception as exc:
                return GenerationWorkerResult(
                    recovered,
                    tuple(processed),
                    intent.generation_intent_id,
                    type(exc).__name__,
                )
            processed.append(intent.generation_intent_id)
        return GenerationWorkerResult(recovered, tuple(processed))
