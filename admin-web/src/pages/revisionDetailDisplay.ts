import type { PlaceEvidenceSource, PlaceRelationEvidence, PlaceRevisionEvidence, SourceChannel } from '../api/types'

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'medium',
    hour12: false,
  }).format(new Date(value))
}

export function localDateTimeValue(value: Date): string {
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 16)
}

export function sourceRecordBusinessLabel(source: PlaceEvidenceSource, sourceChannels: SourceChannel[]): string {
  const channel = sourceChannels.find((item) => item.source_id === source.source_id)
  return `${channel?.display_name ?? '已登记来源'} · ${new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium' }).format(new Date(source.observed_at))}`
}

export function relationMeaning(value: string): string {
  return ({
    contains: '上级地点包含下级地点',
    part_of: '前一个地点属于后一个地点',
    overlaps: '两个地点存在空间或范围重叠',
    same_experience: '两个地点属于同一体验或同一入场场景',
  } as Record<string, string>)[value] ?? '系统识别的地点关系，需要人工确认含义'
}

export function relationExplanation(item: PlaceRelationEvidence): string {
  const from = item.from_place_name ?? '前一个地点'
  const to = item.to_place_name ?? '后一个地点'
  switch (item.relation_type) {
    case 'contains': return `${from} 是范围/园区，包含 ${to}`
    case 'part_of': return `${from} 属于 ${to}`
    case 'overlaps': return `${from} 与 ${to} 的可游览范围可能重叠`
    case 'same_experience': return `${from} 与 ${to} 可能是同一体验，不应重复计算`
    default: return `${from} → ${to}，请根据来源证据确认`
  }
}

export function sourceLabelById(evidence: PlaceRevisionEvidence | null, sourceRecordId: string, sourceChannels: SourceChannel[]): string {
  const source = evidence?.sources.find((item) => item.source_record_id === sourceRecordId)
  return source ? sourceRecordBusinessLabel(source, sourceChannels) : '来源记录不可用'
}

export function sourceRecordReferences(evidence: PlaceRevisionEvidence | null, sourceRecordId: string): string[] {
  if (!evidence) return []
  const references: string[] = []
  if (evidence.geometries.some((item) => item.active && item.source_record_id === sourceRecordId)) references.push('地点几何')
  if (evidence.access_points.some((item) => item.active && item.source_record_id === sourceRecordId)) references.push('访问点')
  if (evidence.time_rules.some((item) => item.active && item.source_record_id === sourceRecordId)) references.push('开放时间')
  if (evidence.closures.some((item) => item.active && item.source_record_id === sourceRecordId)) references.push('固定闭馆日')
  if (evidence.date_exceptions.some((item) => item.active && item.source_record_id === sourceRecordId)) references.push('日期例外')
  if ((evidence.relations ?? []).some((item) => item.active && item.source_record_id === sourceRecordId)) references.push('地点关系')
  return references
}


export function isFormValidationError(value: unknown): boolean {
  return typeof value === 'object' && value !== null && 'errorFields' in value
}
