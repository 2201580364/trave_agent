import { Button, Input, View } from '@tarojs/components'
import Taro, { useDidShow, useRouter } from '@tarojs/taro'
import { useMemo, useState } from 'react'

import './index.css'

import type { Attraction } from '@/entities/planning/types'
import { usePlanningStore } from '@/features/trip-draft/store'
import { useDurableGeneration } from '@/features/trip-draft/use-durable-generation'
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
  const generation = useDurableGeneration('replacement')
  const loading = generation.loading
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
    const intentId = `intent_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    await generation.run({
      kind: 'replacement', intentId,
      path: `/api/v1/trips/${store.tripId}/revisions/${store.revisionId}/attraction-replacements`,
      data: { generation_intent_id: intentId, old_attraction_id: oldAttractionId, new_attraction_id: selectedId },
      selectedAttractionIds: store.selectedAttractionIds.map((id) => id === oldAttractionId ? selectedId : id)
    })
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

        {(error || generation.error) && <View className='error'>{error || generation.error}</View>}
        {loading && <View className='notice'>正在重新规划，刷新后会继续恢复同一任务。</View>}
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
      <PageAction loading={loading} disabled={!selectedId && !store.pendingGeneration} onClick={() => store.pendingGeneration ? generation.run() : submit()}>
        {store.pendingGeneration ? '继续等待当前任务' : '替换并重新规划'}
      </PageAction>
    </View>
  )
}
