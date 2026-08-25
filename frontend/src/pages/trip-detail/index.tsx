import { Button, Text, View } from '@tarojs/components'
import { useDidShow } from '@tarojs/taro'
import { useState } from 'react'

import type { TripRevision } from '@/entities/planning/types'
import { usePlanningStore } from '@/features/trip-draft/store'
import { apiRequest } from '@/shared/api/client'

function minuteLabel(value: number) {
  const dayOffset = Math.floor(value / 1440)
  const minute = value % 1440
  const hour = Math.floor(minute / 60).toString().padStart(2, '0')
  const rest = (minute % 60).toString().padStart(2, '0')
  return `${hour}:${rest}${dayOffset ? ` +${dayOffset}天` : ''}`
}

export default function TripDetailPage() {
  const store = usePlanningStore()
  const [revision, setRevision] = useState<TripRevision | null>(null)
  const [activeDay, setActiveDay] = useState(0)
  const [error, setError] = useState('')

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
  return (
    <View className='page-shell trip-page'>
      <View className='content'>
        <Text className='eyebrow'>杭州 · 规划模式</Text>
        <View className='title'>你的可执行行程</View>
        <View className='subtitle'>先看每天怎么走，再查看未排入和数据说明。</View>

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
                    <View className='field-help'>交通约 {day.total_travel_min ?? 0} 分钟 · {day.weather?.basis === 'forecast' ? '天气预报' : '气候参考'}</View>
                  </View>
                  <View className='status-badge'>{day.search_status === 'best_so_far' ? '当前最优可行方案' : '已完成安排'}</View>
                </View>

                <View className='timeline'>
                  {day.nodes.map((node, index) => (
                    <View key={node.node_id} className='timeline-item'>
                      <View className='time-column'>{minuteLabel(node.arrival_min)}</View>
                      <View className='timeline-rail'><View className='timeline-dot' /></View>
                      <View className='visit-card'>
                        <View className='section-title'>{node.name}</View>
                        <View className='attraction-meta'>游览约 {node.planned_duration_min} 分钟 · {minuteLabel(node.leave_min)} 离开</View>
                        {index > 0 && <View className='transit-note'>从上一站交通约 {node.travel_from_previous_min ?? 0} 分钟</View>}
                      </View>
                    </View>
                  ))}
                  {day.meal && (
                    <View className='meal-block'>晚餐留白 · {day.meal.status === 'reduced' ? '已缩短' : day.meal.status === 'unscheduled' ? '未能安排' : '已安排'}</View>
                  )}
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
