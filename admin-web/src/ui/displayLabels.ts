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
  PROJECTION_NOT_FOUND: '尚未准备求解投影',
  PROJECTION_DEPENDENCY_MISSING: '求解投影依赖数据缺失',
  PROJECTION_ALREADY_EXISTS: '求解投影已存在',
  DURATION_NOT_COLLECTED: '建议时长尚未采集',
  MISSING_VERIFIED_GEOMETRY: '缺少已核验的地点几何',
  MISSING_VERIFIED_TIME_RULE: '缺少已核验的开放时间规则',
  SOURCE_RECORD_INVALID: '来源记录无效',
  MISSING_SOURCE_RECORD: '缺少来源记录',
  REVISION_NOT_HUMAN_VERIFIED: '修订版本尚未完成人工核验',
  PLACE_NOT_ACTIVE: '地点当前未生效',
  READY_FOR_REVIEW: '已准备审核',
  PLACE_FACTS_EDITED: '地点事实已编辑',
  PLACE_FACTS_REFRESH: '刷新地点事实',
  EVIDENCE_APPROVED: '证据已通过核验',
  EVIDENCE_REJECTED: '证据已驳回',
  PUBLICATION_APPROVED: '发布已批准',
  MISSING_VERIFIED_ACCESS_POINT: '缺少已核验的访问点',
  MISSING_ARRIVAL_ACCESS_POINT: '缺少到达访问点',
  MISSING_DEPARTURE_ACCESS_POINT: '缺少离开访问点',
  ACCESS_POINT_NOT_HUMAN_VERIFIED: '访问点尚未人工核验',
  ACCESS_POINT_REVISION_MISMATCH: '访问点不属于当前修订版本',
  TIME_RULE_UNRESOLVED: '开放时间尚未核验',
  FIXED_SESSION_AMBIGUOUS: '固定场次不明确',
  FIXED_SESSION_REQUIRED: '演出地点需要固定场次规则',
  SOURCE_CONFLICT_UNRESOLVED: '来源冲突尚未裁决',
  SOURCE_RECORD_PLACE_MISMATCH: '来源记录不属于当前地点',
  PLACE_NOT_SOLVER_ELIGIBLE: '修订版本尚未获得求解资格',
  OVERLAPPING_SELECTION_UNRESOLVED: '重叠地点关系尚未裁决',
  RELATION_REVIEW_REQUIRED: '地点关系尚未完成检查',
  PROJECTION_NOT_ACTIVE: '求解投影未生效',
  PROJECTION_HASH_MISMATCH: '求解投影完整性校验失败',
  PROJECTION_DURATION_MISMATCH: '求解投影时长与修订版本不一致',
  PROJECTION_REVISION_MISMATCH: '求解投影不属于当前修订版本',
  PROJECTION_PLACE_MISMATCH: '求解投影不属于当前地点',
  PROJECTION_PLACE_KIND_MISMATCH: '求解投影地点类型不一致',
  PROJECTION_GEOMETRY_KIND_MISMATCH: '求解投影几何类型不一致',
  UNSUPPORTED_PLACE_KIND: '地点类型暂不支持求解',
  PLACE_ALWAYS_OPEN: '地点全天开放',
  PLACE_WEEKLY_CLOSED: '命中固定闭馆日',
  PLACE_DATE_EXCEPTION_CLOSED: '命中临时关闭日期例外',
  PLACE_DATE_EXCEPTION_APPLIED: '命中日期开放或场次覆盖',
  HOLIDAY_OPEN_OVERRIDE: '法定节假日开放，覆盖固定闭馆日',
  HOLIDAY_CLOSURE_SHIFT: '节假日结束后顺延闭馆',
  TIME_RULE_NOT_MATCHED: '当天没有匹配的开放时间规则',
  TIME_RULE_OVERLAP: '同一天存在多条冲突时间规则',
  CROSS_MIDNIGHT_WINDOW: '开放或场次跨越午夜',
  LAST_ENTRY_AFTER_CLOSE: '最晚入园时间晚于闭馆时间',
}

const reviewFlagLabels: Record<string, string> = {
  NAME_REQUIRES_HUMAN_VERIFICATION: '名称待人工核验',
  CATEGORY_REQUIRES_HUMAN_VERIFICATION: '分类待人工核验',
  GEOMETRY_UNVERIFIED: '几何待核验',
  ACCESS_POINT_UNVERIFIED: '访问点待核验',
  TIME_RULES_NOT_COLLECTED: '开放时间未采集',
  DURATION_NOT_COLLECTED: '建议时长未采集',
  PROVIDER_POINT_IS_NOT_PLACE_GEOMETRY: '地图候选点不是正式地点几何',
  FIXED_TIME_OR_OPERATING_RULE_REQUIRED: '需要补充固定场次或营业时间',
  PROVIDER_NAME_DIFFERS_FROM_CANDIDATE: '地图名称与候选名称不一致',
  PROVIDER_NAME_SIGNALS_STATUS_RISK: '地图名称可能提示暂停或关闭',
}

const categoryLabels: Record<string, string> = {
  natural_scenery: '自然山水',
  historic_culture: '古镇人文',
  temple: '寺庙祈福',
  city_view: '城市观景',
  museum: '博物馆',
  food_district: '美食街区',
  photo_spot: '网红打卡',
  family_park: '亲子乐园',
  performing_arts: '演出演艺',
}

