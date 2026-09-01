import type {
  AdminActor,
  AdminActorFilters,
  AdminAuditEvent,
  AdminLoginResponse,
  AdminMe,
  ApiErrorBody,
  AuditEventFilters,
  CreateAdminActorInput,
  PageResponse,
  ReplaceAdminRolesInput,
  ReviewDecision,
  ReviewTask,
  ReviewTaskStatus,
  PlaceRevision,
  PlaceListFilters,
  PlaceRevisionEvidence,
  ReviewPlaceEvidenceInput,
  PlaceGeometryInput,
  PlaceAccessPointInput,
  PlaceClosureInput,
  PlaceDateExceptionInput,
  PlaceTimeRuleInput,
  RetirePlaceEvidenceInput,
  PublicationCheck,
  PlaceTimePreview,
  DashboardSummary,
  PublicationBatch,
  ResearchSnapshot,
  SourceConflictResponse,
} from './types'

const API_ROOT = '/api/v1/admin'

export class AdminApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly requestId?: string,
    readonly details?: Record<string, unknown>,
    readonly fieldErrors?: Array<{ field?: string; code?: string; message?: string }>,
  ) {
    super(message)
    this.name = 'AdminApiError'
  }
}

export class AdminApi {
  constructor(
    private readonly getAccessToken: () => string | null,
    private readonly onUnauthorized: () => void,
  ) {}

  createSession(loginName: string, password: string): Promise<AdminLoginResponse> {
    return this.request('/sessions', {
      method: 'POST',
      body: JSON.stringify({ login_name: loginName, password }),
      authenticated: false,
    })
  }

  revokeCurrentSession(): Promise<void> {
    return this.request('/sessions/current', { method: 'DELETE' })
  }

  getMe(): Promise<AdminMe> {
    return this.request('/me')
  }

