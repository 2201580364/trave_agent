"""Planning command handlers.

Traceability: IF-02, IF-03, IF-04, IF-05, A5-API-01..03.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date, datetime
from enum import Enum

from travel_agent.application.common.clock import Clock
from travel_agent.application.common.errors import (
    DraftNotReadyError,
    DraftVersionConflictError,
    GenerationIntentConflictError,
    InvalidStateTransitionError, ResourceNotFoundError,
)
from travel_agent.application.common.unit_of_work import UnitOfWork
from travel_agent.domain.planning import (
    GenerationIntent, GenerationStatus, SolverRun, Trip, TripDraft, TripRevision,
)

from .commands import (
    CreateDraft,
    ReplaceAttractionSelection,
    SubmitGeneration,
    UpdateTravelFacts,
)
from .dto import DraftResult, GenerationExecutionResult, GenerationIntentResult
from .ports import (
    DataSnapshotVersionProvider, GenerationExecutor, IdGenerator, SolverExecutionError,
    SolverGateway, SolverRequest,
)


class CreateDraftHandler:
    def __init__(self, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    def handle(self, command: CreateDraft) -> DraftResult:
        now = self._clock.now()
        draft = TripDraft.create(
            draft_id=self._ids.new_id("draft"),
            principal_id=command.principal_id,
            city_id=command.city_id,
            now=now,
        )
        with self._uow:
            self._uow.drafts.save(draft)
            self._uow.commit()
        return DraftResult(draft)


class UpdateTravelFactsHandler:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def handle(self, command: UpdateTravelFacts) -> DraftResult:
        with self._uow:
            draft = _owned_draft(self._uow, command.draft_id, command.principal_id)
            _check_version(draft, command.expected_draft_version)
            updated = draft.update_travel_facts(command.travel_facts, now=self._clock.now())
            self._uow.drafts.save(updated, expected_version=draft.draft_version)
            self._uow.commit()
        return DraftResult(updated)


class ReplaceAttractionSelectionHandler:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def handle(self, command: ReplaceAttractionSelection) -> DraftResult:
        with self._uow:
            draft = _owned_draft(self._uow, command.draft_id, command.principal_id)
            _check_version(draft, command.expected_draft_version)
            updated = draft.replace_selection(
                command.attraction_ids,
                command.visit_period_preferences,
                now=self._clock.now(),
            )
            self._uow.drafts.save(updated, expected_version=draft.draft_version)
            self._uow.commit()
        return DraftResult(updated)


class SubmitGenerationHandler:
    def __init__(
        self,
        uow: UnitOfWork,
        clock: Clock,
        snapshots: DataSnapshotVersionProvider,
        executor: GenerationExecutor,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._snapshots = snapshots
        self._executor = executor

    def handle(self, command: SubmitGeneration) -> GenerationIntentResult:
        with self._uow:
            existing = self._uow.generation_intents.get(command.generation_intent_id)
            if existing is not None:
                _check_existing_intent(existing, command)
                return _intent_result(existing, reused=True)

            draft = _owned_draft(self._uow, command.draft_id, command.principal_id)
            _check_version(draft, command.draft_version)
            issues = _readiness_issues(draft)
            if issues:
                raise DraftNotReadyError(issues)

            data_version = self._snapshots.current_version(draft.city_id)
            snapshot = _canonical_input_snapshot(draft, data_version)
            snapshot_hash = _snapshot_hash(snapshot)
            now = self._clock.now()
            intent = GenerationIntent(
                generation_intent_id=command.generation_intent_id,
                principal_id=command.principal_id,
                draft_id=command.draft_id,
                draft_version=command.draft_version,
                status=GenerationStatus.QUEUED,
                input_schema_version="generation-input-v1",
                input_snapshot=snapshot,
                input_snapshot_hash=snapshot_hash,
                data_snapshot_version=data_version,
                random_seed=int(snapshot_hash[:15], 16),
                submitted_at=now,
                updated_at=now,
            )
            self._uow.generation_intents.add(intent)
            self._uow.commit()

        self._executor.submit(intent.generation_intent_id)
        return _intent_result(intent, reused=False)


class ExecuteGenerationHandler:
    """Claim and execute one intent, keeping solver work outside transactions."""

    def __init__(
        self,
        uow: UnitOfWork,
        clock: Clock,
        ids: IdGenerator,
        gateway: SolverGateway,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids
        self._gateway = gateway

    def handle(self, generation_intent_id: str) -> GenerationExecutionResult:
        with self._uow:
            intent = self._uow.generation_intents.get(generation_intent_id)
            if intent is None:
                raise ResourceNotFoundError
            if intent.status is GenerationStatus.COMPLETED:
                return GenerationExecutionResult(
                    intent.generation_intent_id, intent.status, None,
                    intent.trip_id, intent.trip_revision_id, True,
                )
            try:
                running = intent.claim_running(now=self._clock.now())
            except ValueError as exc:
                raise InvalidStateTransitionError(str(exc)) from exc
            self._uow.generation_intents.save(running, expected_status=intent.status.value)
            self._uow.commit()

        solver_run_id = self._ids.new_id("solver_run")
        request = SolverRequest(
            solver_run_id,
            running.generation_intent_id,
            running.input_snapshot,
            running.input_snapshot_hash,
            running.data_snapshot_version,
            running.random_seed,
        )
        try:
            outcome = self._gateway.solve(request)
        except SolverExecutionError as exc:
            return self._record_failure(running, exc.code, exc.retryable)

        now = self._clock.now()
        run = SolverRun(
            solver_run_id, running.generation_intent_id,
            "completed" if outcome.quality_gate_passed else "failed",
            outcome.quality_gate_passed, outcome.solver_version,
            outcome.constraint_version, outcome.parameter_version,
            outcome.audit_payload, now,
        )
        with self._uow:
            current = self._uow.generation_intents.get(generation_intent_id)
            if current is None or current.status is not GenerationStatus.RUNNING:
                raise InvalidStateTransitionError("generation intent is no longer running")
            self._uow.solver_runs.add(run)
            if not outcome.quality_gate_passed:
                failed = current.fail(code="quality_gate_failed", retryable=False, now=now)
                self._uow.generation_intents.save(failed, expected_status="running")
                self._uow.commit()
                return GenerationExecutionResult(
                    generation_intent_id, failed.status, solver_run_id, None, None, False
                )

            trip_id = self._ids.new_id("trip")
            revision_id = self._ids.new_id("revision")
            draft = self._uow.drafts.get(current.draft_id)
            if draft is None:
                raise ResourceNotFoundError
            revision = TripRevision(
                revision_id, trip_id, 1, generation_intent_id,
                outcome.completion_kind, outcome.has_soft_degradation,
                outcome.result_schema_version, outcome.result_snapshot,
                outcome.result_snapshot_hash, now,
            )
            trip = Trip(
                trip_id, current.principal_id, draft.city_id, current.draft_id,
                revision_id, now, now,
            )
            self._uow.trips.add(trip)
            self._uow.trip_revisions.add(revision)
            completed = current.complete(
                trip_id=trip_id, trip_revision_id=revision_id, now=now
            )
            self._uow.generation_intents.save(completed, expected_status="running")
            self._uow.commit()
        return GenerationExecutionResult(
            generation_intent_id, completed.status, solver_run_id,
            trip_id, revision_id, False,
        )

    def _record_failure(
        self, intent: GenerationIntent, code: str, retryable: bool
    ) -> GenerationExecutionResult:
        with self._uow:
            current = self._uow.generation_intents.get(intent.generation_intent_id)
            if current is None or current.status is not GenerationStatus.RUNNING:
                raise InvalidStateTransitionError("generation intent is no longer running")
            failed = current.fail(code=code, retryable=retryable, now=self._clock.now())
            self._uow.generation_intents.save(failed, expected_status="running")
            self._uow.commit()
        return GenerationExecutionResult(
            intent.generation_intent_id, failed.status, None, None, None, False
        )


def _owned_draft(uow: UnitOfWork, draft_id: str, principal_id: str) -> TripDraft:
    draft = uow.drafts.get(draft_id)
    if draft is None or draft.principal_id != principal_id:
        raise ResourceNotFoundError
    return draft


def _check_version(draft: TripDraft, expected_version: int) -> None:
    if draft.draft_version != expected_version:
        raise DraftVersionConflictError(
            expected_version=expected_version,
            current_version=draft.draft_version,
        )


def _check_existing_intent(intent: GenerationIntent, command: SubmitGeneration) -> None:
    if intent.principal_id != command.principal_id:
        raise ResourceNotFoundError
    if intent.draft_id != command.draft_id or intent.draft_version != command.draft_version:
        raise GenerationIntentConflictError


def _readiness_issues(draft: TripDraft) -> tuple[str, ...]:
    issues: list[str] = []
    facts = draft.travel_facts
    if facts is None:
        issues.append("travel_facts_missing")
    elif not facts.ready_for_generation:
        if not facts.arrival_confirmation.permits_generation:
            issues.append("arrival_transport_unconfirmed")
        if not facts.departure_confirmation.permits_generation:
            issues.append("departure_transport_unconfirmed")
    if not draft.selected_attraction_ids:
        issues.append("attraction_selection_empty")
    return tuple(issues)


def _canonical_input_snapshot(
    draft: TripDraft,
    data_snapshot_version: str,
) -> dict[str, object]:
    assert draft.travel_facts is not None
    facts = _jsonable(asdict(draft.travel_facts))
    preferences = [
        _jsonable(asdict(item))
        for item in sorted(
            draft.visit_period_preferences,
            key=lambda preference: preference.attraction_id,
        )
    ]
    return {
        "schema_version": "generation-input-v1",
        "city_id": draft.city_id,
        "travel_facts": facts,
        "selected_attraction_ids": list(sorted(draft.selected_attraction_ids)),
        "visit_period_preferences": preferences,
        "data_snapshot_version": data_snapshot_version,
    }


def _jsonable(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _snapshot_hash(snapshot: dict[str, object]) -> str:
    serialized = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _intent_result(intent: GenerationIntent, *, reused: bool) -> GenerationIntentResult:
    return GenerationIntentResult(
        generation_intent_id=intent.generation_intent_id,
        status=intent.status,
        draft_id=intent.draft_id,
        draft_version=intent.draft_version,
        data_snapshot_version=intent.data_snapshot_version,
        reused=reused,
    )
