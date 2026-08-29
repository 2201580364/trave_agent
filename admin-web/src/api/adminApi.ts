import type {
  AdminActor,
  AdminAuditEvent,
  AdminLoginResponse,
  AdminMe,
  ApiErrorBody,
  AuditEventFilters,
  CreateAdminActorInput,
  PageResponse,
  ReplaceAdminRolesInput,
} from './types'

const API_ROOT = '/api/v1/admin'

export class AdminApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly requestId?: string,
    readonly details?: Record<string, unknown>,
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

  listAdminActors(limit = 100, offset = 0): Promise<PageResponse<AdminActor>> {
    const query = new URLSearchParams({ limit: String(limit), offset: String(offset) })
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
    )
  }
}

export function createOperationIntent(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`
}
