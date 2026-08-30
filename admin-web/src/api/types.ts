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
  actor_id?: string
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
}

export type PublicationCheck = {
  revision_id: string
  publishable: boolean
  reason_codes: string[]
}

export type PlaceRevisionEvidence = {
  revision: PlaceRevision
  sources: PlaceEvidenceSource[]
  geometries: PlaceGeometryEvidence[]
  access_points: PlaceAccessPointEvidence[]
  projection: PlaceProjectionEvidence | null
  missing_source_record_ids: string[]
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
    request_id?: string
  }
}
