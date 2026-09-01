import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'

import type { AdminAuditEvent } from '../api/types'
import { AuditEventsPage } from './AuditEventsPage'

const mocks = vi.hoisted(() => ({
  api: { listAuditEvents: vi.fn() },
}))

vi.mock('../auth/AdminSessionProvider', () => ({
  useAdminSession: () => ({ api: mocks.api }),
}))

const event: AdminAuditEvent = {
  audit_event_id: 'audit-1',
  actor_id: 'admin_actor_internal_1',
  actor_login_name: 'local.admin',
  actor_role: 'admin_security',
  action: 'ADMIN_SESSION_CREATE',
  target_type: 'admin_actor',
  target_id: 'admin_actor_internal_1',
  target_revision: null,
  before_digest: null,
  after_digest: 'abcdef0123456789abcdef0123456789',
  reason_code: 'ADMIN_LOGIN_SUCCEEDED',
  reason_text: '管理员登录成功',
  request_id: 'req-1',
  operation_intent_id: null,
  result: 'succeeded',
  error_code: null,
  occurred_at: '2026-09-01T08:00:00Z',
}

describe('AuditEventsPage business-readable audit trail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.api.listAuditEvents.mockResolvedValue({
      items: [event],
      total: 1,
      limit: 50,
      offset: 0,
    })
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false, media: query, onchange: null,
        addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(),
        removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
      })),
    })
  })

  it('shows the operator account and Chinese action while keeping codes in trace details', async () => {
    render(<MemoryRouter><AuditEventsPage /></MemoryRouter>)

    await waitFor(() => expect(screen.getByText('local.admin')).toBeTruthy())
    expect(screen.getByText('管理员登录')).toBeTruthy()
    expect(screen.queryByText('admin_actor_internal_1')).toBeNull()
    expect(screen.queryByText('ADMIN_SESSION_CREATE')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Expand row' }))
    const details = screen.getByText('操作者内部编号').closest('.ant-descriptions')
    expect(details).not.toBeNull()
    expect(within(details as HTMLElement).getByText('admin_actor_internal_1')).toBeTruthy()
    expect(within(details as HTMLElement).getByText('ADMIN_SESSION_CREATE')).toBeTruthy()
    expect(within(details as HTMLElement).getByText('安全管理员')).toBeTruthy()
  })

  it('queries by login account and sends the stable action code selected by its Chinese label', async () => {
    render(<MemoryRouter><AuditEventsPage /></MemoryRouter>)
    await waitFor(() => expect(mocks.api.listAuditEvents).toHaveBeenCalledTimes(1))

    fireEvent.change(screen.getByLabelText('操作者账号'), { target: { value: 'local.admin' } })
    const actionSelect = screen.getByLabelText('动作')
    fireEvent.mouseDown(actionSelect)
    fireEvent.change(actionSelect, { target: { value: '管理员登录' } })
    const actionOption = (await screen.findAllByText('管理员登录')).find((node) =>
      node.closest('.ant-select-item-option'),
    )
    expect(actionOption).toBeTruthy()
    fireEvent.click(actionOption!.closest('.ant-select-item-option') as HTMLElement)
    fireEvent.click(screen.getByRole('button', { name: /查询/ }))

    await waitFor(() => {
      expect(mocks.api.listAuditEvents).toHaveBeenLastCalledWith(expect.objectContaining({
        actor_login_name: 'local.admin',
        action: 'ADMIN_SESSION_CREATE',
      }))
    })
  })

  it('does not expose an unknown machine action code in the main table', async () => {
    mocks.api.listAuditEvents.mockResolvedValue({
      items: [{ ...event, audit_event_id: 'audit-unknown', action: 'FUTURE_INTERNAL_ACTION' }],
      total: 1,
      limit: 50,
      offset: 0,
    })
    render(<MemoryRouter><AuditEventsPage /></MemoryRouter>)

    await waitFor(() => expect(screen.getByText('其他管理操作')).toBeTruthy())
    expect(screen.queryByText('FUTURE_INTERNAL_ACTION')).toBeNull()
  })
})
