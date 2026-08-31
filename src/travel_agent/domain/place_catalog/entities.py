"""Versioned place-catalog facts independent from the M1 solver model."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

PLACE_KINDS = frozenset(
    {
        "attraction",
        "scenic_area",
        "neighborhood",
        "walking_route",
        "market",
        "show",
        "experience",
    }
)
GEOMETRY_KINDS = frozenset({"point", "area", "route"})
ACCESS_POINT_KINDS = frozenset(
    {
        "visitor_entrance",
        "visitor_exit",
        "route_start",
        "route_end",
        "performance_location",
        "meeting_point",
        "area_representative",
    }
)
REVISION_STAGES = frozenset({"candidate", "human_verified", "published", "retired"})
REVIEW_STATUSES = frozenset({"candidate", "human_verified", "rejected"})
PROJECTION_STATUSES = frozenset({"candidate", "published", "retired"})
RELATION_TYPES = frozenset({"contains", "part_of", "overlaps", "same_experience"})
RELATION_RESOLUTIONS = frozenset({"pending", "resolved", "not_required"})
TIME_RULE_KINDS = frozenset({"opening_hours", "fixed_session", "last_entry"})
DATE_EXCEPTION_KINDS = frozenset({"closed", "open_override", "session_override"})
SOURCE_DECISIONS = frozenset({"approved", "conditional"})
COLLECTION_MODES = frozenset(
    {"api", "dataset_download", "manual_reference", "public_page_fetch"}
)
TARGET_STAGES = frozenset({"staging", "published"})

_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _required(*values: str) -> None:
    if any(not value for value in values):
        raise ValueError("place catalog identity fields are required")


def _aware(value: datetime | None, field: str, *, required: bool = True) -> None:
    if value is None:
        if required:
            raise ValueError(f"{field} is required")
        return
    if value.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")


def _sha256(value: str, field: str) -> None:
    if _SHA256.fullmatch(value) is None:
        raise ValueError(f"{field} must be a lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class Place:
    place_id: str
    city_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    merged_into_place_id: str | None = None

    def __post_init__(self) -> None:
        _required(self.place_id, self.city_id)
        if self.status not in {"active", "inactive", "merged"}:
            raise ValueError("place status is invalid")
        if self.status == "merged" and not self.merged_into_place_id:
            raise ValueError("merged place requires a redirect target")
        if self.status != "merged" and self.merged_into_place_id is not None:
            raise ValueError("only merged places may have a redirect target")
        if self.merged_into_place_id == self.place_id:
            raise ValueError("place cannot redirect to itself")
        _aware(self.created_at, "place created_at")
        _aware(self.updated_at, "place updated_at")


@dataclass(frozen=True, slots=True)
class PlaceSourceRecord:
    source_record_id: str
    place_id: str
    source_id: str
    registry_id: str
    registry_sha256: str
    field_dictionary_id: str
    field_dictionary_sha256: str
    source_url: str
    collection_mode: str
    target_stage: str
    source_decision: str
    observed_at: datetime
    content_sha256: str | None
    status: str
    created_at: datetime

    def __post_init__(self) -> None:
        _required(
            self.source_record_id,
            self.place_id,
            self.source_id,
            self.registry_id,
            self.field_dictionary_id,
            self.source_url,
        )
        _sha256(self.registry_sha256, "registry_sha256")
        _sha256(self.field_dictionary_sha256, "field_dictionary_sha256")
        if self.content_sha256 is not None:
            _sha256(self.content_sha256, "content_sha256")
        if not self.source_url.startswith("https://"):
            raise ValueError("source_url must use HTTPS")
        if self.collection_mode not in COLLECTION_MODES:
            raise ValueError("collection mode is invalid")
        if self.target_stage not in TARGET_STAGES:
            raise ValueError("target stage is invalid")
        if self.source_decision not in SOURCE_DECISIONS:
            raise ValueError("source decision is invalid")
        if self.source_decision == "conditional" and self.target_stage != "staging":
            raise ValueError("conditional source records are staging only")
        if self.status not in {"active", "rejected"}:
            raise ValueError("source record status is invalid")
        _aware(self.observed_at, "source observed_at")
        _aware(self.created_at, "source created_at")


@dataclass(frozen=True, slots=True)
class PlaceRevision:
    place_revision_id: str
    place_id: str
    revision_number: int
    lifecycle_status: str
    canonical_name: str
    aliases: tuple[str, ...]
    place_kind: str
    category: str
    admin_area: str
    address: str | None
    geometry_kind: str
    duration_min: int
    duration_recommended: int
    duration_max: int
    internal_travel_min: int
    energy_level: int
    indoor_outdoor: str
    suitable_periods: tuple[str, ...]
    audience_tags: tuple[str, ...]
    rain_suitability: str
    is_always_open: bool
    solver_eligible: bool
    conflicts_resolved: bool
    source_record_ids: tuple[str, ...]
    created_at: datetime
    reviewed_at: datetime | None = None
    published_at: datetime | None = None
    review_flags: tuple[str, ...] = ()
    revision_version: int = 1

    def __post_init__(self) -> None:
        _required(
            self.place_revision_id,
            self.place_id,
            self.canonical_name,
            self.category,
            self.admin_area,
        )
        if self.revision_number <= 0:
            raise ValueError("place revision number must be positive")
        if self.lifecycle_status not in REVISION_STAGES:
            raise ValueError("place revision lifecycle status is invalid")
        if self.place_kind not in PLACE_KINDS:
            raise ValueError("place kind is invalid")
        if self.geometry_kind not in GEOMETRY_KINDS:
            raise ValueError("geometry kind is invalid")
        if not (0 <= self.duration_min <= self.duration_recommended <= self.duration_max):
            raise ValueError("place duration range is invalid")
        if self.duration_recommended <= 0:
            raise ValueError("recommended duration must be positive")
        if self.internal_travel_min < 0:
            raise ValueError("internal travel duration must be non-negative")
        if not 1 <= self.energy_level <= 5:
            raise ValueError("energy level must be between 1 and 5")
        if self.indoor_outdoor not in {"indoor", "outdoor", "mixed"}:
            raise ValueError("indoor_outdoor is invalid")
        if self.rain_suitability not in {"suitable", "conditional", "unsuitable"}:
            raise ValueError("rain suitability is invalid")
        if len(self.aliases) != len(set(self.aliases)):
            raise ValueError("place aliases must be unique")
        if len(self.source_record_ids) != len(set(self.source_record_ids)):
            raise ValueError("place revision source records must be unique")
        if len(self.review_flags) != len(set(self.review_flags)):
            raise ValueError("place revision review flags must be unique")
        if self.revision_version <= 0:
            raise ValueError("place revision version must be positive")
        _aware(self.created_at, "place revision created_at")
        _aware(self.reviewed_at, "place revision reviewed_at", required=False)
        _aware(self.published_at, "place revision published_at", required=False)
        if self.lifecycle_status in {"human_verified", "published"} and self.reviewed_at is None:
            raise ValueError("verified place revision requires reviewed_at")
        if self.lifecycle_status == "published":
            if self.published_at is None or not self.source_record_ids:
                raise ValueError("published place revision requires sources and published_at")
        elif self.published_at is not None:
            raise ValueError("only published place revisions may have published_at")


@dataclass(frozen=True, slots=True)
class PlaceGeometry:
    geometry_id: str
    place_revision_id: str
    geometry_kind: str
    geometry: dict[str, Any]
    source_record_id: str
    review_status: str
    active: bool
    created_at: datetime
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        _required(self.geometry_id, self.place_revision_id, self.source_record_id)
        if self.geometry_kind not in GEOMETRY_KINDS:
            raise ValueError("geometry kind is invalid")
        if not self.geometry:
            raise ValueError("geometry payload is required")
        if self.review_status not in REVIEW_STATUSES:
            raise ValueError("geometry review status is invalid")
        _aware(self.created_at, "geometry created_at")
        _aware(self.reviewed_at, "geometry reviewed_at", required=False)
        if self.review_status == "human_verified" and self.reviewed_at is None:
            raise ValueError("verified geometry requires reviewed_at")


@dataclass(frozen=True, slots=True)
class PlaceAccessPoint:
    access_point_id: str
    place_revision_id: str
    access_point_kind: str
    name: str
    lat: Decimal
    lng: Decimal
    source_record_id: str
    review_status: str
    active: bool
    fetched_at: datetime | None
    reviewed_at: datetime | None
    created_at: datetime

    def __post_init__(self) -> None:
        _required(
            self.access_point_id,
            self.place_revision_id,
            self.name,
            self.source_record_id,
        )
        if self.access_point_kind not in ACCESS_POINT_KINDS:
            raise ValueError("access point kind is invalid")
        if not Decimal("-90") <= self.lat <= Decimal("90"):
            raise ValueError("access point latitude is invalid")
        if not Decimal("-180") <= self.lng <= Decimal("180"):
            raise ValueError("access point longitude is invalid")
        if self.review_status not in REVIEW_STATUSES:
            raise ValueError("access point review status is invalid")
        _aware(self.fetched_at, "access point fetched_at", required=False)
        _aware(self.reviewed_at, "access point reviewed_at", required=False)
        _aware(self.created_at, "access point created_at")
        if self.review_status == "human_verified" and self.reviewed_at is None:
            raise ValueError("verified access point requires reviewed_at")


@dataclass(frozen=True, slots=True)
class PlaceTimeRule:
    time_rule_id: str
    place_revision_id: str
    rule_kind: str
    weekdays: tuple[int, ...]
    start_minute: int | None
    end_minute: int | None
    last_entry_minute: int | None
    valid_from: date | None
    valid_to: date | None
    source_record_id: str
    review_status: str
    active: bool
    created_at: datetime
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        _required(self.time_rule_id, self.place_revision_id, self.source_record_id)
        if self.rule_kind not in TIME_RULE_KINDS:
            raise ValueError("time rule kind is invalid")
        if not self.weekdays or any(day < 1 or day > 7 for day in self.weekdays):
            raise ValueError("time rule weekdays must use ISO weekday numbers")
        if len(self.weekdays) != len(set(self.weekdays)):
            raise ValueError("time rule weekdays must be unique")
        for value in (self.start_minute, self.end_minute, self.last_entry_minute):
            if value is not None and not 0 <= value <= 2880:
                raise ValueError("time rule minute is invalid")
        if self.start_minute is None and self.end_minute is None:
            raise ValueError("time rule requires a start or end minute")
        if (
            self.start_minute is not None
            and self.end_minute is not None
            and self.end_minute <= self.start_minute
        ):
            raise ValueError("time rule end must be after start")
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("time rule validity range is invalid")
        if self.review_status not in REVIEW_STATUSES:
            raise ValueError("time rule review status is invalid")
        _aware(self.created_at, "time rule created_at")
        _aware(self.reviewed_at, "time rule reviewed_at", required=False)
        if self.review_status == "human_verified" and self.reviewed_at is None:
            raise ValueError("verified time rule requires reviewed_at")


@dataclass(frozen=True, slots=True)
class PlaceClosure:
    closure_id: str
    place_revision_id: str
    weekday: int
    source_record_id: str
    review_status: str
    active: bool
    created_at: datetime
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        _required(self.closure_id, self.place_revision_id, self.source_record_id)
        if not 1 <= self.weekday <= 7:
            raise ValueError("closure weekday is invalid")
        if self.review_status not in REVIEW_STATUSES:
            raise ValueError("closure review status is invalid")
        _aware(self.created_at, "closure created_at")
        _aware(self.reviewed_at, "closure reviewed_at", required=False)
        if self.review_status == "human_verified" and self.reviewed_at is None:
            raise ValueError("verified closure requires reviewed_at")


@dataclass(frozen=True, slots=True)
class PlaceDateException:
    date_exception_id: str
    place_revision_id: str
    service_date: date
    exception_kind: str
    start_minute: int | None
    end_minute: int | None
    last_entry_minute: int | None
    source_record_id: str
    review_status: str
    active: bool
    created_at: datetime
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        _required(self.date_exception_id, self.place_revision_id, self.source_record_id)
        if self.exception_kind not in DATE_EXCEPTION_KINDS:
            raise ValueError("date exception kind is invalid")
        for value in (self.start_minute, self.end_minute, self.last_entry_minute):
            if value is not None and not 0 <= value <= 2880:
                raise ValueError("date exception minute is invalid")
        if self.exception_kind != "closed" and (
            self.start_minute is None or self.end_minute is None
        ):
            raise ValueError("open/session exception requires a time range")
        if (
            self.start_minute is not None
            and self.end_minute is not None
            and self.end_minute <= self.start_minute
        ):
            raise ValueError("date exception end must be after start")
        if self.review_status not in REVIEW_STATUSES:
            raise ValueError("date exception review status is invalid")
        _aware(self.created_at, "date exception created_at")
        _aware(self.reviewed_at, "date exception reviewed_at", required=False)
        if self.review_status == "human_verified" and self.reviewed_at is None:
            raise ValueError("verified date exception requires reviewed_at")


@dataclass(frozen=True, slots=True)
class PlaceRelation:
    relation_id: str
    from_place_id: str
    to_place_id: str
    relation_type: str
    source_record_id: str
    review_status: str
    resolution_status: str
    decision_note: str | None
    active: bool
    created_at: datetime
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        _required(
            self.relation_id,
            self.from_place_id,
            self.to_place_id,
            self.source_record_id,
        )
        if self.from_place_id == self.to_place_id:
            raise ValueError("place relation cannot target itself")
        if self.relation_type not in RELATION_TYPES:
            raise ValueError("place relation type is invalid")
        if self.review_status not in REVIEW_STATUSES:
            raise ValueError("place relation review status is invalid")
        if self.resolution_status not in RELATION_RESOLUTIONS:
            raise ValueError("place relation resolution status is invalid")
        if self.resolution_status == "resolved" and not self.decision_note:
            raise ValueError("resolved place relation requires a decision note")
        _aware(self.created_at, "place relation created_at")
        _aware(self.reviewed_at, "place relation reviewed_at", required=False)
        if self.review_status == "human_verified" and self.reviewed_at is None:
            raise ValueError("verified place relation requires reviewed_at")


@dataclass(frozen=True, slots=True)
class ResearchSnapshot:
    snapshot_id: str
    data_snapshot_version: str
    city_id: str
    content_sha256: str
    source_batch_id: str
    snapshot_payload: dict[str, Any]
    created_at: datetime
    status: str = "published"

    def __post_init__(self) -> None:
        _required(self.snapshot_id, self.data_snapshot_version, self.city_id, self.source_batch_id)
        _sha256(self.content_sha256, "research snapshot content_sha256")
        if self.status != "published":
            raise ValueError("research snapshot status is invalid")
        if not isinstance(self.snapshot_payload, dict):
            raise ValueError("research snapshot payload must be an object")
        _aware(self.created_at, "research snapshot created_at")


@dataclass(frozen=True, slots=True)
class PublicationBatch:
    batch_id: str
    city_id: str
    operation_intent_id: str
    created_by: str
    created_at: datetime
    status: str = "preview"
    snapshot_id: str | None = None

    def __post_init__(self) -> None:
        _required(self.batch_id, self.city_id, self.operation_intent_id, self.created_by)
        if self.status not in {"preview", "executing", "published", "partial_failed", "failed"}:
            raise ValueError("publication batch status is invalid")
        _aware(self.created_at, "publication batch created_at")
        if self.status == "published" and not self.snapshot_id:
            raise ValueError("published publication batch requires snapshot_id")


@dataclass(frozen=True, slots=True)
class PublicationBatchItem:
    batch_item_id: str
    batch_id: str
    place_revision_id: str
    status: str
    reason_codes: tuple[str, ...] = ()
    projection_id: str | None = None
    published_at: datetime | None = None

    def __post_init__(self) -> None:
        _required(self.batch_item_id, self.batch_id, self.place_revision_id)
        if self.status not in {"pending", "publishable", "blocked", "published", "failed"}:
            raise ValueError("publication batch item status is invalid")
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("publication batch item reason codes must be unique")
        if self.status == "published" and not self.projection_id:
            raise ValueError("published batch item requires projection_id")
        if self.status == "published" and self.published_at is None:
            raise ValueError("published batch item requires published_at")
        _aware(self.published_at, "publication batch item published_at", required=False)


@dataclass(frozen=True, slots=True)
class SelectionExclusionGroup:
    exclusion_group_id: str
    city_id: str
    name: str
    status: str
    review_status: str
    decision_note: str
    created_at: datetime
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        _required(self.exclusion_group_id, self.city_id, self.name, self.decision_note)
        if self.status not in {"active", "retired"}:
            raise ValueError("selection exclusion group status is invalid")
        if self.review_status not in REVIEW_STATUSES:
            raise ValueError("selection exclusion group review status is invalid")
        _aware(self.created_at, "selection exclusion group created_at")
        _aware(self.reviewed_at, "selection exclusion group reviewed_at", required=False)
        if self.review_status == "human_verified" and self.reviewed_at is None:
            raise ValueError("verified exclusion group requires reviewed_at")


@dataclass(frozen=True, slots=True)
class SelectionExclusionMember:
    exclusion_group_id: str
    place_id: str
    created_at: datetime

    def __post_init__(self) -> None:
        _required(self.exclusion_group_id, self.place_id)
        _aware(self.created_at, "selection exclusion member created_at")


@dataclass(frozen=True, slots=True)
class SolverPlaceProjection:
    projection_id: str
    projection_version: str
    data_snapshot_version: str
    place_id: str
    place_revision_id: str
    solver_node_id: int
    place_kind: str
    geometry_kind: str
    arrival_access_point_id: str
    departure_access_point_id: str
    duration_min: int
    duration_recommended: int
    duration_max: int
    internal_travel_min: int
    solver_payload: dict[str, Any]
    projection_hash: str
    status: str
    gate_reason_codes: tuple[str, ...]
    created_at: datetime
    published_at: datetime | None = None

    def __post_init__(self) -> None:
        _required(
            self.projection_id,
            self.projection_version,
            self.data_snapshot_version,
            self.place_id,
            self.place_revision_id,
            self.arrival_access_point_id,
            self.departure_access_point_id,
        )
        if self.solver_node_id <= 0:
            raise ValueError("solver node id must be positive")
        if self.place_kind not in PLACE_KINDS:
            raise ValueError("projection place kind is invalid")
        if self.geometry_kind not in GEOMETRY_KINDS:
            raise ValueError("projection geometry kind is invalid")
        if not (0 <= self.duration_min <= self.duration_recommended <= self.duration_max):
            raise ValueError("projection duration range is invalid")
        if self.duration_recommended <= 0 or self.internal_travel_min < 0:
            raise ValueError("projection duration values are invalid")
        _sha256(self.projection_hash, "projection_hash")
        if self.status not in PROJECTION_STATUSES:
            raise ValueError("projection status is invalid")
        if len(self.gate_reason_codes) != len(set(self.gate_reason_codes)):
            raise ValueError("projection gate reason codes must be unique")
        _aware(self.created_at, "projection created_at")
        _aware(self.published_at, "projection published_at", required=False)
        if self.status == "published":
            if self.published_at is None or self.gate_reason_codes:
                raise ValueError("published projection requires a clean gate and published_at")
        elif self.published_at is not None:
            raise ValueError("only published projections may have published_at")
