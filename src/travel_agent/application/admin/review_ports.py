"""Narrow review repository contracts (H3/S7-1)."""

from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Protocol, Self

from travel_agent.domain.admin import AdminActor, AdminAuditEvent
from travel_agent.domain.place_catalog import (
    PlaceReviewDecision,
    PlaceReviewTask,
    PlaceRevision,
    PlaceRevisionEvidence,
    PlaceSourceRecord,
)
from travel_agent.domain.place_catalog.repositories import PlaceCatalogRepository


class RevisionQueryRepository(Protocol):
    def get_revision(self, revision_id: str) -> PlaceRevision | None: ...

    def get_revisions(self, revision_ids: tuple[str, ...]) -> tuple[PlaceRevision, ...]: ...

    def get_latest_revision(self, place_id: str) -> PlaceRevision | None: ...

    def list_revisions(
        self,
        *,
        lifecycle_status: str | None,
        keyword: str | None,
        admin_area: str | None,
        place_kind: str | None,
        limit: int,
        offset: int,
    ) -> tuple[PlaceRevision, ...]: ...

    def count_revisions(
        self,
        *,
        lifecycle_status: str | None,
        keyword: str | None = None,
        admin_area: str | None = None,
        place_kind: str | None = None,
    ) -> int: ...


class RevisionWriteRepository(Protocol):
    def add_revision(self, revision: PlaceRevision) -> None: ...

    def update_revision(
        self,
        revision: PlaceRevision,
        *,
        expected_revision_number: int,
        expected_revision_version: int,
    ) -> None: ...

    def approve_revision(self, revision_id: str, *, reviewed_at: datetime) -> None: ...


class ReviewTaskRepository(Protocol):
    def get_task(self, task_id: str) -> PlaceReviewTask | None: ...

    def get_open_task_for_revision(self, revision_id: str) -> PlaceReviewTask | None: ...

    def list_tasks(
        self,
        *,
        status: str | None,
        keyword: str | None,
        admin_area: str | None,
        place_kind: str | None,
        limit: int,
        offset: int,
    ) -> tuple[PlaceReviewTask, ...]: ...

    def count_tasks(
        self,
        *,
        status: str | None,
        keyword: str | None = None,
        admin_area: str | None = None,
        place_kind: str | None = None,
    ) -> int: ...

    def list_decisions(self, task_id: str) -> tuple[PlaceReviewDecision, ...]: ...

    def add_task(self, task: PlaceReviewTask) -> None: ...

    def add_decision(self, decision: PlaceReviewDecision) -> None: ...

    def advance_task(
        self, task: PlaceReviewTask, *, expected_version: int, status: str, now: datetime
    ) -> None: ...


class ReviewRepository(
    RevisionQueryRepository, RevisionWriteRepository, ReviewTaskRepository, Protocol
):
    """Compatibility aggregate for the remaining review workflow."""


class AuditRepository(Protocol):
    def add(self, event: AdminAuditEvent) -> None: ...

    def get_by_operation_intent(self, operation_intent_id: str) -> AdminAuditEvent | None: ...


class ActorRepository(Protocol):
    def get(self, actor_id: str) -> AdminActor | None: ...


class ReviewUnitOfWork(Protocol):
    reviews: ReviewRepository
    catalog: PlaceCatalogRepository
    audits: AuditRepository
    actors: ActorRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...

    def commit(self) -> None: ...


class AuditContext(Protocol):
    @property
    def audits(self) -> AuditRepository: ...

    @property
    def actors(self) -> ActorRepository: ...


class SourceRevisionRepository(Protocol):
    def get_revision(self, revision_id: str) -> PlaceRevision | None: ...

    def update_revision(
        self,
        revision: PlaceRevision,
        *,
        expected_revision_number: int,
        expected_revision_version: int,
    ) -> None: ...


class SourceCatalogRepository(Protocol):
    def create_source_record(
        self, record: PlaceSourceRecord, *, revision_id: str, expected_revision_version: int
    ) -> PlaceRevision: ...

    def detach_source_record(
        self, source_record_id: str, *, revision_id: str, expected_revision_version: int
    ) -> PlaceRevision: ...

    def source_record_references(
        self, source_record_id: str, *, revision_id: str
    ) -> tuple[str, ...]: ...

    def load_revision_evidence(self, place_revision_id: str) -> PlaceRevisionEvidence | None: ...


class SourceReviewUnitOfWork(AuditContext, Protocol):
    @property
    def reviews(self) -> SourceRevisionRepository: ...

    @property
    def catalog(self) -> SourceCatalogRepository: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...

    def commit(self) -> None: ...
