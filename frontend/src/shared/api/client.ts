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

// Per-code fallback copy; used when the server message does not carry
// user-facing Chinese text (contract: clients branch on `code`, §2.4).
const CODE_FALLBACKS: Record<string, string> = {
  draft_version_conflict: '草稿已在其他页面更新，请恢复最新版本后继续。',
  generation_intent_conflict: '该生成请求已被用于其他内容，请刷新页面后重试。',
  invalid_state_transition: '当前状态不允许执行该操作，请刷新页面后重试。',
  trip_revision_conflict: '行程已生成更新版本，请先恢复最新版本后再调整。',
  invalid_attraction_replacement: '暂时无法替换该景点，请刷新页面后重试。',
  draft_not_ready: '行程草稿还有未完成的条件，请先补齐后再生成。',
  plan_share_intent_conflict: '该分享标识已用于其他行程内容，请重新创建分享。',
  feedback_intent_conflict: '该反馈已提交过，请勿重复提交。',
  resource_not_found: '内容不存在或已失效。',
  data_gate_rejected: '当前数据暂无法用于生成，请稍后重试。',
  no_feasible_itinerary: '当前条件下没有可行的行程方案，请调整选择。',
  provider_unavailable: '外部服务暂时不可用，请稍后重试。',
  generation_temporarily_failed: '生成暂时失败，请稍后重试（原请求会继续保留）。',
  rate_limited: '请求过于频繁，请稍后再试。',
}

function hasChinese(text: string): boolean {
  return /[\u3400-\u9fff]/.test(text)
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
    const code = body?.error?.code ?? 'request_failed'
    const serverMessage = body?.error?.message ?? ''
    const message = serverMessage && hasChinese(serverMessage)
      ? serverMessage
      : CODE_FALLBACKS[code] ?? '请求失败，请稍后重试。'
    throw new ApiError(
      response.statusCode,
      code,
      message,
      body?.error?.details
    )
  }
  return response.data as T
}
