import { Button, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useState } from 'react'

import './index.css'

import type { Draft, TripListResponse, TripSummary } from '@/entities/planning/types'
import { usePlanningStore } from '@/features/trip-draft/store'
import { apiRequest } from '@/shared/api/client'

const PAGE_SIZE = 20

function dateRange(start: string | null, end: string | null) {
  if (!start || !end) return '日期待确认'
  if (start === end) return start
  return `${start} 至 ${end}`
}

function updatedLabel(value: string) {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function statusLabel(item: TripSummary) {
  if (item.completion_kind === 'partial_success') return `有 ${item.unplaced_count} 个景点未排入`
  if (item.has_soft_degradation) return '已生成 · 有体验提示'
  return '已生成'
}

export default function TripListPage() {
  const store = usePlanningStore()
  const [items, setItems] = useState<TripSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [error, setError] = useState('')

  const load = async (offset = 0) => {
    if (!store.token) {
      setError('当前设备会话不可用，请返回首页后重试。')
      return
    }
    offset === 0 ? setLoading(true) : setLoadingMore(true)
    setError('')
    try {
      const response = await apiRequest<TripListResponse>(
        `/api/v1/trips?limit=${PAGE_SIZE}&offset=${offset}`,
        { token: store.token }
      )
      setItems((current) => offset === 0 ? response.items : [...current, ...response.items])
      setHasMore(response.has_more)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '行程列表恢复失败。')
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }

  useDidShow(() => {
    void load(0)
  })

  const openTrip = (item: TripSummary) => {
    store.setTrip(
      item.trip_id,
      item.current_revision_id,
      item.current_revision_number
    )
    Taro.navigateTo({ url: '/pages/trip-detail/index' })
  }

  const startNewPlan = async () => {
    if (!store.token) return
    setLoading(true)
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
      setLoading(false)
    }
  }

  return (
    <View className='page-shell trip-list-page'>
      <View className='content'>
        <Text className='eyebrow'>SAVED ON THIS DEVICE</Text>
        <View className='title'>我的行程</View>
        <View className='subtitle'>按最近更新排序；历史版本也会完整保留。</View>

        <Button className='primary trip-list-new' loading={loading} onClick={startNewPlan}>
          ＋ 规划新行程
        </Button>

        {error && <View className='error'>{error}</View>}
        {loading && !items.length && <View className='notice'>正在恢复当前设备保存的行程…</View>}
        {!loading && !error && !items.length && (
          <View className='card empty-trip-card'>
            <View className='section-title'>还没有已生成的行程</View>
            <View className='field-help'>完成一次规划后，就可以从这里恢复最新版和历史版本。</View>
          </View>
        )}

        <View className='trip-list'>
          {items.map((item) => (
            <View key={item.trip_id} className='card trip-list-card'>
              <View className='trip-list-heading'>
                <View>
                  <View className='section-title'>{item.city_name}</View>
                  <View className='trip-list-date'>{dateRange(item.start_date, item.end_date)}</View>
                </View>
                <View className={`trip-list-status ${item.completion_kind === 'partial_success' ? 'trip-list-status--warning' : ''}`}>
                  {statusLabel(item)}
                </View>
              </View>
              <View className='trip-list-metrics'>
                <View><Text className='metric-number'>{item.scheduled_count}</Text><Text>已安排</Text></View>
                <View><Text className='metric-number'>{item.unplaced_count}</Text><Text>未排入</Text></View>
                <View><Text className='metric-number'>{item.current_revision_number}</Text><Text>当前版本</Text></View>
              </View>
              <View className='trip-list-meta'>
                共 {item.revision_count} 个版本 · 最近更新 {updatedLabel(item.updated_at)}
              </View>
              <Button className='secondary trip-list-open' onClick={() => openTrip(item)}>
                查看行程
              </Button>
            </View>
          ))}
        </View>

        {hasMore && (
          <Button className='secondary trip-list-more' loading={loadingMore} onClick={() => load(items.length)}>
            加载更多
          </Button>
        )}
      </View>
    </View>
  )
}
