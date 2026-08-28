import { Button, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useState } from 'react'

import './index.css'

import type { TripRevisionListResponse, TripRevisionSummary } from '@/entities/planning/types'
import { usePlanningStore } from '@/features/trip-draft/store'
import { apiRequest } from '@/shared/api/client'

function revisionDate(item: TripRevisionSummary) {
  if (!item.start_date || !item.end_date) return '日期待确认'
  return item.start_date === item.end_date
    ? item.start_date
    : `${item.start_date} 至 ${item.end_date}`
}

export default function TripRevisionsPage() {
  const store = usePlanningStore()
  const [items, setItems] = useState<TripRevisionSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useDidShow(() => {
    if (!store.token || !store.tripId) {
      setError('当前行程信息不完整，请从“我的行程”重新打开。')
      return
    }
    setLoading(true)
    setError('')
    apiRequest<TripRevisionListResponse>(
      `/api/v1/trips/${store.tripId}/revisions`,
      { token: store.token }
    )
      .then((response) => {
        setItems(response.items)
        const current = response.items.find((item) => item.is_current)
        if (current) {
          store.setCurrentRevision(current.trip_revision_id, current.revision_number)
        }
      })
      .catch((cause) => setError(cause instanceof Error ? cause.message : '历史版本恢复失败。'))
      .finally(() => setLoading(false))
  })

  const openRevision = (item: TripRevisionSummary) => {
    store.viewRevision(item.trip_revision_id)
    Taro.navigateBack()
  }

  return (
    <View className='page-shell revision-page'>
      <View className='content'>
        <Text className='eyebrow'>READ-ONLY HISTORY</Text>
        <View className='title'>历史版本</View>
        <View className='subtitle'>每次重新规划都会生成新版本；查看旧版本不会覆盖当前行程。</View>

        {loading && <View className='notice'>正在读取历史版本…</View>}
        {error && <View className='error'>{error}</View>}

        <View className='revision-list'>
          {items.map((item) => (
            <View key={item.trip_revision_id} className={`card revision-card ${item.is_current ? 'revision-card--current' : ''}`}>
              <View className='revision-heading'>
                <View className='section-title'>第 {item.revision_number} 版</View>
                <View className={item.is_current ? 'current-badge' : 'history-badge'}>
                  {item.is_current ? '当前版本' : '历史只读'}
                </View>
              </View>
              <View className='revision-date'>{revisionDate(item)}</View>
              <View className='revision-summary'>
                已安排 {item.scheduled_count} 个 · 未排入 {item.unplaced_count} 个
              </View>
              {item.has_soft_degradation && <View className='field-help'>本版本包含体验降级提示</View>}
              <Button className='secondary revision-open' onClick={() => openRevision(item)}>
                {item.is_current ? '查看当前版本' : `查看历史第 ${item.revision_number} 版`}
              </Button>
            </View>
          ))}
        </View>
      </View>
    </View>
  )
}