const auditActionLabels: Record<string, string> = {
  ADMIN_ACTOR_BOOTSTRAPPED: '初始化首个管理员',
  ADMIN_ACTOR_CREATE: '创建管理员账号',
  ADMIN_ACTOR_ROLES_CHANGE: '修改管理员角色',
  ADMIN_SESSION_CREATE: '管理员登录',
  ADMIN_SESSION_REVOKE: '管理员退出登录',
  PLACE_ACCESS_POINT_CREATED: '新增地点访问点',
  PLACE_ACCESS_POINT_UPDATED: '修改地点访问点',
  PLACE_ACCESS_POINT_RETIRED: '停用地点访问点',
  PLACE_CLOSURE_CREATED: '新增固定闭馆日',
  PLACE_CLOSURE_UPDATED: '修改固定闭馆日',
  PLACE_CLOSURE_RETIRED: '停用固定闭馆日',
  PLACE_DATE_EXCEPTION_CREATED: '新增日期例外',
  PLACE_DATE_EXCEPTION_UPDATED: '修改日期例外',
  PLACE_DATE_EXCEPTION_RETIRED: '停用日期例外',
  PLACE_EVIDENCE_REVIEWED: '审核地点证据',
  PLACE_GEOMETRY_CREATED: '新增地点几何',
  PLACE_GEOMETRY_UPDATED: '修改地点几何',
  PLACE_GEOMETRY_RETIRED: '停用地点几何',
  PLACE_RELATION_RESOLUTION_UPDATED: '更新地点关系裁决',
  PLACE_RELATION_REVIEW_CONFIRMED_NONE: '确认地点无关系',
  PLACE_REVIEW_SUBMITTED: '提交地点审核',
  PLACE_REVIEW_DECIDED: '作出地点审核决定',
  PLACE_REVISION_CREATED: '新建地点修订版本',
  PLACE_REVISION_UPDATED: '修改地点修订版本',
  PLACE_REVISION_PUBLISHED: '发布地点修订版本',
  PLACE_SOURCE_CONFLICTS_RESOLVED: '确认来源冲突处理结果',
  PLACE_SOURCE_RECORD_CREATED: '新增地点来源记录',
  PLACE_SOURCE_RECORD_DETACHED: '从当前修订移除来源记录',
  PLACE_TIME_RULE_CREATED: '新增开放时间规则',
  PLACE_TIME_RULE_UPDATED: '修改开放时间规则',
  PLACE_TIME_RULE_RETIRED: '停用开放时间规则',
  SOLVER_PROJECTION_PREPARED: '准备求解投影',
  PUBLICATION_BATCH_PREVIEWED: '预览发布批次',
  PUBLICATION_BATCH_EXECUTED: '执行发布批次',
}

const adminRoleLabels: Record<string, string> = {
  data_editor: '数据编辑员',
  data_reviewer: '数据审核员',
  data_publisher: '数据发布员',
  research_viewer: '研究查看员',
  content_moderator: '内容审核员',
  admin_security: '安全管理员',
  authenticated_admin: '已登录管理员',
}

export const auditActionOptions = Object.entries(auditActionLabels).map(([value, label]) => ({
  value,
  label,
}))

function label(value: string | null | undefined, fallback = '未识别') {
  if (!value) return fallback
  return labels[value] ?? fallback
}

export function lifecycleStatusLabel(value: string | null | undefined) { return label(value) }
export function placeKindLabel(value: string | null | undefined) { return label(value) }
export function categoryLabel(value: string | null | undefined) {
  if (!value) return '未提供'
  return categoryLabels[value] ?? value
}
export function geometryKindLabel(value: string | null | undefined) { return label(value) }
export function accessPointKindLabel(value: string | null | undefined) { return label(value) }
export function reviewStatusLabel(value: string | null | undefined) { return label(value) }
export function sourceDecisionLabel(value: string | null | undefined) { return label(value) }
export function collectionModeLabel(value: string | null | undefined) {
  return ({ api: '接口采集', dataset_download: '数据集下载', manual_reference: '人工查阅', public_page_fetch: '公开页面采集' } as Record<string, string>)[value ?? ''] ?? '其他采集方式'
}
export function sourceKindLabel(value: string | null | undefined) {
  return ({ government_public_site: '政府公开网站', official_operator_site: '官方运营方网站', open_data_portal: '开放数据平台', licensed_api: '已授权接口' } as Record<string, string>)[value ?? ''] ?? '其他来源渠道'
}
export function relationTypeLabel(value: string | null | undefined) { return label(value) }
export function relationResolutionLabel(value: string | null | undefined) { return label(value) }

export function relationReviewStatusLabel(value: string | null | undefined) {
  return ({ pending: '待完成关系检查', no_relations: '已确认无关系', not_required: '无需单独确认' } as Record<string, string>)[value ?? ''] ?? '未识别'
}
export function timeRuleKindLabel(value: string | null | undefined) { return label(value) }
export function dateExceptionKindLabel(value: string | null | undefined) { return label(value) }
export function indoorOutdoorLabel(value: string | null | undefined) { return label(value) }
export function rainSuitabilityLabel(value: string | null | undefined) { return label(value) }
export function reviewFlagLabel(value: string | null | undefined) {
  if (!value) return '待核验项'
  return reviewFlagLabels[value] ?? '其他待核验项'
}
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
    place_source_record: '地点来源记录',
    review_task: '审核任务',
    admin_actor: '管理员账号',
    admin_session: '管理员会话',
    solver_projection: '求解投影',
    publication_batch: '发布批次',
    research_snapshot: '研究快照',
  }
  return targetLabels[value ?? ''] ?? '管理对象'
}

export function reasonCodeLabel(value: string | null | undefined) {
  if (!value) return '无'
  return reasonLabels[value] ?? '其他原因'
}

export function auditActionLabel(value: string | null | undefined) {
  return auditActionLabels[value ?? ''] ?? '其他管理操作'
}

export function adminRoleLabel(value: string | null | undefined) {
  return adminRoleLabels[value ?? ''] ?? '其他管理员角色'
}
