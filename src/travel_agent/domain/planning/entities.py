"""Planning aggregates for draft editing and generation idempotency."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from .values import CompletionKind, GenerationStatus, TravelFacts, VisitPeriodPreferenceInput


@dataclass(frozen=True, slots=True)
class TripDraft:
    draft_id: str
    principal_id: str
    city_id: str
    draft_version: int
    status: str
    travel_facts: TravelFacts | None
    selected_attraction_ids: tuple[str, ...]
    visit_period_preferences: tuple[VisitPeriodPreferenceInput, ...]
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.draft_id or not self.principal_id or not self.city_id:
            raise ValueError("draft identity fields are required")
        if self.draft_version <= 0:
            raise ValueError("draft_version must be positive")
        if self.status not in {"editing", "needs_review", "submitted", "abandoned"}:
            raise ValueError("draft status is invalid")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("draft timestamps must be timezone-aware")
        if len(set(self.selected_attraction_ids)) != len(self.selected_attraction_ids):
            raise ValueError("selected attractions must be unique")
        selected = set(self.selected_attraction_ids)
        if any(item.attraction_id not in selected for item in self.visit_period_preferences):
            raise ValueError("visit period preference must target a selected attraction")

    @classmethod
    def create(
        cls,
        *,
        draft_id: str,
        principal_id: str,
        city_id: str,
        now: datetime,
    ) -> TripDraft:
        return cls(
            draft_id=draft_id,
            principal_id=principal_id,
            city_id=city_id,
            draft_version=1,
            status="editing",
            travel_facts=None,
            selected_attraction_ids=(),
            visit_period_preferences=(),
            created_at=now,
            updated_at=now,
        )

    def update_travel_facts(self, facts: TravelFacts, *, now: datetime) -> TripDraft:
        self._ensure_editable()
        return replace(
            self,
            travel_facts=facts,
            draft_version=self.draft_version + 1,
            updated_at=now,
        )

    def clone_with_replacement(
        self,
        *,
        draft_id: str,
        old_attraction_id: str,
        new_attraction_id: str,
        now: datetime,
    ) -> TripDraft:
        if old_attraction_id not in self.selected_attraction_ids:
            raise ValueError("replaced attraction is not part of the source draft")
        if new_attraction_id in self.selected_attraction_ids:
            raise ValueError("replacement attraction is already selected")
        selected = tuple(
            new_attraction_id if item == old_attraction_id else item
            for item in self.selected_attraction_ids
        )
        preferences = tuple(
            item
            for item in self.visit_period_preferences
            if item.attraction_id != old_attraction_id
        )
        return TripDraft(
            draft_id=draft_id,
            principal_id=self.principal_id,
            city_id=self.city_id,
            draft_version=1,
            status="editing",
            travel_facts=self.travel_facts,
            selected_attraction_ids=tuple(sorted(selected)),
            visit_period_preferences=tuple(
                sorted(preferences, key=lambda item: item.attraction_id)
            ),
            created_at=now,
            updated_at=now,
        )

    def replace_selection(
        self,
        attraction_ids: tuple[str, ...],
        preferences: tuple[VisitPeriodPreferenceInput, ...],
        *,
        now: datetime,
    ) -> TripDraft:
        self._ensure_editable()
        normalized_ids = tuple(sorted(set(attraction_ids)))
        normalized_preferences = tuple(
            sorted(preferences, key=lambda item: item.attraction_id)
        )
        return replace(
            self,
            selected_attraction_ids=normalized_ids,
            visit_period_preferences=normalized_preferences,
            draft_version=self.draft_version + 1,
            updated_at=now,
        )

    @property
    def ready_for_generation(self) -> bool:
        return (
            self.status == "editing"
            and self.travel_facts is not None
            and self.travel_facts.ready_for_generation
            and bool(self.selected_attraction_ids)
        )

    def _ensure_editable(self) -> None:
        if self.status not in {"editing", "needs_review"}:
            raise ValueError("draft is not editable")


@dataclass(frozen=True, slots=True)
class GenerationIntent:
    generation_intent_id: str
    principal_id: str
    draft_id: str
    draft_version: int
    status: GenerationStatus
    input_schema_version: str
    input_snapshot: dict[str, object]
    input_snapshot_hash: str
    data_snapshot_version: str
    random_seed: int
    submitted_at: datetime
    updated_at: datetime
    trip_id: str | None = None
    trip_revision_id: str | None = None
    failure_code: str | None = None
    target_trip_id: str | None = None
    base_revision_id: str | None = None

    def __post_init__(self) -> None:
        required = (
            self.generation_intent_id,
            self.principal_id,
            self.draft_id,
            self.input_schema_version,
            self.input_snapshot_hash,
            self.data_snapshot_version,
        )
        if any(not item for item in required):
            raise ValueError("generation intent identity and version fields are required")
        if self.draft_version <= 0:
            raise ValueError("draft_version must be positive")
        if self.random_seed < 0:
            raise ValueError("random_seed must be non-negative")
        if self.submitted_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("intent timestamps must be timezone-aware")
        if (self.target_trip_id is None) != (self.base_revision_id is None):
            raise ValueError("target trip and base revision must be provided together")

    def claim_running(self, *, now: datetime) -> GenerationIntent:
        if self.status not in {GenerationStatus.QUEUED, GenerationStatus.FAILED_RETRYABLE}:
            raise ValueError("generation intent cannot be claimed")
        return replace(self, status=GenerationStatus.RUNNING, updated_at=now, failure_code=None)

    def complete(
        self, *, trip_id: str, trip_revision_id: str, now: datetime
    ) -> GenerationIntent:
        if self.status is not GenerationStatus.RUNNING:
            raise ValueError("only a running generation intent can complete")
        return replace(
            self,
            status=GenerationStatus.COMPLETED,
            trip_id=trip_id,
            trip_revision_id=trip_revision_id,
            updated_at=now,
            failure_code=None,
        )

    def fail(self, *, code: str, retryable: bool, now: datetime) -> GenerationIntent:
        if self.status is not GenerationStatus.RUNNING:
            raise ValueError("only a running generation intent can fail")
        return replace(
            self,
            status=(
                GenerationStatus.FAILED_RETRYABLE
                if retryable
                else GenerationStatus.FAILED_TERMINAL
            ),
            failure_code=code,
            updated_at=now,
        )


@dataclass(frozen=True, slots=True)
class Trip:
    trip_id: str
    principal_id: str
    city_id: str
    source_draft_id: str
    current_revision_id: str
    created_at: datetime
    updated_at: datetime

    def advance_revision(
        self,
        *,
        expected_revision_id: str,
        new_revision_id: str,
        now: datetime,
    ) -> Trip:
        if self.current_revision_id != expected_revision_id:
            raise ValueError("trip current revision has changed")
        return replace(
            self,
            current_revision_id=new_revision_id,
            updated_at=now,
        )


@dataclass(frozen=True, slots=True)
class TripRevision:
    trip_revision_id: str
    trip_id: str
    revision_number: int
    generation_intent_id: str
    completion_kind: CompletionKind
    has_soft_degradation: bool
    result_schema_version: str
    result_snapshot: dict[str, object]
    result_snapshot_hash: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SolverRun:
    solver_run_id: str
    generation_intent_id: str
    status: str
    quality_gate_passed: bool
    solver_version: str
    constraint_version: str
    parameter_version: str
    audit_payload: dict[str, object]
    created_at: datetime
