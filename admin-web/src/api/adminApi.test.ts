import { AdminApi } from './adminApi'

describe('AdminApi', () => {
  it('only adds the in-memory bearer token to authenticated requests', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify({ items: [], limit: 100, offset: 0 }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    const api = new AdminApi(() => 'memory-only-token', vi.fn())

    await api.listAdminActors()

    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers)
    expect(headers.get('Authorization')).toBe('Bearer memory-only-token')
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })

  it('does not send authorization credentials to the login endpoint', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          admin_actor_id: 'admin-1',
          access_token: 'new-token',
          expires_at: '2026-08-29T20:00:00Z',
          role_keys: ['admin_security'],
          permissions: ['admin:actor:read'],
        }),
        { status: 201, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    const api = new AdminApi(() => 'old-token', vi.fn())

    await api.createSession('root.admin', 'Password-Long-Enough-2026!')

    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers)
    expect(headers.has('Authorization')).toBe(false)
  })

  it('clears the session boundary and exposes the stable error code on 401', async () => {
    const onUnauthorized = vi.fn()
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: {
            code: 'admin_authentication_required',
            message: 'authentication required',
            request_id: 'req-expired',
          },
        }),
        { status: 401, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    const api = new AdminApi(() => 'expired-token', onUnauthorized)

    await expect(api.getMe()).rejects.toMatchObject({
      status: 401,
      code: 'admin_authentication_required',
      requestId: 'req-expired',
    })
    expect(onUnauthorized).toHaveBeenCalledOnce()
  })
})
