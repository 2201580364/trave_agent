import { App as AntApp } from 'antd'
import { render, screen } from '@testing-library/react'

import { AdminSessionProvider, useAdminSession } from './AdminSessionProvider'

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
