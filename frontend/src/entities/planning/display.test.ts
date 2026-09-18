import { describe, expect, it } from 'vitest'
import { distanceLabel, durationLabel, shareWeatherLabel, weatherSourceLabel } from './display'

describe('H3 truthful plan display', () => {
  it('does not hide abnormal short durations or small distances', () => {
    expect(durationLabel(1)).toBe('1 分钟')
    expect(durationLabel(27)).toBe('27 分钟')
    expect(distanceLabel(3)).toBe(' · 3 米')
    expect(distanceLabel(null)).toBe('')
  })
  it('does not present a fixture as a forecast even if its day basis says forecast', () => {
    expect(weatherSourceLabel('deterministic_local_fixture', 'forecast')).toContain('非真实预报')
    expect(weatherSourceLabel(undefined, undefined)).toBe('天气来源待核对')
    expect(shareWeatherLabel(null, 'deterministic_local_fixture')).toContain('非真实预报')
    expect(shareWeatherLabel('local deterministic normal weather', 'forecast')).toContain('非真实预报')
  })
})
