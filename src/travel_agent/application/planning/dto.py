"""Application results returned to interface adapters."""

from __future__ import annotations

from dataclasses import dataclass

from travel_agent.domain.planning import GenerationStatus, TripDraft


@dataclass(frozen=True, slots=True)
class DraftResult:
    draft: TripDraft


@dataclass(frozen=True, slots=True)
class GenerationIntentResult:
    generation_intent_id: str
    status: GenerationStatus
    draft_id: str
    draft_version: int
    data_snapshot_version: str
    reused: bool


@dataclass(frozen=True, slots=True)
class GenerationExecutionResult:
    generation_intent_id: str
    status: GenerationStatus
    solver_run_id: str | None
    trip_id: str | None
    trip_revision_id: str | None
    reused: bool
