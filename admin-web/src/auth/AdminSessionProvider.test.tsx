import { App as AntApp } from 'antd'
import { render, screen } from '@testing-library/react'

import { AdminSessionProvider, useAdminSession } from './AdminSessionProvider'

const TOKEN_STORAGE_KEY = 'travel-agent-admin-session-token'

function TriggerApiError() {
  const { login } = useAdminSession()
  return (
    <button
      onClick={() => void login('reviewer', 'invalid-password').catch(() => undefined)}
    >
      触发接口错误
    </button>
  )
}

describe('AdminSessionProvider API error notification', () => {
  it('shows the backend business reason and request id for a standard error response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: {
            code: 'domain_validation_failed',
            message: '请先维护固定闭馆日，再生成节假日开放和顺延闭馆例外',
            request_id: 'req-holiday-policy',
            retryable: false,
            field_errors: [],
            details: {},
          },
        }),
        { status: 422, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    render(
      <AntApp>
        <AdminSessionProvider>
          <TriggerApiError />
        </AdminSessionProvider>
      </AntApp>,
    )
    screen.getByRole('button', { name: '触发接口错误' }).click()

    expect(await screen.findByText('操作受限')).toBeTruthy()
    expect(
      await screen.findByText(/请先维护固定闭馆日.*req-holiday-policy/),
    ).toBeTruthy()
  })
})

function PrincipalProbe() {
  const { principal } = useAdminSession()
  return <div data-testid="principal">{principal?.login_name ?? 'anonymous'}</div>
}

function LogoutProbe() {
  const { logout } = useAdminSession()
  return (
    <button onClick={() => void logout()}>
      退出登录
    </button>
  )
}

describe('AdminSessionProvider session persistence', () => {
  it('restores the principal from sessionStorage via /me on mount', async () => {
    sessionStorage.setItem(TOKEN_STORAGE_KEY, 'stored-token')
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          admin_actor_id: 'actor-1',
          login_name: 'reviewer',
          role_keys: ['data_reviewer'],
          permissions: ['admin:session:self'],
          admin_session_id: 'session-1',
          expires_at: new Date(Date.now() + 3_600_000).toISOString(),
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    render(
      <AntApp>
        <AdminSessionProvider>
          <PrincipalProbe />
        </AdminSessionProvider>
      </AntApp>,
    )

    expect((await screen.findByTestId('principal')).textContent).toBe('reviewer')
    expect(fetchSpy.mock.calls[0]?.[0]).toContain('/api/v1/admin/me')
    const init = fetchSpy.mock.calls[0]?.[1] as RequestInit | undefined
    const headers = init?.headers
    const authorization = headers instanceof Headers ? headers.get('Authorization') : null
    expect(authorization).toBe('Bearer stored-token')
  })

  it('clears the stored token when /me rejects a stale session', async () => {
    sessionStorage.setItem(TOKEN_STORAGE_KEY, 'stale-token')
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: { code: 'admin_authentication_required', message: '会话不存在' },
        }),
        { status: 401, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    render(
      <AntApp>
        <AdminSessionProvider>
          <PrincipalProbe />
        </AdminSessionProvider>
      </AntApp>,
    )

    expect((await screen.findByTestId('principal')).textContent).toBe('anonymous')
    expect(sessionStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull()
  })

  it('removes the stored token on logout', async () => {
    sessionStorage.setItem(TOKEN_STORAGE_KEY, 'active-token')
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            admin_actor_id: 'actor-1',
            login_name: 'reviewer',
            role_keys: ['data_reviewer'],
            permissions: ['admin:session:self'],
            admin_session_id: 'session-1',
            expires_at: new Date(Date.now() + 3_600_000).toISOString(),
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }))

    render(
      <AntApp>
        <AdminSessionProvider>
          <PrincipalProbe />
          <LogoutProbe />
        </AdminSessionProvider>
      </AntApp>,
    )

    await screen.findByTestId('principal')
    screen.getByRole('button', { name: '退出登录' }).click()

    expect((await screen.findByTestId('principal')).textContent).toBe('anonymous')
    expect(sessionStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull()
  })
})
