"""Outbound ports required by planning use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from travel_agent.domain.planning import CompletionKind


class IdGenerator(Protocol):
    def new_id(self, prefix: str) -> str: ...


class DataSnapshotVersionProvider(Protocol):
    def current_version(self, city_id: str) -> str: ...


class GenerationExecutor(Protocol):
    def submit(self, generation_intent_id: str) -> None: ...


@dataclass(frozen=True, slots=True)
class SolverRequest:
    generation_intent_id: str
    input_snapshot: dict[str, object]
    input_snapshot_hash: str
    data_snapshot_version: str
    random_seed: int


@dataclass(frozen=True, slots=True)
class SolverOutcome:
    completion_kind: CompletionKind
    has_soft_degradation: bool
    quality_gate_passed: bool
    result_schema_version: str
    result_snapshot: dict[str, object]
    result_snapshot_hash: str
    solver_version: str
    constraint_version: str
    parameter_version: str
    audit_payload: dict[str, object]


class SolverGateway(Protocol):
    def solve(self, request: SolverRequest) -> SolverOutcome: ...


class SolverExecutionError(Exception):
    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable
