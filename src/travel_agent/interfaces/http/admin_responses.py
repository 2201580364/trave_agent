"""Typed O03/O04/O05/O09 HTTP responses; H3, API contract section 15.

Keep serialized timestamps as strings to preserve existing wire values. Optional
context fields are omitted with response_model_exclude_unset; explicit nulls stay.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

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


# H3 / S8: remaining management response contracts.


class AdminLoginResponse(AdminResponse):
    admin_actor_id: str
    access_token: str
    expires_at: str
    role_keys: list[str]
    permissions: list[str]


class AdminMe(AdminResponse):
    admin_actor_id: str
    login_name: str
    role_keys: list[str]
    permissions: list[str]
    expires_at: str


AdminActorStatus = Literal["active"] | Literal["disabled"] | Literal["locked"]


class AdminActor(AdminResponse):
    admin_actor_id: str
    login_name: str
    status: AdminActorStatus
    version: int
    session_version: int
    role_keys: list[str]
    created_at: str
    updated_at: str
    reused: bool = False


AdminAuditResult = Literal["succeeded"] | Literal["rejected"] | Literal["failed"]


class AdminAuditEvent(AdminResponse):
    audit_event_id: str
    actor_id: str
    actor_login_name: str | None
    actor_role: str
    action: str
    target_type: str
    target_id: str
    target_revision: str | None
    before_digest: str | None
    after_digest: str | None
    reason_code: str
    reason_text: str | None
    request_id: str
    operation_intent_id: str | None
    result: AdminAuditResult
    error_code: str | None
    occurred_at: str


class ReviewDecision(AdminResponse):
    review_decision_id: str
    review_task_id: str
    place_revision_id: str
    actor_id: str
    actor_role: str
    decision_kind: Literal["approve"] | Literal["request_changes"] | Literal["cancel"]
    reason_code: str
    reason_text: str | None
    created_at: str


class SourceConflictRecord(AdminResponse):
    source_record_id: str
    source_url: str
    source_decision: str
    status: str
    observed_at: str


class SourceConflict(AdminResponse):
    source_id: str
    resolved: bool
    records: list[SourceConflictRecord]


class SourceConflictResponse(AdminResponse):
    revision_id: str
    items: list[SourceConflict]


class PublicationBatchItem(AdminResponse):
    batch_item_id: str
    place_revision_id: str
    status: (
        Literal["pending"]
        | Literal["publishable"]
        | Literal["blocked"]
        | Literal["published"]
        | Literal["failed"]
    )
    reason_codes: list[str]
    projection_id: str | None
    published_at: str | None
    canonical_name: str = ""
    admin_area: str = ""
    place_kind: str = ""
    category: str = ""
    revision_number: int = 0


class PublicationBatch(AdminResponse):
    batch_id: str
    city_id: str
    operation_intent_id: str
    status: (
        Literal["preview"]
        | Literal["executing"]
        | Literal["published"]
        | Literal["partial_failed"]
        | Literal["failed"]
    )
    snapshot_id: str | None
    created_at: str
    items: list[PublicationBatchItem]


class ResearchSnapshot(AdminResponse):
    snapshot_id: str
    data_snapshot_version: str
    city_id: str
    content_sha256: str
    source_batch_id: str
    created_at: str
    status: Literal["published"]
    payload: dict[str, Any] = Field(default_factory=dict)


class DashboardSummaryRevisions(AdminResponse):
    candidate: int
    human_verified: int
    published: int


class DashboardSummary(AdminResponse):
    revisions: DashboardSummaryRevisions
    review_tasks: dict[str, int]
    recent_ready_tasks: list[ReviewTask]


class HolidayCalendarPeriodsItem(AdminResponse):
    name: str
    start: str
    end: str


class HolidayCalendar(AdminResponse):
    calendar_id: str
    display_name: str
    source_note: str
    source_record_id: str | None = Field(default=None)
    periods: list[HolidayCalendarPeriodsItem]


class HolidayCalendarSyncJob(AdminResponse):
    source_published_at: str | None
    source_content_sha256: str | None
    sync_job_id: str
    region_code: str
    year: int
    mode: Literal["preview"] | Literal["sync"]
    status: (
        Literal["queued"]
        | Literal["running"]
        | Literal["not_announced"]
        | Literal["temporarily_unavailable"]
        | Literal["needs_attention"]
        | Literal["validated_preview"]
        | Literal["published"]
        | Literal["up_to_date"]
        | Literal["cancelled"]
    )
    source_url: str | None = Field(default=None)
    source_title: str | None = Field(default=None)
    validation_result: dict[str, Any]
    calendar_id: str | None = Field(default=None)
    attempt_count: int
    next_retry_at: str | None = Field(default=None)
    created_by: str
    created_at: str
    started_at: str | None = Field(default=None)
    finished_at: str | None = Field(default=None)


class HolidayCalendarVersionPeriodsItem(AdminResponse):
    holiday_name: str
    start_date: str
    end_date: str
    evidence_quote: str
    display_order: int


class HolidayCalendarVersionAdjustedWorkdaysItem(AdminResponse):
    service_date: str
    holiday_name: str
    evidence_quote: str


class HolidayCalendarVersion(AdminResponse):
    calendar_id: str
    region_code: str
    year: int
    version: int
    status: Literal["published"] | Literal["superseded"]
    display_name: str
    source_record_id: str
    source_content_sha256: str
    normalized_digest: str
    supersedes_calendar_id: str | None = Field(default=None)
    published_at: str
    periods: list[HolidayCalendarVersionPeriodsItem]
    adjusted_workdays: list[HolidayCalendarVersionAdjustedWorkdaysItem]


class HolidayCalendarImpactAffectedPlacesItem(AdminResponse):
    place_revision_id: str
    place_name: str
    admin_area: str
    materialized_exception_count: int


class HolidayCalendarImpact(AdminResponse):
    calendar_id: str
    compared_calendar_id: str | None = Field(default=None)
    changed_date_count: int
    added_holiday_dates: list[str]
    removed_holiday_dates: list[str]
    added_adjusted_workdays: list[str]
    removed_adjusted_workdays: list[str]
    affected_places: list[HolidayCalendarImpactAffectedPlacesItem]
    historical_rows_without_provenance_excluded: bool


class SourceChannel(AdminResponse):
    source_id: str
    display_name: str
    source_kind: str
    decision: Literal["approved"] | Literal["conditional"]
    collection_modes: list[str]
    base_urls: list[str]
    conditions: list[str]


class AdminActorPage(AdminResponse):
    items: list[AdminActor]
    limit: int
    offset: int
    total: int


class AdminAuditPage(AdminResponse):
    items: list[AdminAuditEvent]
    limit: int
    offset: int
    total: int


class SourceChannelList(AdminResponse):
    items: list[SourceChannel]


class HolidayCalendarList(AdminResponse):
    items: list[HolidayCalendar]


class HolidaySyncCapability(AdminResponse):
    execution_available: bool
    region_code: str


class HolidaySyncJobPage(AdminResponse):
    items: list[HolidayCalendarSyncJob]
    limit: int
    offset: int


class ReviewDecisionList(AdminResponse):
    items: list[ReviewDecision]


class BatchReviewFailure(AdminResponse):
    task_id: str | None
    error_code: str
    message: str


class BatchReviewResult(AdminResponse):
    total: int
    succeeded: list[ReviewTask]
    failed: list[BatchReviewFailure]


class PreparedProjection(AdminResponse):
    projection_id: str
    place_revision_id: str
    status: str
    projection_hash: str
    gate_reason_codes: list[str]


class PublishedProjection(AdminResponse):
    projection_id: str
    place_revision_id: str
    data_snapshot_version: str
    status: str
    published_at: str | None


class ResearchSnapshotPage(AdminResponse):
    items: list[ResearchSnapshot]
    limit: int
    offset: int


class PublicationBatchExecution(AdminResponse):
    batch: PublicationBatch
    snapshot: ResearchSnapshot | None
    reused: bool
