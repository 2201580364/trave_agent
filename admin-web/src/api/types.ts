export type AdminLoginResponse = {
  admin_actor_id: string
  access_token: string
  expires_at: string
  role_keys: string[]
  permissions: string[]
}

export type AdminMe = {
  admin_actor_id: string
  login_name: string
  role_keys: string[]
  permissions: string[]
  expires_at: string
}

export type AdminActorStatus = 'active' | 'disabled' | 'locked'

export type AdminActor = {
  admin_actor_id: string
  login_name: string
  status: AdminActorStatus
  version: number
  session_version: number
  role_keys: string[]
  created_at: string
  updated_at: string
  reused?: boolean
}

export type AdminAuditResult = 'succeeded' | 'rejected' | 'failed'

export type AdminAuditEvent = {
  audit_event_id: string
  actor_id: string
  actor_login_name: string | null
  actor_role: string
  action: string
  target_type: string
  target_id: string
  target_revision: string | null
  before_digest: string | null
  after_digest: string | null
  reason_code: string
  reason_text: string | null
  request_id: string
  operation_intent_id: string | null
  result: AdminAuditResult
  error_code: string | null
  occurred_at: string
}

export type PageResponse<T> = {
  items: T[]
  limit: number
  offset: number
  total?: number
}

export type CreateAdminActorInput = {
  operation_intent_id: string
  login_name: string
  initial_password: string
  role_keys: string[]
  reason_code: string
  reason_text?: string | null
}

export type ReplaceAdminRolesInput = {
  operation_intent_id: string
  expected_version: number
  role_keys: string[]
  reason_code: string
  reason_text?: string | null
}

export type AuditEventFilters = {
  keyword?: string
  actor_id?: string
  actor_login_name?: string
  target_type?: string
  target_id?: string
  action?: string
  result?: AdminAuditResult
  limit?: number
  offset?: number
}

export type ReviewTaskStatus =
  | 'draft'
  | 'ready_for_review'
  | 'in_review'
  | 'changes_requested'
  | 'approved'
  | 'closed'

export type ReviewTask = {
  review_task_id: string
  place_revision_id: string
  status: ReviewTaskStatus
  assigned_reviewer_id: string | null
  version: number
  created_by: string
  created_at: string
  updated_at: string
  place_id?: string
  revision_number?: number
  canonical_name?: string
  admin_area?: string
  place_kind?: string
  category?: string
}

export type PlaceListFilters = {
  keyword?: string
  admin_area?: string
  place_kind?: string
}

export type AdminActorFilters = {
  keyword?: string
  actor_status?: AdminActorStatus
  role_key?: string
}

export type ReviewDecision = {
  review_decision_id: string
  review_task_id: string
  place_revision_id: string
  actor_id: string
  actor_role: string
  decision_kind: 'approve' | 'request_changes' | 'cancel'
  reason_code: string
  reason_text: string | null
  created_at: string
}

export type PlaceRevision = {
  place_revision_id: string
  place_id: string
  revision_number: number
  revision_version: number
  lifecycle_status: 'candidate' | 'human_verified' | 'published' | 'retired'
  canonical_name: string
  aliases: string[]
  place_kind: string
  category: string
  admin_area: string
  address: string | null
  geometry_kind: string
  duration_min: number
  duration_recommended: number
  duration_max: number
  internal_travel_min: number
  energy_level: number
  indoor_outdoor: string
  suitable_periods: string[]
  audience_tags: string[]
  rain_suitability: string
  is_always_open: boolean
  solver_eligible: boolean
  conflicts_resolved: boolean
  source_record_ids: string[]
  created_at: string
  reviewed_at: string | null
  published_at: string | null
  review_flags: string[]
  relation_review_status?: 'pending' | 'no_relations' | 'not_required'
  review_readiness?: ReviewReadiness | null
}

export type ReviewReadinessCheck = {
  key: 'basic' | 'source' | 'geometry' | 'access_point' | 'time' | 'relation'
  collected: boolean
  verified: boolean
  total: number
  verified_count: number
}

export type ReviewReadiness = {
  status: 'needs_evidence' | 'ready_for_review' | 'under_review' | 'changes_requested' | 'ready_for_approval' | 'human_verified' | 'published' | 'retired'
  completed_checks: number
  verified_checks: number
  total_checks: number
  missing_checks: ReviewReadinessCheck['key'][]
  pending_review_checks: ReviewReadinessCheck['key'][]
  task_status: ReviewTaskStatus | null
  checks: ReviewReadinessCheck[]
}

export type PublicationCheck = {
  revision_id: string
  publishable: boolean
  reason_codes: string[]
}

