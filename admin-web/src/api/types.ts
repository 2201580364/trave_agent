/**
 * API 类型（S8-3）：
 *
 * - `api-schema.d.ts` 由 `npm run generate-api-types`（openapi-typescript）从
 *   `var/reports/openapi-schema.json`（后端 `scripts/export_openapi_schema.py`
 *   导出，CI 同链路）生成，是请求体和管理响应模型的权威来源；
 * - 管理响应类型统一从生成文件再导出；动态快照载荷保持版本化结构。
 * - 新增请求体类型：不要在本文件手写——直接使用
 *   `import type { components } from './api-schema'` 中的
 *   `components['schemas']['XxxInput']`；
 * - 现有页面表单 Input 适配类型和筛选条件保留；新增响应类型必须从生成文件取。
 */
import type { components } from './api-schema'

export type AdminLoginResponse = components['schemas']['AdminLoginResponse']

export type AdminMe = components['schemas']['AdminMe']

export type AdminActorStatus = components['schemas']['AdminActor']['status']

export type AdminActor = components['schemas']['AdminActor']

export type AdminAuditResult = components['schemas']['AdminAuditEvent']['result']

export type AdminAuditEvent = components['schemas']['AdminAuditEvent']

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

export type ReviewDecision = components['schemas']['ReviewDecision']

export type PlaceRevision = components['schemas']['PlaceRevision']

export type ReviewReadinessCheck = components['schemas']['ReviewReadinessCheck']

export type ReviewReadiness = components['schemas']['ReviewReadiness']

export type PublicationCheck = components['schemas']['PublicationCheck']

export type SourceConflictRecord = components['schemas']['SourceConflictRecord']

export type SourceConflict = components['schemas']['SourceConflict']

export type SourceConflictResponse = components['schemas']['SourceConflictResponse']

export type PublicationBatchItem = components['schemas']['PublicationBatchItem']

export type PublicationBatch = components['schemas']['PublicationBatch']

export type ResearchSnapshot = components['schemas']['ResearchSnapshot']

export type PlaceRevisionEvidence = components['schemas']['PlaceRevisionEvidence']

export type PlaceRelationEvidence = components['schemas']['PlaceRelationEvidence']

export type PlaceTimePreview = components['schemas']['PlaceTimePreview']

export type DashboardSummary = components['schemas']['DashboardSummary']

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

export type HolidayCalendar = components['schemas']['HolidayCalendar']

export type HolidayCalendarSyncJob = components['schemas']['HolidayCalendarSyncJob']

export type HolidayCalendarVersion = components['schemas']['HolidayCalendarVersion']

export type HolidayCalendarImpact = components['schemas']['HolidayCalendarImpact']

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

export type SourceChannel = components['schemas']['SourceChannel']

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
