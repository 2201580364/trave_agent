import { Button, Input, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useMemo, useState } from 'react'

import type { Attraction, Draft } from '@/entities/planning/types'
import { usePlanningStore } from '@/features/trip-draft/store'
import { apiRequest } from '@/shared/api/client'
import { PageAction } from '@/shared/ui/PageAction'
import { StepHeader } from '@/shared/ui/StepHeader'

export default function AttractionSelectPage() {
  const store = usePlanningStore()
  const [items, setItems] = useState<Attraction[]>([])
  const [keyword, setKeyword] = useState('')
  const [indoorOnly, setIndoorOnly] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useDidShow(() => {
    if (!store.token) return
    apiRequest<{ items: Attraction[] }>('/api/v1/attractions?city_id=hangzhou', {
      token: store.token
    })
      .then((response) => setItems(response.items))
      .catch((cause) => setError(cause instanceof Error ? cause.message : '景点加载失败。'))
  })

  const filtered = useMemo(
    () => items.filter((item) => (
      item.name.includes(keyword.trim()) && (!indoorOnly || item.is_indoor)
    )),
    [items, keyword, indoorOnly]
  )

  const toggle = (id: string) => {
    const selected = store.selectedAttractionIds.includes(id)
      ? store.selectedAttractionIds.filter((item) => item !== id)
      : [...store.selectedAttractionIds, id]
    store.setSelectedAttractions(selected)
  }

  const submit = async () => {
    if (!store.token || !store.draftId || !store.selectedAttractionIds.length) return
    setLoading(true)
    setError('')
    try {
      const draft = await apiRequest<Draft>(
        `/api/v1/trip-drafts/${store.draftId}/attraction-selection`,
        {
          method: 'PUT',
          token: store.token,
          data: {
            expected_draft_version: store.draftVersion,
            attraction_ids: store.selectedAttractionIds,
            visit_period_preferences: []
          }
        }
      )
      store.setDraftVersion(draft.draft_version)
      Taro.navigateTo({ url: '/pages/trip-review/index' })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '保存景点选择失败。')
    } finally {
      setLoading(false)
    }
  }

  return (
    <View className='page-shell'>
      <View className='content'>
        <StepHeader step={2} title='想去哪里' />
        <View className='title'>选择真正想去的地方</View>
        <View className='subtitle'>这里只展示已发布的基础信息，不使用虚构评分或推荐理由。</View>

        <View className='card search-card'>
          <Input className='input' value={keyword} placeholder='搜索景点名称' onInput={(event) => setKeyword(event.detail.value)} />
          <Button className={`filter-chip ${indoorOnly ? 'filter-chip--active' : ''}`} onClick={() => setIndoorOnly(!indoorOnly)}>
            {indoorOnly ? '✓ ' : ''}只看室内
          </Button>
        </View>

        {error && <View className='error'>{error}</View>}
        {!items.length && !error && <View className='notice'>正在读取已发布的杭州景点数据…</View>}

        <View className='attraction-list'>
          {filtered.map((item) => {
            const selected = store.selectedAttractionIds.includes(item.attraction_id)
            return (
              <View
                key={item.attraction_id}
                className={`attraction-card ${selected ? 'attraction-card--selected' : ''}`}
                onClick={() => toggle(item.attraction_id)}
              >
                <View className='attraction-main'>
                  <View className='section-title'>{item.name}</View>
                  <View className='attraction-meta'>
                    {item.is_indoor ? '室内' : '室外'} · 体力 {item.energy_level} 星 · 建议 {item.suggested_duration_min} 分钟
                  </View>
                  <View className='field-help'>
                    {item.is_always_open ? '全天开放信息已验证' : item.close_days.length ? `每周闭馆：${item.close_days.join('、')}` : '开放时间以发布数据为准'}
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

      <View className='selected-summary'>
        <Text>已选 {store.selectedAttractionIds.length} 个景点</Text>
      </View>
      <PageAction loading={loading} disabled={!store.selectedAttractionIds.length} onClick={submit}>确认选择</PageAction>
    </View>
  )
}
