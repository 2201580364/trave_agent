import { describe, expect, it } from 'vitest'

import type { PlaceGeometryEvidence } from '../api/types'
import { geometryFormValues, geometryPayload, geometrySummary } from './RevisionDetailsPage'

describe('geometry evidence business form conversion', () => {
  it('builds a point GeoJSON payload from longitude and latitude fields', () => {
    expect(geometryPayload({
      geometry_kind: 'point',
      geometry_lng: 120.16097,
      geometry_lat: 30.253778,
      source_record_id: 'source-1',
    })).toEqual({ type: 'Point', coordinates: [120.16097, 30.253778] })
  })

  it('builds and closes an area payload automatically', () => {
    expect(geometryPayload({
      geometry_kind: 'area',
      geometry_coordinates: '120.1, 30.2\n120.2, 30.2\n120.2, 30.3',
      source_record_id: 'source-1',
    })).toEqual({
      type: 'Polygon',
      coordinates: [[[120.1, 30.2], [120.2, 30.2], [120.2, 30.3], [120.1, 30.2]]],
    })
  })

  it('keeps route point order and requires at least two points', () => {
    expect(geometryPayload({
      geometry_kind: 'route',
      geometry_coordinates: '120.1, 30.2\n120.2, 30.3',
      source_record_id: 'source-1',
    })).toEqual({
      type: 'LineString',
      coordinates: [[120.1, 30.2], [120.2, 30.3]],
    })
    expect(() => geometryPayload({
      geometry_kind: 'route',
      geometry_coordinates: '120.1, 30.2',
      source_record_id: 'source-1',
    })).toThrow('路线轨迹至少需要 2 个坐标点')
  })

  it('rejects invalid coordinates with Chinese validation messages', () => {
    expect(() => geometryPayload({
      geometry_kind: 'point', geometry_lng: 181, geometry_lat: 30, source_record_id: 'source-1',
    })).toThrow('请输入 -180 到 180 之间的经度')
    expect(() => geometryPayload({
      geometry_kind: 'point', geometry_lng: 120, geometry_lat: 91, source_record_id: 'source-1',
    })).toThrow('请输入 -90 到 90 之间的纬度')
    expect(() => geometryPayload({
      geometry_kind: 'area', geometry_coordinates: '120.1, 30.2\ninvalid\n120.2, 30.3', source_record_id: 'source-1',
    })).toThrow('边界/路线坐标必须逐行填写“经度, 纬度”')
  })

  it('converts existing GeoJSON back into editable business fields', () => {
    const point: PlaceGeometryEvidence = {
      geometry_id: 'geometry-1', geometry_kind: 'point',
      geometry: { type: 'Point', coordinates: [120.16097, 30.253778] },
      source_record_id: 'source-1', source_record_valid: true, review_status: 'candidate', active: true,
      created_at: '2026-08-30T00:00:00Z', reviewed_at: null,
    }
    expect(geometryFormValues(point, 'point')).toMatchObject({
      geometry_kind: 'point', geometry_lng: 120.16097, geometry_lat: 30.253778, source_record_id: 'source-1',
    })

    const area: PlaceGeometryEvidence = {
      ...point,
      geometry_id: 'geometry-2', geometry_kind: 'area',
      geometry: { type: 'Polygon', coordinates: [[[120.1, 30.2], [120.2, 30.2], [120.1, 30.2]]] },
    }
    expect(geometryFormValues(area, 'point').geometry_coordinates).toBe('120.1, 30.2\n120.2, 30.2\n120.1, 30.2')
  })

  it('shows a Chinese business summary instead of raw geometry JSON', () => {
    expect(geometrySummary({ kind: 'provider_candidate_point', lat: 30.253778, lng: 120.16097 }))
      .toBe('点位：经度 120.16097，纬度 30.253778')
    expect(geometrySummary({ type: 'Polygon', coordinates: [[[120.1, 30.2], [120.2, 30.2], [120.1, 30.2]]] }))
      .toBe('区域边界：3 个坐标点')
    expect(geometrySummary({ type: 'LineString', coordinates: [[120.1, 30.2], [120.2, 30.3]] }))
      .toBe('路线轨迹：2 个坐标点')
  })
})
