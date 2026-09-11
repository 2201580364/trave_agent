/**
 * API 手工类型（S8-3 过渡期边界说明）：
 *
 * - `api-schema.d.ts` 由 `npm run generate-api-types`（openapi-typescript）从
 *   `var/reports/openapi-schema.json`（后端 `scripts/export_openapi_schema.py`
 *   导出，CI 同链路）生成，是**请求体（Input）类型的权威来源**；
 * - 地点修订、证据、审核任务、准备度、时间预览及发布检查已使用后端响应模型，
 *   对应响应类型从生成文件再导出；认证、O17 等尚未迁移的响应仍暂留手工。
 * - 新增请求体类型：不要在本文件手写——直接使用
 *   `import type { components } from './api-schema'` 中的
 *   `components['schemas']['XxxInput']`；
 * - 本文件中已存在的 `*Input` 类型在过渡期保留（与生成类型双向兼容，S8-3
 *   已验证），待后端补 response_model 后整体迁往生成类型并删除。
 * - 后续每个响应能力域补齐 response_model 后：重跑 generate-api-types → 响应类型
 *   改从生成文件取 → 删除本文件对应手工类型。
 */
import type { components } from './api-schema'

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

/**
 * 生成类型再导出（S8-3 示范接线）：本体来自 api-schema.d.ts，
 * 后端 Pydantic 模型变更后重跑 `npm run generate-api-types` 即自动同步。
 */
export type CreateAdminActorInput =
  components['schemas']['CreateAdminActorInput']

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

export type ReviewTask = components['schemas']['ReviewTask']

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

export type PlaceRevision = components['schemas']['PlaceRevision']

export type ReviewReadinessCheck = components['schemas']['ReviewReadinessCheck']

export type ReviewReadiness = components['schemas']['ReviewReadiness']

export type PublicationCheck = components['schemas']['PublicationCheck']

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

export type PlaceRevisionEvidence = components['schemas']['PlaceRevisionEvidence']

export type PlaceRelationEvidence = components['schemas']['PlaceRelationEvidence']

export type PlaceTimePreview = components['schemas']['PlaceTimePreview']

export type DashboardSummary = {
  revisions: { candidate: number; human_verified: number; published: number }
  review_tasks: Record<string, number>
  recent_ready_tasks: ReviewTask[]
}

export type PlaceTimeRuleEvidence = components['schemas']['PlaceTimeRuleEvidence']

export type PlaceClosureEvidence = components['schemas']['PlaceClosureEvidence']

export type PlaceDateExceptionEvidence = components['schemas']['PlaceDateExceptionEvidence']

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

export type PlaceEvidenceSource = components['schemas']['PlaceEvidenceSource']

export type PlaceGeometryEvidence = components['schemas']['PlaceGeometryEvidence']

export type PlaceAccessPointEvidence = components['schemas']['PlaceAccessPointEvidence']

export type PlaceProjectionEvidence = components['schemas']['PlaceProjectionEvidence']

export type ApiErrorBody = {
  error?: {
    code?: string
    message?: string
    details?: Record<string, unknown>
    field_errors?: Array<{ field?: string; code?: string; message?: string }>
    request_id?: string
  }
}

export type PlaceRevisionPage = components['schemas']['PlaceRevisionPage']
export type ReviewTaskPage = components['schemas']['ReviewTaskPage']