export type SourceConflictRecord = {
  source_record_id: string
  source_url: string
  source_decision: string
  status: string
  observed_at: string
}

export type SourceConflict = {
  source_id: string
  resolved: boolean
  records: SourceConflictRecord[]
}

export type SourceConflictResponse = {
  revision_id: string
  items: SourceConflict[]
}

export type PublicationBatchItem = {
  batch_item_id: string
  place_revision_id: string
  status: 'pending' | 'publishable' | 'blocked' | 'published' | 'failed'
  reason_codes: string[]
  projection_id: string | null
  published_at: string | null
  canonical_name?: string
  admin_area?: string
  place_kind?: string
  category?: string
  revision_number?: number
}

export type PublicationBatch = {
  batch_id: string
  city_id: string
  operation_intent_id: string
  status: 'preview' | 'executing' | 'published' | 'partial_failed' | 'failed'
  snapshot_id: string | null
  created_at: string
  items: PublicationBatchItem[]
}

export type ResearchSnapshot = {
  snapshot_id: string
  data_snapshot_version: string
  city_id: string
  content_sha256: string
  source_batch_id: string
  created_at: string
  status: 'published'
  payload?: Record<string, unknown>
}

export type PlaceRevisionEvidence = {
  revision: PlaceRevision
  sources: PlaceEvidenceSource[]
  geometries: PlaceGeometryEvidence[]
  access_points: PlaceAccessPointEvidence[]
  time_rules: PlaceTimeRuleEvidence[]
  closures: PlaceClosureEvidence[]
  date_exceptions: PlaceDateExceptionEvidence[]
  relations?: PlaceRelationEvidence[]
  projection: PlaceProjectionEvidence | null
  missing_source_record_ids: string[]
}

export type PlaceRelationEvidence = {
  relation_id: string
  from_place_id: string
  to_place_id: string
  from_place_name?: string | null
  to_place_name?: string | null
  relation_summary?: string | null
  relation_type: string
  source_record_id: string
  source_record_valid: boolean
  review_status: string
  resolution_status: string
  decision_note: string | null
  active: boolean
  created_at: string
  reviewed_at: string | null
}

export type PlaceTimePreview = {
  revision_id: string
  service_date: string
  open: boolean
  windows: Array<{ start_minute: number | null; end_minute: number | null; last_entry_minute: number | null }>
  fixed_sessions: Array<{ time_rule_id: string; start_minute: number; end_minute: number; last_entry_minute: number | null }>
  reason_codes: string[]
  applied_exception_ids: string[]
  rule_ids: string[]
}

export type DashboardSummary = {
  revisions: { candidate: number; human_verified: number; published: number }
  review_tasks: Record<string, number>
  recent_ready_tasks: ReviewTask[]
}

export type PlaceTimeRuleEvidence = {
  time_rule_id: string
  rule_kind: string
  weekdays: number[]
  start_minute: number | null
  end_minute: number | null
  last_entry_minute: number | null
  valid_from: string | null
  valid_to: string | null
  source_record_id: string
  source_record_valid: boolean
  review_status: string
  active: boolean
  created_at: string
  reviewed_at: string | null
}

export type PlaceClosureEvidence = {
  closure_id: string
  weekday: number
  source_record_id: string
  source_record_valid: boolean
  review_status: string
  active: boolean
  created_at: string
  reviewed_at: string | null
}

export type PlaceDateExceptionEvidence = {
  date_exception_id: string
  service_date: string
  exception_kind: string
  start_minute: number | null
  end_minute: number | null
  last_entry_minute: number | null
  source_record_id: string
  source_record_valid: boolean
  review_status: string
  active: boolean
  created_at: string
  reviewed_at: string | null
}

export type PlaceGeometryInput = {
  expected_revision_version: number
  geometry_kind: string
  geometry: Record<string, unknown>
  source_record_id: string
  operation_intent_id: string
  reason_code: string
  reason_text?: string
}

export type PlaceAccessPointInput = {
  expected_revision_version: number
  access_point_kind: string
  name: string
  lat: number
  lng: number
  source_record_id: string
  fetched_at?: string | null
  operation_intent_id: string
  reason_code: string
  reason_text?: string
}

export type PlaceTimeRuleInput = {
  expected_revision_version: number
  rule_kind: 'opening_hours' | 'fixed_session' | 'last_entry'
  weekdays: number[]
  start_minute: number | null
  end_minute: number | null
  last_entry_minute: number | null
  valid_from: string | null
  valid_to: string | null
  source_record_id: string
  operation_intent_id: string
  reason_code: string
  reason_text?: string
}

export type PlaceClosureInput = {
  expected_revision_version: number
  weekday: number
  source_record_id: string
  operation_intent_id: string
  reason_code: string
  reason_text?: string
}

