import { AdminApiError } from './adminApi'
import { reasonCodeLabel } from '../ui/displayLabels'

/**
 * Unified error rendering pipeline.
 *
 * Contract (api-contract.md §2.4): clients branch on `code`, never on
 * `message`. The backend already produces complete Chinese `message` copy
 * (centralized in `application/admin/error_messages.py`); this module only
 * adds legacy fallbacks for codes that may still arrive with non-Chinese
 * messages, plus structured `details` rendering.
 */

// Fallback copy for codes that may still surface with English messages from
// older deployments; server copy wins whenever it already carries Chinese.
const CODE_FALLBACKS: Record<string, string> = {
  admin_authentication_required: '管理员会话无效或已过期，请重新登录。',
  admin_permission_denied: '当前管理员没有执行此操作的权限。',
  admin_operation_intent_conflict: '该操作标识已被用于不同内容，请关闭窗口后重新操作。',
  admin_login_name_conflict: '该登录名已存在，请使用其他登录名。',
  admin_actor_version_conflict: '管理员资料已被其他操作更新，请刷新列表后重试。',
  admin_role_safety_violation: '不能移除最后一个有效安全管理员的安全角色，请先建立恢复路径。',
  admin_network_error: '无法连接管理服务，请检查网络或服务状态。',
  domain_validation_failed: '提交内容未通过安全或格式校验，请检查后重试。',
  projection_preparation_rejected: '求解投影暂不能准备，请先补齐证据。',
  source_record_validation_failed: '来源记录未通过治理校验，请检查来源渠道、地址和采集方式。',
  source_record_in_use: '当前来源仍被地点证据引用，请先把相关证据改用其他来源。',
  review_revision_not_approvable: '审核准备度未全部通过，无法审核通过。',
  publication_gate_rejected: '发布门禁未通过，请先补齐依赖证据。',
}

const READINESS_CHECK_LABELS: Record<string, string> = {
  basic: '基础事实（名称/分类/游览时长，需在详情页编辑并保存一次）',
  source: '来源记录（需当前有效且冲突已裁决）',
  geometry: '几何证据（O04 地图形状）',
  access_point: '访问点证据（O04 进出端点）',
  time: '开放时间证据（O05 周规则/闭馆日/日期例外）',
  relation: '地点关系检查（O07 裁决与核验）',
}

function hasChinese(text: string): boolean {
  return /[\u3400-\u9fff]/.test(text)
}

function readinessCheckSummary(details: Record<string, unknown> | undefined): string {
  if (!details) return ''
  const missing = Array.isArray(details.missing_checks) ? details.missing_checks.map(String) : []
  const pending = Array.isArray(details.pending_review_checks)
    ? details.pending_review_checks.map(String)
    : []
  const parts: string[] = []
  if (missing.length > 0) {
    parts.push(`证据未采集齐：${missing.map((key) => READINESS_CHECK_LABELS[key] ?? key).join('；')}`)
  }
  if (pending.length > 0) {
    parts.push(`已采集但未逐条人工核验：${pending.map((key) => READINESS_CHECK_LABELS[key] ?? key).join('；')}`)
  }
  if (details.not_candidate === true) {
    parts.push('当前修订版本已不是候选状态（可能已被编辑更新），请刷新页面后重新送审。')
  }
  if (parts.length === 0) return ''
  return `（未通过的审核准备项：${parts.join('。')}。）`
}

function detailSummary(error: AdminApiError): string {
  if (error.code === 'review_revision_not_approvable') return readinessCheckSummary(error.details)
  const reasonCodes = Array.isArray(error.details?.reason_codes)
    ? `（原因：${error.details.reason_codes.map((code) => reasonCodeLabel(String(code))).join('、')}）`
    : ''
  const references = error.code === 'source_record_in_use' && Array.isArray(error.details?.references)
    ? `（仍在使用：${error.details.references.map(String).join('、')}）`
    : ''
  return reasonCodes + references
}

export function adminErrorMessage(error: unknown): string {
  if (error instanceof AdminApiError) {
    const summary = detailSummary(error)
    const serverMessage = error.message
    // Server copy is authoritative when it already carries Chinese user text;
    // otherwise fall back per code, then to a generic safe default.
    const baseMessage = hasChinese(serverMessage) && !summary.includes(serverMessage)
      ? serverMessage
      : CODE_FALLBACKS[error.code] ?? (hasChinese(serverMessage) ? serverMessage : '操作未完成，请检查输入和当前状态。')
    const fieldErrors = error.fieldErrors && error.fieldErrors.length > 0
      ? `（字段：${error.fieldErrors.map((item) => {
        if (typeof item !== 'object' || item === null) return String(item)
        const field = 'field' in item ? String(item.field) : '未知字段'
        const detail = 'message' in item ? String(item.message) : '值无效'
        return `${field}：${detail}`
      }).join('；')}）`
      : ''
    const message = baseMessage + summary + fieldErrors
    return error.requestId ? `${message}（请求 ${error.requestId}）` : message
  }
  return '管理服务暂时不可用，请稍后重试。'
}
