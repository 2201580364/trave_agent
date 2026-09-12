"""Read-only review queries (H3/S7-1)."""

from __future__ import annotations

from collections.abc import Callable

from travel_agent.application.common.errors import ResourceNotFoundError
from travel_agent.domain.admin import AdminPrincipal
from travel_agent.domain.place_catalog import PlaceRevision, PlaceRevisionEvidence

from .review_ports import ReviewQueryUnitOfWork
from .review_readiness import evaluate_review_readiness
from .review_support import ReviewSupport


class ReviewQueryService(ReviewSupport):
    def __init__(self, uow_factory: Callable[[], ReviewQueryUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def revisions_by_ids(
        self,
        principal: AdminPrincipal,
        *,
        revision_ids: tuple[str, ...],
    ) -> dict[str, PlaceRevision]:
        self._require(principal, "place:review:read")
        normalized = tuple(dict.fromkeys(revision_ids))
        with self._uow_factory() as uow:
            return {
                revision.place_revision_id: revision
                for revision in uow.reviews.get_revisions(normalized)
            }

    def list_revisions(
        self,
        principal: AdminPrincipal,
        *,
        lifecycle_status: str | None,
        limit: int,
        offset: int,
        keyword: str | None = None,
        admin_area: str | None = None,
        place_kind: str | None = None,
    ) -> tuple[PlaceRevision, ...]:
        self._require(principal, "place:candidate:read")
        with self._uow_factory() as uow:
            return uow.reviews.list_revisions(
                lifecycle_status=lifecycle_status,
                keyword=_optional_query(keyword),
                admin_area=_optional_query(admin_area),
                place_kind=_optional_query(place_kind),
                limit=limit,
                offset=offset,
            )

    def count_revisions(
        self,
        principal: AdminPrincipal,
        *,
        lifecycle_status: str | None,
        keyword: str | None = None,
        admin_area: str | None = None,
        place_kind: str | None = None,
    ) -> int:
        self._require(principal, "place:candidate:read")
        with self._uow_factory() as uow:
            return uow.reviews.count_revisions(
                lifecycle_status=lifecycle_status,
                keyword=_optional_query(keyword),
                admin_area=_optional_query(admin_area),
                place_kind=_optional_query(place_kind),
            )

    def review_readiness_by_revision_ids(
        self,
        principal: AdminPrincipal,
        *,
        revision_ids: tuple[str, ...],
    ) -> dict[str, dict[str, object]]:
        """Return collection/review readiness without mutating workflow state."""

        self._require(principal, "place:candidate:read")
        normalized = tuple(dict.fromkeys(revision_ids))
        with self._uow_factory() as uow:
            result: dict[str, dict[str, object]] = {}
            for revision_id in normalized:
                evidence = uow.catalog.load_revision_evidence(revision_id)
                if evidence is None:
                    continue
                result[revision_id] = evaluate_review_readiness(
                    evidence,
                    uow.reviews.get_open_task_for_revision(revision_id),
                )
            return result

    def dashboard_summary(self, principal: AdminPrincipal) -> dict[str, object]:
        self._require(principal, "place:candidate:read")
        with self._uow_factory() as uow:
            candidates = uow.reviews.count_revisions(lifecycle_status="candidate")
            verified = uow.reviews.count_revisions(lifecycle_status="human_verified")
            published = uow.reviews.count_revisions(lifecycle_status="published")
            tasks: dict[str, int] = {}
            for task_status in (
                "ready_for_review",
                "in_review",
                "changes_requested",
                "approved",
                "closed",
            ):
                tasks[task_status] = uow.reviews.count_tasks(status=task_status)
            recent = uow.reviews.list_tasks(
                status="ready_for_review",
                keyword=None,
                admin_area=None,
                place_kind=None,
                limit=5,
                offset=0,
            )
            return {
                "revisions": {
                    "candidate": candidates,
                    "human_verified": verified,
                    "published": published,
                },
                "review_tasks": tasks,
                "recent_ready_tasks": tuple(recent),
            }

    def get_revision(self, principal: AdminPrincipal, *, revision_id: str) -> PlaceRevision:
        self._require(principal, "place:candidate:read")
        with self._uow_factory() as uow:
            revision = uow.reviews.get_revision(revision_id)
            if revision is None:
                raise ResourceNotFoundError
            return revision

    def get_revision_evidence(
        self, principal: AdminPrincipal, *, revision_id: str
    ) -> PlaceRevisionEvidence:
        """Return revision-scoped geometry/access-point evidence for O04."""

        self._require(principal, "place:candidate:read")
        with self._uow_factory() as uow:
            evidence = uow.catalog.load_revision_evidence(revision_id)
            if evidence is None:
                raise ResourceNotFoundError
            return evidence


def _optional_query(value: str | None) -> str | None:
    normalized = value.strip() if value else ""
    return normalized or None
