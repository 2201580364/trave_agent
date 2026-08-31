const labels: Record<string, string> = {
  // lifecycle and workflow
  candidate: '候选',
  human_verified: '人工已核验',
  published: '已发布',
  retired: '已退役',
  draft: '草稿',
  ready_for_review: '待审核',
  in_review: '审核中',
  changes_requested: '待修改',
  approved: '已通过',
  approve: '通过',
  request_changes: '退回修改',
  cancel: '已关闭',
  closed: '已关闭',
  rejected: '已驳回',
  pending: '待处理',
  resolved: '已裁决',
  not_required: '无需裁决',
  active: '生效',
  inactive: '未生效',
  merged: '已合并',
  // place and geometry
  attraction: '景点',
  scenic_area: '景区',
  neighborhood: '街区',
  walking_route: '步行路线',
  market: '市集',
  show: '演出/固定场次',
  experience: '体验',
  point: '点',
  area: '区域',
  route: '路线',
  visitor_entrance: '游客入口',
  visitor_exit: '游客出口',
  route_start: '路线起点',
  route_end: '路线终点',
  performance_location: '演出地点',
  meeting_point: '集合点',
  area_representative: '区域代表点',
  // source, time, relation and suitability
  conditional: '有条件通过',
  opening_hours: '开放时间',
  fixed_session: '固定场次',
  last_entry: '最晚入园',
  open_override: '临时开放',
  session_override: '场次覆盖',
  morning: '上午',
  afternoon: '下午',
  evening: '晚上',
  indoor: '室内',
  outdoor: '室外',
  mixed: '室内外兼有',
  suitable: '适合',
  unsuitable: '不适合',
  contains: '包含',
  part_of: '属于',
  overlaps: '重叠',
  same_experience: '同一体验',
  publishable: '可发布',
  blocked: '已阻断',
  failed: '失败',
  executing: '执行中',
  partial_failed: '部分失败',
  succeeded: '成功',
  preview: '待执行',
  like: '满意',
  dislike: '不满意',
  reasonable: '合理',
  neutral: '一般',
  unreasonable: '不合理',
}

const reasonLabels: Record<string, string> = {
  MISSING_VERIFIED_ACCESS_POINT: '缺少已核验的访问点',
  PROJECTION_NOT_FOUND: '尚未准备求解投影',
  PROJECTION_ALREADY_EXISTS: '求解投影已存在',
  DURATION_NOT_COLLECTED: '建议时长尚未采集',
  MISSING_VERIFIED_GEOMETRY: '缺少已核验的地点几何',
  MISSING_VERIFIED_TIME_RULE: '缺少已核验的开放时间规则',
  SOURCE_RECORD_INVALID: '来源记录无效',
  REVISION_NOT_HUMAN_VERIFIED: '修订版本尚未完成人工核验',
  PLACE_NOT_ACTIVE: '地点当前未生效',
  READY_FOR_REVIEW: '已准备审核',
  PLACE_FACTS_EDITED: '地点事实已编辑',
  PLACE_FACTS_REFRESH: '刷新地点事实',
  EVIDENCE_APPROVED: '证据已通过核验',
  EVIDENCE_REJECTED: '证据已驳回',
  PUBLICATION_APPROVED: '发布已批准',
}

function label(value: string | null | undefined, fallback = '未识别') {
  if (!value) return fallback
  return labels[value] ?? fallback
}

export function lifecycleStatusLabel(value: string | null | undefined) { return label(value) }
export function placeKindLabel(value: string | null | undefined) { return label(value) }
export function geometryKindLabel(value: string | null | undefined) { return label(value) }
export function accessPointKindLabel(value: string | null | undefined) { return label(value) }
export function reviewStatusLabel(value: string | null | undefined) { return label(value) }
export function sourceDecisionLabel(value: string | null | undefined) { return label(value) }
export function relationTypeLabel(value: string | null | undefined) { return label(value) }
export function relationResolutionLabel(value: string | null | undefined) { return label(value) }
export function timeRuleKindLabel(value: string | null | undefined) { return label(value) }
export function dateExceptionKindLabel(value: string | null | undefined) { return label(value) }
export function indoorOutdoorLabel(value: string | null | undefined) { return label(value) }
export function rainSuitabilityLabel(value: string | null | undefined) { return label(value) }
export function projectionStatusLabel(value: string | null | undefined) { return label(value) }
export function workflowReasonLabel(value: string | null | undefined) { return reasonLabels[value ?? ''] ?? '管理操作' }

export function auditTargetTypeLabel(value: string | null | undefined) {
  const targetLabels: Record<string, string> = {
    place: '地点',
    place_revision: '地点修订版本',
    place_geometry: '地点几何',
    place_access_point: '地点访问点',
    place_time_rule: '地点时间规则',
    place_closure: '地点闭馆规则',
    place_date_exception: '地点日期例外',
    place_relation: '地点关系',
    review_task: '审核任务',
    admin_actor: '管理员账号',
    publication_batch: '发布批次',
    research_snapshot: '研究快照',
  }
  return targetLabels[value ?? ''] ?? '管理对象'
}

export function reasonCodeLabel(value: string | null | undefined) {
  if (!value) return '无'
  return reasonLabels[value] ?? '其他原因'
}
