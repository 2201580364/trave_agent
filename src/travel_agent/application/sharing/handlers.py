"""M1 plan-share handlers with immutable, redacted public snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from travel_agent.application.common.clock import Clock
from travel_agent.application.common.errors import (
    PlanShareIntentConflictError,
    ResourceNotFoundError,
)
from travel_agent.application.common.unit_of_work import UnitOfWork
from travel_agent.application.planning.ports import IdGenerator
from travel_agent.domain.planning import TripDraft
from travel_agent.domain.sharing import PlanShare, PublishedPlanShare

from .commands import CopyPlanShareToDraft, CreatePlanShare
from .ports import PlanShareTokenCodec


@dataclass(frozen=True, slots=True)
class PlanShareResult:
    share: PlanShare
    public_token: str
    reused: bool


@dataclass(frozen=True, slots=True)
class CopiedDraftResult:
    draft: TripDraft


class CreatePlanShareHandler:
    def __init__(
        self,
        uow: UnitOfWork,
        clock: Clock,
        ids: IdGenerator,
        tokens: PlanShareTokenCodec,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids
        self._tokens = tokens

    def handle(self, command: CreatePlanShare) -> PlanShareResult:
        with self._uow:
            existing = self._uow.plan_shares.get_by_intent(
                command.plan_share_intent_id
            )
            if existing is not None:
                if existing.principal_id != command.principal_id:
                    raise ResourceNotFoundError
                if (
                    existing.trip_id != command.trip_id
                    or existing.revision_id != command.revision_id
                    or existing.template != command.template
                ):
                    raise PlanShareIntentConflictError
                return PlanShareResult(
                    existing,
                    self._tokens.issue(existing.plan_share_id),
                    True,
                )

            trip = self._uow.trips.get(command.trip_id)
            revision = self._uow.trip_revisions.get(command.revision_id)
            if (
                trip is None
                or trip.principal_id != command.principal_id
                or revision is None
                or revision.trip_id != trip.trip_id
            ):
                raise ResourceNotFoundError
            if command.template != "simple":
                raise ValueError("only the simple plan-share template is available")

            plan_share_id = self._ids.new_id("plan_share")
            public_token = self._tokens.issue(plan_share_id)
            snapshot = _public_share_snapshot(trip.city_id, revision)
            now = self._clock.now()
            share = PlanShare(
                plan_share_id=plan_share_id,
                plan_share_intent_id=command.plan_share_intent_id,
                principal_id=command.principal_id,
                trip_id=trip.trip_id,
                revision_id=revision.trip_revision_id,
                status="published",
                template=command.template,
                public_token_hash=self._tokens.hash(public_token),
                share_schema_version="plan-share-v1",
                share_snapshot=snapshot,
                share_snapshot_hash=_snapshot_hash(snapshot),
                created_at=now,
                published_at=now,
            )
            self._uow.plan_shares.add(share)
            self._uow.commit()
        return PlanShareResult(share, public_token, False)


class GetPublishedPlanShareHandler:
    def __init__(self, uow: UnitOfWork, tokens: PlanShareTokenCodec) -> None:
        self._uow = uow
        self._tokens = tokens

    def handle(self, public_token: str) -> PublishedPlanShare:
        with self._uow:
            share = self._uow.plan_shares.get_by_public_token_hash(
                self._tokens.hash(public_token)
            )
            if share is None or share.status != "published":
                raise ResourceNotFoundError
            return PublishedPlanShare(
                share.plan_share_id,
                share.template,
                share.share_snapshot,
                share.published_at,
            )


class CopyPlanShareToDraftHandler:
    def __init__(
        self,
        uow: UnitOfWork,
        clock: Clock,
        ids: IdGenerator,
        tokens: PlanShareTokenCodec,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids
        self._tokens = tokens

    def handle(self, command: CopyPlanShareToDraft) -> CopiedDraftResult:
        with self._uow:
            share = self._uow.plan_shares.get_by_public_token_hash(
                self._tokens.hash(command.public_token)
            )
            if share is None or share.status != "published":
                raise ResourceNotFoundError
            revision = self._uow.trip_revisions.get(share.revision_id)
            intent = (
                self._uow.generation_intents.get(revision.generation_intent_id)
                if revision is not None
                else None
            )
            trip = self._uow.trips.get(share.trip_id)
            raw_selected = (
                intent.input_snapshot.get("selected_attraction_ids")
                if intent is not None
                else None
            )
            if (
                revision is None
                or revision.trip_id != share.trip_id
                or trip is None
                or intent is None
                or not isinstance(raw_selected, list)
                or not raw_selected
                or any(not isinstance(item, str) or not item for item in raw_selected)
            ):
                raise ResourceNotFoundError

            now = self._clock.now()
            draft = TripDraft.create(
                draft_id=self._ids.new_id("draft"),
                principal_id=command.principal_id,
                city_id=trip.city_id,
                now=now,
            ).replace_selection(
                tuple(raw_selected),
                (),
                now=now,
            )
            self._uow.drafts.save(draft)
            self._uow.commit()
        return CopiedDraftResult(draft)


def _public_share_snapshot(city_id: str, revision) -> dict[str, object]:
    result = revision.result_snapshot
    raw_days = result.get("days")
    days = raw_days if isinstance(raw_days, list) else []
    public_days: list[dict[str, object]] = []
    for raw_day in days:
        if not isinstance(raw_day, dict):
            continue
        raw_nodes = raw_day.get("nodes")
        nodes = raw_nodes if isinstance(raw_nodes, list) else []
        items: list[dict[str, object]] = []
        for raw_node in nodes:
            if not isinstance(raw_node, dict):
                continue
            name = raw_node.get("name")
            arrival_min = raw_node.get("arrival_min")
            duration_min = raw_node.get("planned_duration_min")
            if not isinstance(name, str) or not isinstance(arrival_min, int):
                continue
            fixed = raw_node.get("timing_kind") == "fixed_event"
            item: dict[str, object] = {
                "name": name,
                "period": _period(arrival_min),
                "duration_min": duration_min if isinstance(duration_min, int) else None,
                "timing_kind": "fixed_event" if fixed else "flexible",
            }
            if fixed:
                item["fixed_time"] = _minute_label(arrival_min)
            items.append(item)
        raw_weather = raw_day.get("weather")
        weather = raw_weather if isinstance(raw_weather, dict) else {}
        public_days.append(
            {
                "date": raw_day.get("date"),
                "weather": {
                    "condition": weather.get("condition"),
                    "basis": weather.get("basis"),
                },
                "items": items,
            }
        )
    dates = [
        day["date"]
        for day in public_days
        if isinstance(day.get("date"), str)
    ]
    raw_unplaced = result.get("unplaced")
    return {
        "schema_version": "plan-share-v1",
        "content_kind": "planned_itinerary",
        "title": f"{_city_name(city_id)}行程计划",
        "city_id": city_id,
        "city_name": _city_name(city_id),
        "start_date": min(dates) if dates else None,
        "end_date": max(dates) if dates else None,
        "revision_number": revision.revision_number,
        "completion_kind": revision.completion_kind.value,
        "has_soft_degradation": revision.has_soft_degradation,
        "scheduled_count": sum(len(day["items"]) for day in public_days),
        "unplaced_count": len(raw_unplaced) if isinstance(raw_unplaced, list) else 0,
        "days": public_days,
        "data_notice": "这是出发前的计划摘要，开放、天气和交通请在出发前再次确认。",
        "privacy_notice": "分享内容不包含账号凭证、到离交通详情、私人备注和内部路线数据。",
    }


def _period(arrival_min: int) -> str:
    minute = arrival_min % 1440
    if minute < 12 * 60:
        return "morning"
    if minute < 18 * 60:
        return "afternoon"
    return "evening"


def _minute_label(value: int) -> str:
    minute = value % 1440
    return f"{minute // 60:02d}:{minute % 60:02d}"


def _city_name(city_id: str) -> str:
    return "杭州" if city_id == "hangzhou" else city_id


def _snapshot_hash(snapshot: dict[str, object]) -> str:
    canonical = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
