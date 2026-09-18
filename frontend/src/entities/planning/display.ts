// H3: display the actual plan; formatting must not invent duration or evidence.
export function durationLabel(minutes: number): string {
  return `${minutes} 分钟`
}

export function distanceLabel(meters?: number | null): string {
  if (meters == null || meters <= 0) return ''
  return meters < 1000
    ? ` · ${meters} 米`
    : ` · 约 ${(meters / 1000).toFixed(1)} 公里`
}

export function weatherSourceLabel(provenance: unknown, basis?: string): string {
  if (provenance === 'deterministic_local_fixture') return '测试天气，非真实预报'
  if (basis === 'forecast') return '天气预报，出发前请复核'
  if (basis === 'climate') return '气候参考，非实时预报'
  return '天气来源待核对'
}

export function shareWeatherLabel(condition: string | null, basis: string | null): string {
  // Also label immutable legacy shares that stored the fixture's raw condition.
  const fixture = basis === 'deterministic_local_fixture' || condition === 'local deterministic normal weather'
  if (fixture) return weatherSourceLabel('deterministic_local_fixture')
  return `${condition ? `${condition} · ` : ''}${weatherSourceLabel(undefined, basis ?? undefined)}`
}