  listAdminActors(
    limit = 100,
    offset = 0,
    filters: AdminActorFilters = {},
  ): Promise<PageResponse<AdminActor>> {
    const query = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== '') query.set(key, String(value))
    })
    return this.request(`/admin-actors?${query}`)
  }

  createAdminActor(input: CreateAdminActorInput): Promise<AdminActor> {
    return this.request('/admin-actors', {
      method: 'POST',
      body: JSON.stringify(input),
    })
  }

  replaceAdminRoles(actorId: string, input: ReplaceAdminRolesInput): Promise<AdminActor> {
    return this.request(`/admin-actors/${encodeURIComponent(actorId)}/roles`, {
      method: 'PUT',
      body: JSON.stringify(input),
    })
  }

  listAuditEvents(filters: AuditEventFilters): Promise<PageResponse<AdminAuditEvent>> {
    const query = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== '') query.set(key, String(value))
    })
    return this.request(`/audit-events?${query}`)
  }

  listReviewTasks(
    status?: ReviewTaskStatus,
    limit = 50,
    offset = 0,
    filters: PlaceListFilters = {},
  ): Promise<PageResponse<ReviewTask>> {
    const query = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (status !== undefined) query.set('review_status', status)
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== '') query.set(key, String(value))
    })
    return this.request(`/review-tasks?${query}`)
  }

  listCandidates(
    status = 'candidate',
    limit = 50,
    offset = 0,
    filters: PlaceListFilters = {},
  ): Promise<PageResponse<PlaceRevision>> {
    const query = new URLSearchParams({ lifecycle_status: status, limit: String(limit), offset: String(offset) })
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== '') query.set(key, String(value))
    })
    return this.request(`/candidates?${query}`)
  }

  getPlaceRevision(revisionId: string): Promise<PlaceRevision> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}`)
  }

  getPlaceRevisionEvidence(revisionId: string): Promise<PlaceRevisionEvidence> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/evidence`)
  }

  previewPlaceRevisionTime(revisionId: string, serviceDate: string): Promise<PlaceTimePreview> {
    const query = new URLSearchParams({ service_date: serviceDate })
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/time-preview?${query}`)
  }

  getDashboardSummary(): Promise<DashboardSummary> { return this.request('/dashboard-summary') }

  resolvePlaceRelation(revisionId: string, relationId: string, input: { expected_revision_version: number; resolution_status: string; decision_note?: string | null; operation_intent_id: string; reason_code: string }): Promise<PlaceRevision> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/relations/${encodeURIComponent(relationId)}/resolve`, { method: 'POST', body: JSON.stringify(input) })
  }

  confirmNoPlaceRelations(revisionId: string, input: { expected_revision_number: number; expected_revision_version: number; operation_intent_id: string; reason_code: string; reason_text?: string | null }): Promise<PlaceRevision> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/relations/confirm-none`, { method: 'POST', body: JSON.stringify(input) })
  }

  createGeometry(revisionId: string, input: PlaceGeometryInput): Promise<PlaceRevision> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/geometries`, {
      method: 'POST', body: JSON.stringify(input),
    })
  }

  updateGeometry(revisionId: string, geometryId: string, input: PlaceGeometryInput): Promise<PlaceRevision> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/geometries/${encodeURIComponent(geometryId)}`, {
      method: 'PATCH', body: JSON.stringify(input),
    })
  }

  retireGeometry(revisionId: string, geometryId: string, input: RetirePlaceEvidenceInput): Promise<PlaceRevision> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/geometries/${encodeURIComponent(geometryId)}`, {
      method: 'DELETE', body: JSON.stringify(input),
    })
  }

  createAccessPoint(revisionId: string, input: PlaceAccessPointInput): Promise<PlaceRevision> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/access-points`, {
      method: 'POST', body: JSON.stringify(input),
    })
  }

  updateAccessPoint(revisionId: string, accessPointId: string, input: PlaceAccessPointInput): Promise<PlaceRevision> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/access-points/${encodeURIComponent(accessPointId)}`, {
      method: 'PATCH', body: JSON.stringify(input),
    })
  }

  retireAccessPoint(revisionId: string, accessPointId: string, input: RetirePlaceEvidenceInput): Promise<PlaceRevision> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/access-points/${encodeURIComponent(accessPointId)}`, {
      method: 'DELETE', body: JSON.stringify(input),
    })
  }

  createTimeRule(revisionId: string, input: PlaceTimeRuleInput): Promise<PlaceRevision> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/time-rules`, {
      method: 'POST', body: JSON.stringify(input),
    })
  }

  updateTimeRule(revisionId: string, timeRuleId: string, input: PlaceTimeRuleInput): Promise<PlaceRevision> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/time-rules/${encodeURIComponent(timeRuleId)}`, {
      method: 'PATCH', body: JSON.stringify(input),
    })
  }

  retireTimeRule(revisionId: string, timeRuleId: string, input: RetirePlaceEvidenceInput): Promise<PlaceRevision> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/time-rules/${encodeURIComponent(timeRuleId)}`, {
      method: 'DELETE', body: JSON.stringify(input),
    })
  }

  createClosure(revisionId: string, input: PlaceClosureInput): Promise<PlaceRevision> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/closures`, {
      method: 'POST', body: JSON.stringify(input),
    })
  }

  updateClosure(revisionId: string, closureId: string, input: PlaceClosureInput): Promise<PlaceRevision> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/closures/${encodeURIComponent(closureId)}`, {
      method: 'PATCH', body: JSON.stringify(input),
    })
  }

  retireClosure(revisionId: string, closureId: string, input: RetirePlaceEvidenceInput): Promise<PlaceRevision> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/closures/${encodeURIComponent(closureId)}`, {
      method: 'DELETE', body: JSON.stringify(input),
    })
  }

  createDateException(revisionId: string, input: PlaceDateExceptionInput): Promise<PlaceRevision> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/date-exceptions`, {
      method: 'POST', body: JSON.stringify(input),
    })
  }

  updateDateException(revisionId: string, dateExceptionId: string, input: PlaceDateExceptionInput): Promise<PlaceRevision> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/date-exceptions/${encodeURIComponent(dateExceptionId)}`, {
      method: 'PATCH', body: JSON.stringify(input),
    })
  }

  retireDateException(revisionId: string, dateExceptionId: string, input: RetirePlaceEvidenceInput): Promise<PlaceRevision> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/date-exceptions/${encodeURIComponent(dateExceptionId)}`, {
      method: 'DELETE', body: JSON.stringify(input),
    })
  }
  reviewEvidence(revisionId: string, kind: string, id: string, input: ReviewPlaceEvidenceInput): Promise<PlaceRevision> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/evidence/${encodeURIComponent(kind)}/${encodeURIComponent(id)}/review`, { method: 'POST', body: JSON.stringify(input) })
  }

  createPlaceRevision(
    placeId: string,
    input: { base_revision_id: string; operation_intent_id: string; reason_code: string; reason_text?: string },
  ): Promise<PlaceRevision> {
    return this.request(`/places/${encodeURIComponent(placeId)}/revisions`, {
      method: 'POST',
      body: JSON.stringify(input),
    })
  }

  updatePlaceRevision(
    revisionId: string,
    input: Record<string, unknown>,
  ): Promise<PlaceRevision> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}`, {
      method: 'PATCH',
      body: JSON.stringify(input),
    })
  }

  submitPlaceReview(
    revisionId: string,
    input: { operation_intent_id: string; reason_code: string; reason_text?: string },
  ): Promise<ReviewTask> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/review-tasks`, {
      method: 'POST',
      body: JSON.stringify(input),
    })
  }

  checkPlaceRevisionPublication(revisionId: string): Promise<PublicationCheck> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/publication-checks`)
  }

  listSourceConflicts(revisionId: string): Promise<SourceConflictResponse> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/source-conflicts`)
  }

  resolveSourceConflicts(
    revisionId: string,
    input: {
      expected_revision_number: number
      expected_revision_version: number
      resolved: boolean
      operation_intent_id: string
      reason_code: string
      reason_text?: string
    },
  ): Promise<PlaceRevision> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/source-conflicts/resolve`, {
      method: 'POST',
      body: JSON.stringify(input),
    })
  }

  preparePlaceRevisionProjection(
    revisionId: string,
    input: { data_snapshot_version: string; solver_node_id?: number; operation_intent_id: string; reason_code: string; reason_text?: string },
  ): Promise<{ projection_id: string; place_revision_id: string; status: string; projection_hash: string; gate_reason_codes: string[] }> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/projection-preparations`, {
      method: 'POST',
      body: JSON.stringify(input),
    })
  }

  publishPlaceRevision(
    revisionId: string,
    input: { operation_intent_id: string; reason_code: string; reason_text?: string },
  ): Promise<Record<string, unknown>> {
    return this.request(`/place-revisions/${encodeURIComponent(revisionId)}/publications`, {
      method: 'POST',
      body: JSON.stringify(input),
    })
  }

  previewPublicationBatch(input: { city_id: string; place_revision_ids: string[]; operation_intent_id: string; reason_code: string; reason_text?: string }): Promise<PublicationBatch> {
    return this.request('/publication-batches/previews', { method: 'POST', body: JSON.stringify(input) })
  }

  executePublicationBatch(batchId: string, input: { operation_intent_id: string; reason_code: string; reason_text?: string }): Promise<{ batch: PublicationBatch; snapshot: ResearchSnapshot | null; reused: boolean }> {
    return this.request(`/publication-batches/${encodeURIComponent(batchId)}/execute`, { method: 'POST', body: JSON.stringify(input) })
  }

  listResearchSnapshots(cityId?: string, limit = 50, offset = 0): Promise<PageResponse<ResearchSnapshot>> {
    const query = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (cityId) query.set('city_id', cityId)
    return this.request(`/research-snapshots?${query}`)
  }

  getResearchSnapshot(snapshotId: string): Promise<ResearchSnapshot> {
    return this.request(`/research-snapshots/${encodeURIComponent(snapshotId)}`)
  }

  decidePlaceReview(
    taskId: string,
    input: {
      expected_version: number
      decision_kind: ReviewDecision['decision_kind']
      reason_code: string
      reason_text?: string
    },
  ): Promise<ReviewTask> {
    return this.request(`/review-tasks/${encodeURIComponent(taskId)}/decisions`, {
      method: 'POST',
      body: JSON.stringify({
        ...input,
        operation_intent_id: createOperationIntent('review-decide'),
      }),
    })
  }

  decidePlaceReviewBatch(items: Array<{ task_id: string; expected_version: number; decision_kind: ReviewDecision['decision_kind']; reason_code: string; reason_text?: string }>): Promise<{ total: number; succeeded: ReviewTask[]; failed: Array<{ task_id: string; error_code: string; message: string }> }> {
    return this.request('/review-tasks/batch-decisions', {
      method: 'POST',
      body: JSON.stringify({ items: items.map((item) => ({ ...item, operation_intent_id: createOperationIntent('review-batch') })) }),
    })
  }

  listReviewDecisions(taskId: string): Promise<{ items: ReviewDecision[] }> {
    return this.request(`/review-tasks/${encodeURIComponent(taskId)}/decisions`)
  }

  getReviewTask(taskId: string): Promise<ReviewTask> {
    return this.request(`/review-tasks/${encodeURIComponent(taskId)}`)
  }

  private async request<T>(
    path: string,
    init: RequestInit & { authenticated?: boolean } = {},
  ): Promise<T> {
    const { authenticated = true, ...requestInit } = init
    const headers = new Headers(requestInit.headers)
    if (requestInit.body !== undefined) headers.set('Content-Type', 'application/json')
    if (authenticated) {
      const token = this.getAccessToken()
      if (!token) {
        this.onUnauthorized()
        throw new AdminApiError(401, 'admin_authentication_required', '管理员会话不存在')
      }
      headers.set('Authorization', `Bearer ${token}`)
    }

    const response = await fetch(`${API_ROOT}${path}`, { ...requestInit, headers })
    if (response.ok) {
      if (response.status === 204) return undefined as T
      return (await response.json()) as T
    }

    let body: ApiErrorBody = {}
    try {
      body = (await response.json()) as ApiErrorBody
    } catch {
      // Keep the stable fallback below; never include an untrusted response body.
    }
    if (response.status === 401 && authenticated) this.onUnauthorized()
    const code = body.error?.code ?? 'admin_request_failed'
    throw new AdminApiError(
      response.status,
      code,
      body.error?.message ?? `管理请求失败（HTTP ${response.status}）`,
      body.error?.request_id ?? response.headers.get('X-Request-ID') ?? undefined,
      body.error?.details,
      body.error?.field_errors,
    )
  }
}

export function createOperationIntent(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`
}
