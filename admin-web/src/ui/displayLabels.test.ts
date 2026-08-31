import { describe, expect, it } from 'vitest'

import {
  accessPointKindLabel,
  auditTargetTypeLabel,
  lifecycleStatusLabel,
  placeKindLabel,
  reasonCodeLabel,
  reviewStatusLabel,
} from './displayLabels'

describe('管理端展示标签', () => {
  it('将内部生命周期、地点类型和证据类型转换为中文', () => {
    expect(lifecycleStatusLabel('human_verified')).toBe('人工已核验')
    expect(placeKindLabel('scenic_area')).toBe('景区')
    expect(accessPointKindLabel('visitor_entrance')).toBe('游客入口')
    expect(reviewStatusLabel('rejected')).toBe('已驳回')
  })

  it('将审计对象和门禁原因转换为中文，未知值不泄漏内部代码', () => {
    expect(auditTargetTypeLabel('place_revision')).toBe('地点修订版本')
    expect(reasonCodeLabel('MISSING_VERIFIED_ACCESS_POINT')).toBe('缺少已核验的访问点')
    expect(reasonCodeLabel('FIXED_SESSION_REQUIRED')).toBe('演出地点需要固定场次规则')
    expect(placeKindLabel('future_internal_value')).toBe('未识别')
    expect(reasonCodeLabel('FUTURE_REASON')).toBe('其他原因')
  })
})
