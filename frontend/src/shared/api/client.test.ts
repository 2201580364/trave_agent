/**
 * S8-1 tests for the shared API client (shared/api/client.ts).
 *
 * apiRequest is the single request path used by every page. Taro.request is
 * mocked so we can assert the error mapping contract (network failure, HTTP
 * error envelope, success pass-through) without a Taro runtime.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

const taroRequest = vi.fn()

vi.mock('@tarojs/taro', () => ({
  default: {
    request: (...args: unknown[]) => taroRequest(...args)
  }
}))

import { ApiError, apiRequest } from './client'

afterEach(() => {
  taroRequest.mockReset()
})

describe('apiRequest success path', () => {
  it('returns the response data and sends GET by default', async () => {
    taroRequest.mockResolvedValue({ statusCode: 200, data: { ok: 1 } })

    const result = await apiRequest<{ ok: number }>('/api/v1/things')

    expect(result).toEqual({ ok: 1 })
    expect(taroRequest).toHaveBeenCalledTimes(1)
    const call = taroRequest.mock.calls[0][0] as {
      url: string
      method: string
      header: Record<string, string>
    }
    expect(call.url).toBe('/api/v1/things')
    expect(call.method).toBe('GET')
    expect(call.header['Content-Type']).toBe('application/json')
    expect(call.header.Authorization).toBeUndefined()
  })

  it('sends Bearer auth header when a token is given', async () => {
    taroRequest.mockResolvedValue({ statusCode: 200, data: {} })

    await apiRequest('/api/v1/me', { method: 'POST', token: 'tok-1', data: { a: 1 } })

    const call = taroRequest.mock.calls[0][0] as {
      method: string
      data: unknown
      header: Record<string, string>
    }
    expect(call.method).toBe('POST')
    expect(call.data).toEqual({ a: 1 })
    expect(call.header.Authorization).toBe('Bearer tok-1')
  })
})

describe('apiRequest error mapping', () => {
  it('maps a transport failure to network_unavailable with status 0', async () => {
    taroRequest.mockRejectedValue(new Error('socket hang up'))

    const error = await apiRequest('/api/v1/x').catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(0)
    expect((error as ApiError).code).toBe('network_unavailable')
  })

  it('maps an HTTP error envelope to ApiError with code and details', async () => {
    taroRequest.mockResolvedValue({
      statusCode: 409,
      data: {
        error: {
          code: 'draft_version_conflict',
          message: '草稿版本已过期',
          details: { expected: 3, actual: 4 }
        }
      }
    })

    const error = await apiRequest('/api/v1/x').catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    const apiError = error as ApiError
    expect(apiError.status).toBe(409)
    expect(apiError.code).toBe('draft_version_conflict')
    expect(apiError.message).toBe('草稿版本已过期')
    expect(apiError.details).toEqual({ expected: 3, actual: 4 })
  })

  it('falls back to a generic code when the error body has no envelope', async () => {
    taroRequest.mockResolvedValue({ statusCode: 500, data: null })

    const error = await apiRequest('/api/v1/x').catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(500)
    expect((error as ApiError).code).toBe('request_failed')
  })

  it('does not throw for 2xx statuses', async () => {
    taroRequest.mockResolvedValue({ statusCode: 201, data: { created: true } })

    const result = await apiRequest('/api/v1/x', { method: 'POST' })

    expect(result).toEqual({ created: true })
  })
})
