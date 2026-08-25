import { Button, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useState } from 'react'

import './index.css'

import type { Draft, MealBreak, TripRevision } from '@/entities/planning/types'
import { usePlanningStore } from '@/features/trip-draft/store'
import { apiRequest } from '@/shared/api/client'

function minuteLabel(value: number) {
  const dayOffset = Math.floor(value / 1440)
  const minute = value % 1440
  const hour = Math.floor(minute / 60).toString().padStart(2, '0')
  const rest = (minute % 60).toString().padStart(2, '0')
  return `${hour}:${rest}${dayOffset ? ` +${dayOffset}天` : ''}`
}

function arrivalLabel(value: number, fixedEvent = false) {
  if (fixedEvent) return `${minuteLabel(value)} 场次`
  const start = Math.floor(value / 15) * 15
  return `${minuteLabel(start)}–${minuteLabel(start + 30)}`
}

function durationLabel(value: number) {
  if (value <= 30) return '20–30 分钟'
  if (value <= 60) return '半小时至 1 小时'
  if (value <= 90) return '1–1.5 小时'
  if (value <= 120) return '1.5–2 小时'
  const hours = Math.round(value / 30) / 2
  return `${hours} 小时`
}

function transitDurationLabel(value: number) {
  if (value <= 6) return '5–10 分钟'
  if (value <= 12) return '10–15 分钟'
  if (value <= 20) return '15–25 分钟'
  if (value <= 30) return '25–40 分钟'
  const start = Math.floor(value / 10) * 10
  return `${start}–${start + 15} 分钟`
}

function dayTransitLabel(value: number) {
  return value > 0 ? `市内接驳约 ${transitDurationLabel(value)}` : '本日无景点间接驳'
}

function transportModeLabel(mode?: string | null) {
  if (mode === 'walking_estimate') return '步行'
  if (mode === 'taxi_estimate') return '打车'
  if (mode === 'transit_or_taxi_estimate') return '公交/地铁或打车'
  return '驾车/打车'
}

function mealLabel(name: string, meal?: MealBreak | null) {
  if (!meal || meal.status === 'unscheduled') return `${name}留白 · 未能安排`
  const time = meal.start_min != null && meal.end_min != null
    ? ` · 建议 ${minuteLabel(Math.floor(meal.start_min / 10) * 10)}–${minuteLabel(Math.floor(meal.end_min / 10) * 10)} 前后`
    : ''
  return `${name}留白${meal.status === 'reduced' ? ' · 已缩短' : ' · 已安排'}${time}`
}

