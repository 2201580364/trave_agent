import Taro from '@tarojs/taro'

export interface ApiErrorBody {
  error?: { code?: string; message?: string; details?: Record<string, unknown> }
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details: Record<string, unknown> = {}
  ) {
    super(message)
  }
}

export async function apiRequest<T>(
  path: string,
  options: {
    method?: 'GET' | 'POST' | 'PATCH' | 'PUT'
    token?: string
    data?: unknown
  } = {}
): Promise<T> {
  let response
  try {
    response = await Taro.request<T & ApiErrorBody>({
      url: path,
      method: options.method ?? 'GET',
      data: options.data,
      header: {
        'Content-Type': 'application/json',
        ...(options.token ? { Authorization: `Bearer ${options.token}` } : {})
      }
    })
  } catch {
    throw new ApiError(
      0,
      'network_unavailable',
      '网络暂时不可用，请检查连接后重试。'
    )
  }
  if (response.statusCode >= 400) {
    const body = response.data as ApiErrorBody | null
    throw new ApiError(
      response.statusCode,
      body?.error?.code ?? 'request_failed',
      body?.error?.message ?? '请求失败，请稍后重试。',
      body?.error?.details
    )
  }
  return response.data as T
}
