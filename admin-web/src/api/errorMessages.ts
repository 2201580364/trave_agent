import { AdminApiError } from './adminApi'
import { reasonCodeLabel } from '../ui/displayLabels'

const ERROR_MESSAGES: Record<string, string> = {
  admin_authentication_required: '管理员会话无效或已过期，请重新登录。',
  admin_permission_denied: '当前管理员没有执行此操作的权限。',
  admin_operation_intent_conflict: '该操作标识已被用于不同内容，请关闭窗口后重新操作。',
  admin_login_name_conflict: '该登录名已存在，请使用其他登录名。',
  admin_actor_version_conflict: '管理员资料已被其他操作更新，请刷新列表后重试。',
  admin_role_safety_violation: '不能移除最后一个有效安全管理员的安全角色，请先建立恢复路径。',
  domain_validation_failed: '提交内容未通过安全或格式校验，请检查后重试。',
  projection_preparation_rejected: '求解投影暂不能准备，请先补齐证据。',
}

export function adminErrorMessage(error: unknown): string {
  if (error instanceof AdminApiError) {
    const reasonCodes = Array.isArray(error.details?.reason_codes)
      ? `（原因：${error.details.reason_codes.map((code) => reasonCodeLabel(String(code))).join('、')}）`
      : ''
    const baseMessage = error.code === 'publication_gate_rejected'
      ? '发布门禁未通过，请先补齐依赖证据。'
      : (ERROR_MESSAGES[error.code] ?? '操作未完成，请检查输入和当前状态。')
    const fieldErrors = error.fieldErrors && error.fieldErrors.length > 0
      ? `（字段：${error.fieldErrors.map((item) => {
        if (typeof item !== 'object' || item === null) return String(item)
        const field = 'field' in item ? String(item.field) : '未知字段'
        const detail = 'message' in item ? String(item.message) : '值无效'
        return `${field}：${detail}`
      }).join('；')}）`
      : ''
    const message = baseMessage + reasonCodes + fieldErrors
    return error.requestId ? `${message}（请求 ${error.requestId}）` : message
  }
  return '管理服务暂时不可用，请稍后重试。'
}