export default function TripDetailPage() {
  const store = usePlanningStore()
  const [revision, setRevision] = useState<TripRevision | null>(null)
  const [activeDay, setActiveDay] = useState(0)
  const [error, setError] = useState('')
  const [startingNew, setStartingNew] = useState(false)

  useDidShow(() => {
    if (!store.token || !store.tripId || !store.revisionId) return
    apiRequest<TripRevision>(
      `/api/v1/trips/${store.tripId}/revisions/${store.revisionId}`,
      { token: store.token }
    )
      .then(setRevision)
      .catch((cause) => setError(cause instanceof Error ? cause.message : '行程恢复失败。'))
  })

  const result = revision?.result_snapshot
  const day = result?.days[activeDay]
  const dayTransitMin = day?.nodes.reduce(
    (total, node) => total + (node.buffered_travel_from_previous_min ?? 0),
    0
  ) ?? 0
  const startNewPlan = async () => {
    if (!store.token) return
    setStartingNew(true)
    setError('')
    try {
      const draft = await apiRequest<Draft>('/api/v1/trip-drafts', {
        method: 'POST',
        token: store.token,
        data: { city_id: 'hangzhou' }
      })
      store.replacePlan(draft.draft_id, draft.draft_version)
      Taro.redirectTo({ url: '/pages/trip-time/index' })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '暂时无法新建行程。')
    } finally {
      setStartingNew(false)
    }
  }

  return (
    <View className='page-shell trip-page'>
      <View className='content'>
        <Text className='eyebrow'>杭州 · 规划模式</Text>
        <View className='title'>你的可执行行程</View>
        <View className='subtitle'>先看每天怎么走，再查看未排入和数据说明。</View>
        <Button className='secondary trip-new-button' loading={startingNew} onClick={startNewPlan}>
          ＋ 规划新行程
        </Button>

        {revision?.completion_kind === 'partial_success' && (
          <View className='notice notice--warning'>部分景点未排入，已保留可执行的成功行程。</View>
        )}
        {revision?.has_soft_degradation && (
          <View className='notice'>行程存在体验降级，但没有违反闭馆、时间窗或交通衔接等硬约束。</View>
        )}
        {error && <View className='error'>{error}</View>}
        {!revision && !error && <View className='notice'>正在恢复已保存的行程结果…</View>}

        {result && (
          <>
            <View className='card result-summary'>
              <View><Text className='summary-number'>{result.days.length}</Text><Text className='summary-caption'>天行程</Text></View>
              <View><Text className='summary-number'>{result.summary?.scheduled_count ?? '—'}</Text><Text className='summary-caption'>已安排</Text></View>
              <View><Text className='summary-number'>{result.unplaced?.length ?? 0}</Text><Text className='summary-caption'>未排入</Text></View>
            </View>

            <View className='day-tabs' role='tablist'>
              {result.days.map((item, index) => (
                <Button
                  key={item.date}
                  className={`day-tab ${activeDay === index ? 'day-tab--active' : ''}`}
                  onClick={() => setActiveDay(index)}
                >
                  第 {index + 1} 天<Text className='day-date'>{item.date.slice(5)}</Text>
                </Button>
              ))}
            </View>

            {day && (
              <View className='card timeline-card'>
                <View className='day-heading'>
                  <View>
                    <View className='section-title'>{day.date}</View>
                    <View className='field-help'>{dayTransitLabel(dayTransitMin)} · {day.weather?.basis === 'forecast' ? '天气预报' : '气候参考'}</View>
                  </View>
                  <View className='status-badge'>{day.search_status === 'best_so_far' ? '当前最优可行方案' : '已完成安排'}</View>
                </View>

                {day.nodes.some((node) => node.travel_basis === 'approximate') && (
                  <View className='notice transit-warning'>当前接驳为本地近似估算，交通方式和耗时请在出发前用实时导航确认。</View>
                )}

                {day.nodes.length > 0 && (
                  <View className='meal-list'>
                    <View className='meal-block'>{mealLabel('午餐', day.lunch)}</View>
                    <View className='meal-block'>{mealLabel('晚餐', day.meal)}</View>
                  </View>
                )}

                <View className='timeline'>
                  {!day.nodes.length && (
                    <View className='notice'>本日暂无景点安排，可调整日期或景点后重新生成。</View>
                  )}
                  {day.nodes.map((node, index) => (
                    <View key={node.node_id} className='timeline-item'>
                      <View className='time-column'>{arrivalLabel(node.arrival_min, node.timing_kind === 'fixed_event')}</View>
                      <View className='timeline-rail'><View className='timeline-dot' /></View>
                      <View className='visit-card'>
                        <View className='section-title'>{node.name}</View>
                        <View className='attraction-meta'>建议停留约 {durationLabel(node.planned_duration_min)}</View>
                        {index > 0 && (
                          <View className='transit-note'>
                            从上一站建议 {transportModeLabel(node.transport_mode)} · 约 {transitDurationLabel(node.buffered_travel_from_previous_min ?? node.travel_from_previous_min ?? 0)}
                          </View>
                        )}
                      </View>
                    </View>
                  ))}
                </View>
              </View>
            )}

            {!!result.unplaced?.length && (
              <View className='card'>
                <View className='section-title'>未排入的景点</View>
                {result.unplaced.map((item) => (
                  <View key={item.attraction_id} className='unplaced-row'>
                    <Text>{item.name}</Text><Text className='reason-code'>{item.reason_code}</Text>
                  </View>
                ))}
              </View>
            )}

            {!!result.degradations?.length && (
              <View className='card'>
                <View className='section-title'>行程提示</View>
                {result.degradations.map((item) => (
                  <View key={item.code} className='notice'>{item.message}</View>
                ))}
              </View>
            )}

            <View className='card provenance-card'>
              <View className='section-title'>这份行程依据什么生成</View>
              <View className='field-help'>使用已发布的景点、天气和交通数据快照；刷新页面不会重新随机排列节点。</View>
            </View>
          </>
        )}
      </View>
    </View>
  )
}