export type PlaceDateExceptionInput = {
  expected_revision_version: number
  service_date: string
  exception_kind: 'closed' | 'open_override' | 'session_override'
  start_minute: number | null
  end_minute: number | null
  last_entry_minute: number | null
  source_record_id: string
  operation_intent_id: string
  reason_code: string
  reason_text?: string
}

export type HolidayCalendar = {
  calendar_id: string
  display_name: string
  source_note: string
  source_record_id?: string | null
  periods: Array<{ name: string; start: string; end: string }>
}

export type HolidayCalendarSyncJob = {
  sync_job_id: string
  region_code: string
  year: number
  mode: 'preview' | 'sync'
  status: 'queued' | 'running' | 'not_announced' | 'temporarily_unavailable' | 'needs_attention' | 'validated_preview' | 'published' | 'up_to_date' | 'cancelled'
  source_url?: string | null
  source_title?: string | null
  validation_result: Record<string, unknown>
  calendar_id?: string | null
  attempt_count: number
  next_retry_at?: string | null
  created_by: string
  created_at: string
  started_at?: string | null
  finished_at?: string | null
}

export type HolidayCalendarVersion = {
  calendar_id: string
  region_code: string
  year: number
  version: number
  status: 'published' | 'superseded'
  display_name: string
  source_record_id: string
  source_content_sha256: string
  normalized_digest: string
  supersedes_calendar_id?: string | null
  published_at: string
  periods: Array<{ holiday_name: string; start_date: string; end_date: string; evidence_quote: string; display_order: number }>
  adjusted_workdays: Array<{ service_date: string; holiday_name: string; evidence_quote: string }>
}

export type HolidayCalendarImpact = {
  calendar_id: string
  compared_calendar_id?: string | null
  changed_date_count: number
  added_holiday_dates: string[]
  removed_holiday_dates: string[]
  added_adjusted_workdays: string[]
  removed_adjusted_workdays: string[]
  affected_places: Array<{ place_revision_id: string; place_name: string; admin_area: string; materialized_exception_count: number }>
  historical_rows_without_provenance_excluded: boolean
}

export type GenerateHolidayExceptionsInput = {
  expected_revision_version: number
  calendar_id: string
  source_record_id: string
  open_start_minute: number
  open_end_minute: number
  open_last_entry_minute: number | null
  shift_closure: boolean
  operation_intent_id: string
  reason_code: string
  reason_text?: string
}

export type RetirePlaceEvidenceInput = {
  expected_revision_version: number
  operation_intent_id: string
  reason_code: string
  reason_text?: string
}
export type ReviewPlaceEvidenceInput = { review_status: 'human_verified' | 'rejected'; operation_intent_id: string; reason_code: string; reason_text?: string }

export type SourceChannel = {
  source_id: string
  display_name: string
  source_kind: string
  decision: 'approved' | 'conditional'
  collection_modes: string[]
  base_urls: string[]
  conditions: string[]
}

export type CreatePlaceSourceRecordInput = {
  expected_revision_version: number
  source_id: string
  source_url: string
  collection_mode: string
  observed_at: string
  content_sha256?: string
  operation_intent_id: string
  reason_code: string
  reason_text?: string
}

export type PlaceEvidenceSource = {
  source_record_id: string
  source_id: string
  source_url: string
  source_url_redacted: boolean
  collection_mode: string
  target_stage: string
  source_decision: string
  observed_at: string
  status: string
  content_sha256?: string | null
  attached_to_revision?: boolean
}

export type PlaceGeometryEvidence = {
  geometry_id: string
  geometry_kind: string
  geometry: Record<string, unknown>
  source_record_id: string
  source_record_valid: boolean
  review_status: string
  active: boolean
  created_at: string
  reviewed_at: string | null
}

export type PlaceAccessPointEvidence = {
  access_point_id: string
  access_point_kind: string
  name: string
  lat: number
  lng: number
  source_record_id: string
  source_record_valid: boolean
  review_status: string
  active: boolean
  fetched_at: string | null
  reviewed_at: string | null
  created_at: string
}

export type PlaceProjectionEvidence = {
  projection_id: string
  projection_version: string
  data_snapshot_version: string
  solver_node_id: number
  place_kind: string
  geometry_kind: string
  arrival_access_point_id: string
  departure_access_point_id: string
  status: string
  projection_hash: string
  gate_reason_codes: string[]
  created_at: string
  published_at: string | null
}

export type ApiErrorBody = {
  error?: {
    code?: string
    message?: string
    details?: Record<string, unknown>
    field_errors?: Array<{ field?: string; code?: string; message?: string }>
    request_id?: string
  }
}
