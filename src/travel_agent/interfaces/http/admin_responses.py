"""Typed O03/O04/O05/O09 HTTP responses; H3, API contract section 15.

Keep serialized timestamps as strings to preserve existing wire values. Optional
context fields are omitted with response_model_exclude_unset; explicit nulls stay.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

ReviewCheckKey = Literal["basic", "source", "geometry", "access_point", "time", "relation"]
ReviewTaskStatus = Literal[
    "draft", "ready_for_review", "in_review", "changes_requested", "approved", "closed"
]


class AdminResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReviewReadinessCheck(AdminResponse):
    key: Literal["basic", "source", "geometry", "access_point", "time", "relation"]
    collected: bool
    verified: bool
    total: int
    verified_count: int


class ReviewReadiness(AdminResponse):
    status: Literal[
        "needs_evidence",
        "ready_for_review",
        "under_review",
        "changes_requested",
        "ready_for_approval",
        "human_verified",
        "published",
        "retired",
    ]
    completed_checks: int
    verified_checks: int
    total_checks: int
    missing_checks: list[ReviewCheckKey]
    pending_review_checks: list[ReviewCheckKey]
    task_status: ReviewTaskStatus | None
    checks: list[ReviewReadinessCheck]


class PlaceRevision(AdminResponse):
    place_revision_id: str
    place_id: str
    revision_number: int
    revision_version: int
    lifecycle_status: Literal["candidate", "human_verified", "published", "retired"]
    canonical_name: str
    aliases: list[str]
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
    suitable_periods: list[str]
    audience_tags: list[str]
    rain_suitability: str
    is_always_open: bool
    solver_eligible: bool
    conflicts_resolved: bool
    source_record_ids: list[str]
    created_at: str
    reviewed_at: str | None
    published_at: str | None
    review_flags: list[str]
    relation_review_status: Literal["pending", "no_relations", "not_required"]
    review_readiness: ReviewReadiness | None = None


class PublicationCheck(AdminResponse):
    revision_id: str
    publishable: bool
    reason_codes: list[str]


class PlaceEvidenceSource(AdminResponse):
    source_record_id: str
    source_id: str
    source_url: str
    source_url_redacted: bool
    collection_mode: str
    target_stage: str
    source_decision: str
    observed_at: str
    status: str
    content_sha256: str | None
    attached_to_revision: bool


class PlaceGeometryEvidence(AdminResponse):
    geometry_id: str
    geometry_kind: str
    geometry: dict[str, Any]
    source_record_id: str
    source_record_valid: bool
    review_status: str
    active: bool
    created_at: str
    reviewed_at: str | None


class PlaceAccessPointEvidence(AdminResponse):
    access_point_id: str
    access_point_kind: str
    name: str
    lat: float
    lng: float
    source_record_id: str
    source_record_valid: bool
    review_status: str
    active: bool
    fetched_at: str | None
    reviewed_at: str | None
    created_at: str


class PlaceTimeRuleEvidence(AdminResponse):
    time_rule_id: str
    rule_kind: str
    weekdays: list[int]
    start_minute: int | None
    end_minute: int | None
    last_entry_minute: int | None
    valid_from: str | None
    valid_to: str | None
    source_record_id: str
    source_record_valid: bool
    review_status: str
    active: bool
    created_at: str
    reviewed_at: str | None


class PlaceClosureEvidence(AdminResponse):
    closure_id: str
    weekday: int
    source_record_id: str
    source_record_valid: bool
    review_status: str
    active: bool
    created_at: str
    reviewed_at: str | None


class PlaceDateExceptionEvidence(AdminResponse):
    date_exception_id: str
    service_date: str
    exception_kind: str
    start_minute: int | None
    end_minute: int | None
    last_entry_minute: int | None
    source_record_id: str
    source_record_valid: bool
    review_status: str
    active: bool
    created_at: str
    reviewed_at: str | None


class PlaceRelationEvidence(AdminResponse):
    relation_id: str
    from_place_id: str
    to_place_id: str
    from_place_name: str | None
    to_place_name: str | None
    relation_summary: str | None
    relation_type: str
    source_record_id: str
    source_record_valid: bool
    review_status: str
    resolution_status: str
    decision_note: str | None
    active: bool
    created_at: str
    reviewed_at: str | None


class PlaceProjectionEvidence(AdminResponse):
    projection_id: str
    projection_version: str
    data_snapshot_version: str
    solver_node_id: int
    place_kind: str
    geometry_kind: str
    arrival_access_point_id: str
    departure_access_point_id: str
    status: str
    projection_hash: str
    gate_reason_codes: list[str]
    created_at: str
    published_at: str | None


class PlaceRevisionEvidence(AdminResponse):
    revision: PlaceRevision
    sources: list[PlaceEvidenceSource]
    geometries: list[PlaceGeometryEvidence]
    access_points: list[PlaceAccessPointEvidence]
    time_rules: list[PlaceTimeRuleEvidence]
    closures: list[PlaceClosureEvidence]
    date_exceptions: list[PlaceDateExceptionEvidence]
    relations: list[PlaceRelationEvidence]
    projection: PlaceProjectionEvidence | None
    missing_source_record_ids: list[str]


class ReviewTask(AdminResponse):
    review_task_id: str
    place_revision_id: str
    status: ReviewTaskStatus
    assigned_reviewer_id: str | None
    version: int
    created_by: str
    created_at: str
    updated_at: str
    place_id: str | None = None
    revision_number: int | None = None
    canonical_name: str | None = None
    admin_area: str | None = None
    place_kind: str | None = None
    category: str | None = None


class PlaceRevisionPage(AdminResponse):
    items: list[PlaceRevision]
    limit: int
    offset: int
    total: int


class ReviewTaskPage(AdminResponse):
    items: list[ReviewTask]
    limit: int
    offset: int
    total: int


class TimeWindowPreview(AdminResponse):
    start_minute: int | None
    end_minute: int | None
    last_entry_minute: int | None


class RegularSessionPreview(TimeWindowPreview):
    time_rule_id: str


class OverrideSessionPreview(TimeWindowPreview):
    date_exception_id: str


class PlaceTimePreview(AdminResponse):
    revision_id: str
    service_date: str
    open: bool
    windows: list[TimeWindowPreview]
    fixed_sessions: list[RegularSessionPreview | OverrideSessionPreview]
    reason_codes: list[str]
    applied_exception_ids: list[str]
    rule_ids: list[str]
