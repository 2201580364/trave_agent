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

export type ApiErrorBody = {
  error?: {
    code?: string
    message?: string
    details?: Record<string, unknown>
    request_id?: string
  }
}
