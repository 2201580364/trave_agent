import type { PlaceGeometryEvidence } from "../api/types";
export type GeometryFormValues = {
  geometry_kind: 'point' | 'area' | 'route'
  geometry_lat?: number
  geometry_lng?: number
  geometry_coordinates?: string
  source_record_id: string
}

export function geometryFormValues(item: PlaceGeometryEvidence | undefined, fallbackKind: string, sourceRecordId?: string): Partial<GeometryFormValues> {
  if (!item) return { geometry_kind: fallbackKind as GeometryFormValues['geometry_kind'], source_record_id: sourceRecordId }
  const payload = item.geometry as { type?: string; coordinates?: unknown; lat?: number; lng?: number }
  const coordinates = payload.coordinates
  if (item.geometry_kind === 'point') {
    const point = Array.isArray(coordinates) && coordinates.length >= 2
      ? coordinates
      : [payload.lng, payload.lat]
    return {
      geometry_kind: 'point',
      geometry_lng: typeof point[0] === 'number' ? point[0] : undefined,
      geometry_lat: typeof point[1] === 'number' ? point[1] : undefined,
      source_record_id: item.source_record_id,
    }
  }
  const line = item.geometry_kind === 'area'
    ? (Array.isArray(coordinates) && Array.isArray(coordinates[0]) ? coordinates[0] : coordinates)
    : coordinates
  const lines = Array.isArray(line)
    ? line.filter((pair): pair is [number, number] => Array.isArray(pair) && pair.length >= 2 && typeof pair[0] === 'number' && typeof pair[1] === 'number').map((pair) => `${pair[0]}, ${pair[1]}`).join('\n')
    : ''
  return { geometry_kind: item.geometry_kind as GeometryFormValues['geometry_kind'], geometry_coordinates: lines, source_record_id: item.source_record_id }
}

// 解析并校验坐标文本；返回坐标点数组，格式/数量不合法时抛出用户可读错误。
// 表单字段级校验与 payload 生成共用此函数，保证两处口径一致。
export function parseCoordinateLines(kind: GeometryFormValues['geometry_kind'], text: string | undefined): [number, number][] {
  const points = (text ?? '').split(/\r?\n/).map((line) => line.trim()).filter(Boolean).map((line) => {
    const pair = line.split(/[,，\s]+/).filter(Boolean).map(Number)
    if (pair.length !== 2 || pair.some((value) => !Number.isFinite(value) || value < -180 || value > 180)) throw new Error('边界/路线坐标必须逐行填写“经度, 纬度”')
    if (pair[1] < -90 || pair[1] > 90) throw new Error('纬度必须在 -90 到 90 之间')
    return [pair[0], pair[1]] as [number, number]
  })
  const minimum = kind === 'area' ? 3 : 2
  if (points.length < minimum) throw new Error(`${kind === 'area' ? '区域边界' : '路线轨迹'}至少需要 ${minimum} 个坐标点`)
  return points
}

export function geometryPayload(values: GeometryFormValues): Record<string, unknown> {
  if (values.geometry_kind === 'point') {
    if (typeof values.geometry_lng !== 'number' || typeof values.geometry_lat !== 'number') throw new Error('请填写完整的经度和纬度')
    if (values.geometry_lng < -180 || values.geometry_lng > 180) throw new Error('请输入 -180 到 180 之间的经度')
    if (values.geometry_lat < -90 || values.geometry_lat > 90) throw new Error('请输入 -90 到 90 之间的纬度')
    return { type: 'Point', coordinates: [values.geometry_lng, values.geometry_lat] }
  }
  const points = parseCoordinateLines(values.geometry_kind, values.geometry_coordinates)
  if (values.geometry_kind === 'area' && (points[0][0] !== points.at(-1)?.[0] || points[0][1] !== points.at(-1)?.[1])) points.push(points[0])
  return values.geometry_kind === 'area'
    ? { type: 'Polygon', coordinates: [points] }
    : { type: 'LineString', coordinates: points }
}

export function geometrySummary(value: Record<string, unknown>): string {
  const type = typeof value.type === 'string' ? value.type : ''
  const coordinates = value.coordinates
  if (Array.isArray(coordinates) && coordinates.length >= 2 && (type === 'Point' || !type)) {
    return `点位：经度 ${coordinates[0]}，纬度 ${coordinates[1]}`
  }
  if ((type === 'Point' || !type) && typeof value.lat === 'number' && typeof value.lng === 'number') {
    return `点位：经度 ${value.lng}，纬度 ${value.lat}`
  }
  if (type === 'Polygon' && Array.isArray(coordinates) && Array.isArray(coordinates[0])) {
    return `区域边界：${coordinates[0].length} 个坐标点`
  }
  if (type === 'LineString' && Array.isArray(coordinates)) {
    return `路线轨迹：${coordinates.length} 个坐标点`
  }
  return '图形数据已保存（可在编辑中查看原始数据）'
}

