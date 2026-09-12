"""Revision lifecycle and evidence review (H3/S7-1)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from travel_agent.application.common.clock import Clock
from travel_agent.application.common.errors import ResourceNotFoundError
from travel_agent.application.planning.ports import IdGenerator
from travel_agent.domain.admin import AdminPrincipal
from travel_agent.domain.place_catalog import PlaceRevision

from .errors import (
    PlaceRevisionVersionConflictError,
    ReviewRevisionNotCandidateError,
    ReviewTaskConflictError,
    ReviewTaskNotFoundError,
)
from .review_evidence import _evidence_digest
from .review_ports import RevisionLifecycleUnitOfWork
from .review_support import ReviewSupport, _digest, _revision_digest


class RevisionLifecycleService(ReviewSupport):
    def __init__(
        self, uow_factory: Callable[[], RevisionLifecycleUnitOfWork], clock: Clock, ids: IdGenerator
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._ids = ids

    def review_evidence(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        evidence_kind: str,
        evidence_id: str,
        review_status: str,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        self._require(principal, "place:review:decide")
        reason_text = self._validate_reason(reason_code, reason_text)
        digest = _digest(
            {
                "revision_id": revision_id,
                "evidence_kind": evidence_kind,
                "evidence_id": evidence_id,
                "review_status": review_status,
                "reason_code": reason_code,
                "reason_text": reason_text,
            }
        )
        now = self._clock.now()
        with self._uow_factory() as uow:
            replay = self._replay(uow, operation_intent_id, digest)
            if replay is not None:
                revision = uow.reviews.get_revision(revision_id)
                if revision is None:
                    raise ResourceNotFoundError
                return revision
            actor = self._actor(uow, principal)
            revision = uow.reviews.get_revision(revision_id)
            if revision is None:
                raise ResourceNotFoundError
            if revision.lifecycle_status != "candidate":
                raise ReviewRevisionNotCandidateError
            task = uow.reviews.get_open_task_for_revision(revision_id)
            if task is None:
                raise ReviewTaskNotFoundError
            evidence = uow.catalog.load_revision_evidence(revision_id)
            if evidence is None:
                raise ResourceNotFoundError
            items = (
                evidence.geometries
                if evidence_kind == "geometry"
                else evidence.access_points
                if evidence_kind == "access_point"
                else evidence.time_rules
                if evidence_kind == "time_rule"
                else evidence.closures
                if evidence_kind == "closure"
                else evidence.date_exceptions
                if evidence_kind == "date_exception"
                else evidence.relations
                if evidence_kind == "relation"
                else ()
            )
            current = next(
                (
                    item
                    for item in items
                    if getattr(item, f"{evidence_kind}_id", None) == evidence_id
                ),
                None,
            )
            if current is None or not current.active:
                raise ResourceNotFoundError
            try:
                updated = uow.catalog.review_evidence(
                    revision_id=revision_id,
                    evidence_kind=evidence_kind,
                    evidence_id=evidence_id,
                    review_status=review_status,
                    reviewed_at=now,
                    place_id=revision.place_id,
                )
            except ValueError as exc:
                if "not found" in str(exc):
                    raise ResourceNotFoundError from exc
                raise
            uow.audits.add(
                self._event(
                    actor,
                    action="PLACE_EVIDENCE_REVIEWED",
                    target_type=f"place_{evidence_kind}",
                    target_id=evidence_id,
                    target_revision=str(updated.revision_number),
                    before_digest=_evidence_digest(current),
                    after_digest=_digest(
                        {
                            "evidence_id": evidence_id,
                            "review_status": review_status,
                            "reviewed_at": (
                                now.isoformat() if review_status == "human_verified" else None
                            ),
                            "active": True,
                        }
                    ),
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=digest,
                )
            )
            uow.commit()
            return updated

    def create_revision(
        self,
        principal: AdminPrincipal,
        *,
        place_id: str,
        base_revision_id: str,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        self._require(principal, "place:candidate:write")
        reason_text = self._validate_reason(reason_code, reason_text)
        operation_digest = _digest(
            {
                "place_id": place_id,
                "base_revision_id": base_revision_id,
                "reason_code": reason_code,
                "reason_text": reason_text,
            }
        )
        now = self._clock.now()
        with self._uow_factory() as uow:
            existing = self._replay(uow, operation_intent_id, operation_digest)
            if existing is not None:
                revision = uow.reviews.get_revision(existing.target_id)
                if revision is None:
                    raise ResourceNotFoundError
                return revision
            actor = self._actor(uow, principal)
            base = uow.reviews.get_revision(base_revision_id)
            latest = uow.reviews.get_latest_revision(place_id)
            if base is None or latest is None or base.place_id != place_id:
                raise ResourceNotFoundError
            revision = replace(
                base,
                place_revision_id=self._ids.new_id("place_revision"),
                revision_number=latest.revision_number + 1,
                lifecycle_status="candidate",
                solver_eligible=False,
                conflicts_resolved=False,
                reviewed_at=None,
                published_at=None,
                revision_version=1,
                relation_review_status="pending",
                created_at=now,
            )
            uow.reviews.add_revision(revision)
            # A new revision inherits the currently active evidence as a new,
            # unverified copy.  Child rows are revision-scoped, so merely
            # copying the parent row would leave the editor with an empty
            # evidence set and force needless re-entry of unchanged facts.
            evidence = uow.catalog.load_revision_evidence(base_revision_id)
            if evidence is not None:
                for item in evidence.geometries:
                    if item.active:
                        uow.catalog.add_geometry(
                            replace(
                                item,
                                geometry_id=self._ids.new_id("geometry"),
                                place_revision_id=revision.place_revision_id,
                                review_status="candidate",
                                reviewed_at=None,
                                created_at=now,
                            )
                        )
                for item in evidence.access_points:
                    if item.active:
                        uow.catalog.add_access_point(
                            replace(
                                item,
                                access_point_id=self._ids.new_id("access_point"),
                                place_revision_id=revision.place_revision_id,
                                review_status="candidate",
                                reviewed_at=None,
                                created_at=now,
                            )
                        )
                for item in evidence.time_rules:
                    if item.active:
                        uow.catalog.add_time_rule(
                            replace(
                                item,
                                time_rule_id=self._ids.new_id("time_rule"),
                                place_revision_id=revision.place_revision_id,
                                review_status="candidate",
                                reviewed_at=None,
                                created_at=now,
                            )
                        )
                for item in evidence.closures:
                    if item.active:
                        uow.catalog.add_closure(
                            replace(
                                item,
                                closure_id=self._ids.new_id("closure"),
                                place_revision_id=revision.place_revision_id,
                                review_status="candidate",
                                reviewed_at=None,
                                created_at=now,
                            )
                        )
                for item in evidence.date_exceptions:
                    if item.active:
                        uow.catalog.add_date_exception(
                            replace(
                                item,
                                date_exception_id=self._ids.new_id("date_exception"),
                                place_revision_id=revision.place_revision_id,
                                review_status="candidate",
                                reviewed_at=None,
                                created_at=now,
                            )
                        )
            uow.audits.add(
                self._event(
                    actor,
                    action="PLACE_REVISION_CREATED",
                    target_type="place_revision",
                    target_id=revision.place_revision_id,
                    target_revision=str(revision.revision_number),
                    before_digest=_revision_digest(base),
                    after_digest=_revision_digest(revision),
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=operation_digest,
                )
            )
            uow.commit()
            return revision

    def update_revision(
        self,
        principal: AdminPrincipal,
        *,
        revision_id: str,
        expected_revision_number: int,
        changes: dict[str, object],
        expected_revision_version: int | None = None,
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> PlaceRevision:
        self._require(principal, "place:candidate:write")
        reason_text = self._validate_reason(reason_code, reason_text)
        allowed = {
            "canonical_name",
            "aliases",
            "place_kind",
            "category",
            "admin_area",
            "address",
            "geometry_kind",
            "duration_min",
            "duration_recommended",
            "duration_max",
            "internal_travel_min",
            "energy_level",
            "indoor_outdoor",
            "suitable_periods",
            "audience_tags",
            "rain_suitability",
            "is_always_open",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError("unsupported revision fields: " + ", ".join(sorted(unknown)))
        normalized = {
            key: tuple(value)
            if key in {"aliases", "suitable_periods", "audience_tags"} and isinstance(value, list)
            else value
            for key, value in changes.items()
        }
        operation_digest = _digest(
            {
                "revision_id": revision_id,
                "expected_revision_number": expected_revision_number,
                "changes": normalized,
                "reason_code": reason_code,
                "reason_text": reason_text,
            }
        )
        with self._uow_factory() as uow:
            existing = self._replay(uow, operation_intent_id, operation_digest)
            if existing is not None:
                revision = uow.reviews.get_revision(existing.target_id)
                if revision is None:
                    raise ResourceNotFoundError
                return revision
            actor = self._actor(uow, principal)
            current = uow.reviews.get_revision(revision_id)
            if current is None:
                raise ResourceNotFoundError
            if current.lifecycle_status != "candidate":
                raise ReviewRevisionNotCandidateError
            if current.revision_number != expected_revision_number:
                raise ReviewTaskConflictError
            expected_version = (
                current.revision_version
                if expected_revision_version is None
                else expected_revision_version
            )
            if current.revision_version != expected_version:
                raise PlaceRevisionVersionConflictError

            # Imported candidates use 1/1/1 as a temporary "not collected"
            # duration marker.  The editor intentionally exposes the
            # recommended duration first; accepting that edit must establish
            # a valid range instead of returning an opaque 422.  For a real
            # range, retain the domain invariant and return a field-specific
            # validation message when the recommendation is outside it.
            if "duration_recommended" in normalized:
                recommended = normalized["duration_recommended"]
                if not isinstance(recommended, int):
                    raise ValueError("建议时长必须是整数分钟")
                has_explicit_range = "duration_min" in normalized or "duration_max" in normalized
                if (
                    not has_explicit_range
                    and current.duration_min
                    == current.duration_recommended
                    == current.duration_max
                    == 1
                    and "DURATION_NOT_COLLECTED" in current.review_flags
                ):
                    normalized["duration_min"] = recommended
                    normalized["duration_max"] = recommended
                    normalized["review_flags"] = tuple(
                        flag for flag in current.review_flags if flag != "DURATION_NOT_COLLECTED"
                    )
                else:
                    minimum = normalized.get("duration_min", current.duration_min)
                    maximum = normalized.get("duration_max", current.duration_max)
                    if (
                        not isinstance(minimum, int)
                        or not isinstance(maximum, int)
                        or not minimum <= recommended <= maximum
                    ):
                        msg = (
                            f"建议时长必须介于 {minimum} 到 {maximum} 分钟之间；"
                            f"如需调整范围，请同时修改最短和最长时长"
                        )
                        raise ValueError(msg)
            cleared_flags: set[str] = set()
            if "canonical_name" in normalized:
                cleared_flags.add("NAME_REQUIRES_HUMAN_VERIFICATION")
            if "category" in normalized:
                cleared_flags.add("CATEGORY_REQUIRES_HUMAN_VERIFICATION")
            if {"duration_min", "duration_recommended", "duration_max"}.intersection(normalized):
                cleared_flags.add("DURATION_NOT_COLLECTED")
            if normalized.get("is_always_open") is True:
                cleared_flags.add("TIME_RULES_NOT_COLLECTED")
            if cleared_flags:
                existing_flags = normalized.get("review_flags", current.review_flags)
                if not isinstance(existing_flags, tuple):
                    raise ValueError("review flags are invalid")
                normalized["review_flags"] = tuple(
                    flag for flag in existing_flags if flag not in cleared_flags
                )
            updated = replace(
                current,
                **normalized,
                solver_eligible=False,
                conflicts_resolved=False,
                reviewed_at=None,
                published_at=None,
                revision_version=current.revision_version + 1,
                relation_review_status="pending",
            )
            uow.reviews.update_revision(
                updated,
                expected_revision_number=expected_revision_number,
                expected_revision_version=expected_version,
            )
            uow.audits.add(
                self._event(
                    actor,
                    action="PLACE_REVISION_UPDATED",
                    target_type="place_revision",
                    target_id=revision_id,
                    target_revision=str(updated.revision_number),
                    before_digest=_revision_digest(current),
                    after_digest=_revision_digest(updated),
                    reason_code=reason_code,
                    reason_text=reason_text,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=operation_digest,
                )
            )
            uow.commit()
            return updated
