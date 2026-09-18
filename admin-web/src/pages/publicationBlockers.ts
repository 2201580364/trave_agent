import type { PlaceRevision, PlaceRevisionEvidence, PublicationCheck, SourceConflict } from '../api/types'
import { reasonCodeLabel, reviewFlagLabel } from '../ui/displayLabels'

export type PublicationBlocker = { code: string; title: string; description: string; actionLabel?: string; target?: 'review-actions' | 'o04-evidence' | 'o05-evidence' | 'o06-source-conflicts' | 'o07-evidence' | 'revision-basic-facts' }

export function buildPublicationBlockers(
  revision: PlaceRevision,
  evidence: PlaceRevisionEvidence | null,
  sourceConflicts: SourceConflict[],
  publicationCheck: PublicationCheck | null,
): PublicationBlocker[] {
  const codes: string[] = []
  if (revision.lifecycle_status === 'candidate') codes.push('REVISION_NOT_HUMAN_VERIFIED')
  if (revision.source_record_ids.length === 0) codes.push('MISSING_SOURCE_RECORD')
  if (sourceConflicts.some((item) => !item.resolved)) codes.push('SOURCE_CONFLICT_UNRESOLVED')

  // 基础事实阻断项（与后端 evaluate_review_readiness 的 basic 检查同口径）：
  // 阻断 flag 只能通过编辑并保存名称/分类/时长清除，证据核验不会碰它们。
  const BASIC_FACT_BLOCKING_FLAGS = ['NAME_REQUIRES_HUMAN_VERIFICATION', 'CATEGORY_REQUIRES_HUMAN_VERIFICATION', 'DURATION_NOT_COLLECTED'] as const
  if (revision.lifecycle_status === 'candidate' && revision.review_flags.some((flag) => BASIC_FACT_BLOCKING_FLAGS.includes(flag as typeof BASIC_FACT_BLOCKING_FLAGS[number]))) {
    codes.push('BASIC_FACTS_NOT_CONFIRMED')
  }

  const validSourceIds = new Set((evidence?.sources ?? []).filter((item) => item.status === 'active').map((item) => item.source_record_id))
  if (evidence) {
    const verifiedGeometry = evidence.geometries.some((item) => item.active && item.review_status === 'human_verified' && item.geometry_kind === revision.geometry_kind && validSourceIds.has(item.source_record_id))
    const verifiedAccessPoint = evidence.access_points.some((item) => item.active && item.review_status === 'human_verified' && validSourceIds.has(item.source_record_id))
    const verifiedTimeRules = evidence.time_rules.filter((item) => item.active && item.review_status === 'human_verified' && validSourceIds.has(item.source_record_id))
    const verifiedTimeRule = revision.is_always_open || verifiedTimeRules.length > 0
    if (!verifiedGeometry) codes.push('MISSING_VERIFIED_GEOMETRY')
    if (!verifiedAccessPoint) codes.push('MISSING_VERIFIED_ACCESS_POINT')
    if (!verifiedTimeRule) codes.push('TIME_RULE_UNRESOLVED')
    if (revision.place_kind === 'show' && verifiedTimeRules.filter((item) => item.rule_kind === 'fixed_session').length === 0) codes.push('FIXED_SESSION_REQUIRED')
    if (evidence.relations?.some((item) => item.active && ['overlaps', 'same_experience'].includes(item.relation_type) && item.resolution_status === 'pending')) codes.push('OVERLAPPING_SELECTION_UNRESOLVED')
    if (evidence.relations?.some((item) => item.active && item.review_status !== 'human_verified')) codes.push('RELATION_EVIDENCE_UNVERIFIED')
    if ((evidence.relations ?? []).filter((item) => item.active).length === 0 && revision.relation_review_status === 'pending') codes.push('RELATION_REVIEW_REQUIRED')
  }
  if (!revision.solver_eligible) codes.push('PLACE_NOT_SOLVER_ELIGIBLE')
  if (publicationCheck && !publicationCheck.publishable) codes.push(...publicationCheck.reason_codes)

  const priority = [
    'BASIC_FACTS_NOT_CONFIRMED',
    'FIXED_SESSION_REQUIRED',
    'FIXED_SESSION_AMBIGUOUS',
    'SOURCE_CONFLICT_UNRESOLVED',
    'TIME_RULE_UNRESOLVED',
    'MISSING_VERIFIED_TIME_RULE',
    'MISSING_VERIFIED_GEOMETRY',
    'MISSING_VERIFIED_ACCESS_POINT',
    'RELATION_REVIEW_REQUIRED',
    'RELATION_EVIDENCE_UNVERIFIED',
    'OVERLAPPING_SELECTION_UNRESOLVED',
    'REVISION_NOT_HUMAN_VERIFIED',
    'PLACE_NOT_SOLVER_ELIGIBLE',
  ]
  const uniqueCodes = [...new Set(codes)].sort((left, right) => {
    const leftIndex = priority.indexOf(left)
    const rightIndex = priority.indexOf(right)
    return (leftIndex < 0 ? priority.length : leftIndex) - (rightIndex < 0 ? priority.length : rightIndex)
  })
  return uniqueCodes.map((code): PublicationBlocker => {
    if (code === 'BASIC_FACTS_NOT_CONFIRMED') return {
      code, title: '基础事实尚未经编辑确认',
      description: `名称、分类或游览时长还没有人工确认过（系统标记：${revision.review_flags.filter((flag) => BASIC_FACT_BLOCKING_FLAGS.includes(flag as typeof BASIC_FACT_BLOCKING_FLAGS[number])).map((flag) => reviewFlagLabel(flag)).join('、') || '待核验'}）。请在页面上方的“基础信息”中重新保存一次名称与分类，并把时长改为真实游览时长（当前导入值 ${revision.duration_recommended} 分钟通常是占位值）。仅核验证据区不会清除这些标记。`,
      actionLabel: '编辑基础事实', target: 'revision-basic-facts',
    }
    if (code === 'REVISION_NOT_HUMAN_VERIFIED') return {
      code, title: '尚未完成人工核验',
      description: '当前仍是候选修订版本。数据编辑员先补齐证据并送审，审核员逐项核验后点击“审核通过”。',
      actionLabel: '查看审核操作', target: 'review-actions',
    }
    if (code === 'MISSING_SOURCE_RECORD' || code === 'SOURCE_RECORD_INVALID' || code === 'SOURCE_RECORD_PLACE_MISMATCH' || code === 'CONDITIONAL_SOURCE_STAGING_ONLY') return {
      code, title: reasonCodeLabel(code),
      description: '求解器只接受当前地点仍生效的来源记录。请在 O04/O05 证据中选择有效来源，并核对来源地址、观察时间和状态。',
      actionLabel: '查看证据与来源', target: 'o04-evidence',
    }
    if (code === 'SOURCE_CONFLICT_UNRESOLVED') return {
      code, title: '存在未完成裁决的来源冲突',
      description: `检测到 ${sourceConflicts.filter((item) => !item.resolved).length} 组来源内容不一致。请打开 O06 查看每条来源记录，核对后由数据编辑员标记处理完成。`,
      actionLabel: '查看来源冲突（O06）', target: 'o06-source-conflicts',
    }
    if (code === 'MISSING_VERIFIED_GEOMETRY' || code === 'MISSING_VERIFIED_ACCESS_POINT' || code === 'MISSING_ARRIVAL_ACCESS_POINT' || code === 'MISSING_DEPARTURE_ACCESS_POINT' || code === 'ACCESS_POINT_NOT_HUMAN_VERIFIED' || code === 'ACCESS_POINT_REVISION_MISMATCH') return {
      code, title: reasonCodeLabel(code),
      description: code.includes('ACCESS') || code.includes('ARRIVAL') || code.includes('DEPARTURE')
        ? '至少需要一个当前修订版本下、来源有效且已人工核验的访问点，供系统确定游客到达和离开端点。'
        : '需要一条与地点几何类型一致、来源有效且已人工核验的几何记录。',
      actionLabel: '查看地图与访问点（O04）', target: 'o04-evidence',
    }
    if (code === 'FIXED_SESSION_REQUIRED') return {
      code, title: reasonCodeLabel(code),
      description: '该地点类型是演出/固定场次。无论当前是否已有普通开放时间，求解器都需要一条明确开始和结束时间的“固定场次”规则；请在 O05 新增或编辑规则，并重新送审。',
      actionLabel: '处理固定场次（O05）', target: 'o05-evidence',
    }
    if (code === 'TIME_RULE_UNRESOLVED' || code === 'MISSING_VERIFIED_TIME_RULE' || code === 'FIXED_SESSION_AMBIGUOUS') return {
      code, title: reasonCodeLabel(code),
      description: revision.is_always_open
        ? '当前标记为全天开放；请在 O05 核对该事实是否有来源支持。'
        : `当前读取到 ${evidence?.time_rules.filter((item) => item.active).length ?? 0} 条有效开放时间规则，其中 ${evidence?.time_rules.filter((item) => item.active && item.review_status === 'human_verified').length ?? 0} 条已人工核验。需要至少一条当前有效来源支持、并已人工核验的“开放时间规则”；日期例外仅用于节假日/临时调整，不是必需项。`,
      actionLabel: '查看开放时间（O05）', target: 'o05-evidence',
    }
    if (code === 'OVERLAPPING_SELECTION_UNRESOLVED') return {
      code, title: reasonCodeLabel(code),
      description: '存在“重叠”或“同一体验”关系尚未裁决。请在 O07 选择已裁决或无需裁决，并填写裁决说明。',
      actionLabel: '查看关系裁决（O07）', target: 'o07-evidence',
    }
    if (code === 'RELATION_EVIDENCE_UNVERIFIED') return {
      code, title: '地点关系证据尚未审核',
      description: '关系裁决表示数据编辑员是否同意该关系；当前 O07 关系证据仍是“候选”，请由 reviewer 在关系表的“审核”列点击“通过”或“驳回”，再执行修订版本审核。',
      actionLabel: '审核关系证据（O07）', target: 'o07-evidence',
    }
    if (code === 'RELATION_REVIEW_REQUIRED') return {
      code, title: reasonCodeLabel(code),
      description: '当前没有系统发现的关系记录，但 O07 尚未登记检查结论。请进入 O07，由数据编辑员确认“无关系”；如发现关系，应补录后逐条裁决。',
      actionLabel: '处理关系检查（O07）', target: 'o07-evidence',
    }
    if (code === 'PLACE_NOT_SOLVER_ELIGIBLE' || code === 'REVISION_NOT_HUMAN_VERIFIED') return {
      code, title: '当前修订版本尚不满足求解器使用条件',
      description: '求解资格不是手工勾选项，而是证据核验、冲突裁决和修订审核通过后的结果。请按上方具体阻断项处理，完成后重新送审或重新准备求解投影。',
    }
    return {
      code, title: reasonCodeLabel(code),
      description: '该项由发布门禁检查发现，请按对应证据区域核对并刷新页面。',
    }
  })
}


import { formatDateTime, localDateTimeValue, relationExplanation, relationMeaning, sourceLabelById, sourceRecordBusinessLabel, sourceRecordReferences } from './revisionDetailDisplay'
export { formatDateTime, localDateTimeValue, relationExplanation, relationMeaning, sourceLabelById, sourceRecordBusinessLabel, sourceRecordReferences } from './revisionDetailDisplay'

