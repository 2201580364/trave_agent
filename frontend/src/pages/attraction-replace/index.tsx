import { Button, Input, View } from '@tarojs/components'
import Taro, { useDidShow, useRouter } from '@tarojs/taro'
import { useMemo, useState } from 'react'

import './index.css'

import type { Attraction, GenerationIntent } from '@/entities/planning/types'
import { usePlanningStore } from '@/features/trip-draft/store'
import { apiRequest } from '@/shared/api/client'
import { PageAction } from '@/shared/ui/PageAction'

export default function AttractionReplacePage() {
  const store = usePlanningStore()
  const router = useRouter()
  const oldAttractionId = decodeURIComponent(router.params.oldAttractionId ?? '')
  const oldAttractionName = decodeURIComponent(router.params.oldAttractionName ?? '')
  const [items, setItems] = useState<Attraction[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [keyword, setKeyword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useDidShow(() => {
    if (!store.token) return
    apiRequest<{ items: Attraction[] }>('/api/v1/attractions?city_id=hangzhou', {
      token: store.token
    })
      .then((response) => setItems(response.items))
      .catch((cause) => setError(cause instanceof Error ? cause.message : '景点候选加载失败。'))
  })

  const candidates = useMemo(
    () => items.filter((item) => (
      item.attraction_id !== oldAttractionId
      && !store.selectedAttractionIds.includes(item.attraction_id)
      && item.name.includes(keyword.trim())
    )),
    [items, keyword, oldAttractionId, store.selectedAttractionIds]
  )

  const submit = async () => {
    if (!store.token || !store.tripId || !store.revisionId || !selectedId) return
    setLoading(true)
    setError('')
    try {
      const intent = await apiRequest<GenerationIntent>(
        `/api/v1/trips/${store.tripId}/revisions/${store.revisionId}/attraction-replacements`,
        {
          method: 'POST',
          token: store.token,
          data: {
            generation_intent_id: `intent_${Date.now()}`,
            old_attraction_id: oldAttractionId,
            new_attraction_id: selectedId
          }
        }
      )
      if (intent.status !== 'completed' || !intent.trip_id || !intent.trip_revision_id) {
        throw new Error(intent.failure_code ? `重新规划失败：${intent.failure_code}` : '行程仍在重新规划，请稍后重试。')
      }
      if (intent.replacement_draft_id && intent.replacement_draft_version) {
        store.setDraft(intent.replacement_draft_id, intent.replacement_draft_version)
      }
      store.setSelectedAttractions(
        store.selectedAttractionIds.map((id) => id === oldAttractionId ? selectedId : id)
      )
      store.setTrip(intent.trip_id, intent.trip_revision_id)
      Taro.redirectTo({ url: '/pages/trip-detail/index' })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '暂时无法替换景点。')
    } finally {
      setLoading(false)
    }
  }

  return (
    <View className='page-shell replacement-page'>
      <View className='content'>
        <Button className='back-button' onClick={() => Taro.navigateBack()}>‹ 返回原行程</Button>
        <View className='eyebrow'>行程修订</View>
        <View className='title'>替换“{oldAttractionName || '当前景点'}”</View>
        <View className='subtitle'>选择一个新景点后会完整重新规划交通、开放时间和每日节奏。只有成功后才会生成新版本，原版本会继续保留。</View>

        <View className='card search-card'>
          <Input
            className='input'
            value={keyword}
            placeholder='搜索可替换景点'
            onInput={(event) => setKeyword(event.detail.value)}
          />
        </View>

        {error && <View className='error'>{error}</View>}
        {!items.length && !error && <View className='notice'>正在读取可替换景点…</View>}
        {!!items.length && !candidates.length && (
          <View className='notice'>当前没有符合条件的候选，请修改搜索词或返回原行程。</View>
        )}

        <View className='candidate-list'>
          {candidates.map((item) => {
            const selected = selectedId === item.attraction_id
            return (
              <View
                key={item.attraction_id}
                className={`candidate-card ${selected ? 'candidate-card--selected' : ''}`}
                onClick={() => setSelectedId(item.attraction_id)}
              >
                <View>
                  <View className='section-title'>{item.name}</View>
                  <View className='field-help'>
                    {item.is_indoor ? '室内' : '室外'} · 体力 {item.energy_level} 星 · 建议 {item.suggested_duration_min} 分钟
                  </View>
                </View>
                <View className={`select-mark ${selected ? 'select-mark--active' : ''}`}>
                  {selected ? '✓' : '+'}
                </View>
              </View>
            )
          })}
        </View>
      </View>
      <PageAction loading={loading} disabled={!selectedId} onClick={submit}>
        替换并重新规划
      </PageAction>
    </View>
  )
}
