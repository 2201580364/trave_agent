import { Button, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useState } from 'react'

import './index.css'

import type { Draft } from '@/entities/planning/types'
import { useDurableGeneration } from '@/features/trip-draft/use-durable-generation'
import { usePlanningStore } from '@/features/trip-draft/store'
import { apiRequest } from '@/shared/api/client'
import { PageAction } from '@/shared/ui/PageAction'
import { StepHeader } from '@/shared/ui/StepHeader'

interface ReviewResponse {
  ready_for_generation: boolean
  issues: string[]
  summary: Draft
}

export default function TripReviewPage() {
  const store = usePlanningStore()
  const [review, setReview] = useState<ReviewResponse | null>(null)
  const generation = useDurableGeneration('initial')
  const loading = generation.loading
  const [error, setError] = useState('')

  useDidShow(() => {
    if (!store.token || !store.draftId) return
    apiRequest<ReviewResponse>(`/api/v1/trip-drafts/${store.draftId}/review`, {
      token: store.token
    })
      .then(setReview)
      .catch((cause) => setError(cause instanceof Error ? cause.message : '摘要加载失败。'))
  })

  const generate = async () => {
    if (!store.token || !store.draftId || !review?.ready_for_generation) return
    const intentId = `intent_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    await generation.run({
      kind: 'initial', intentId, path: '/api/v1/generation-intents',
      data: { generation_intent_id: intentId, draft_id: store.draftId, draft_version: store.draftVersion },
      selectedAttractionIds: store.selectedAttractionIds
    })
  }

  const facts = review?.summary.travel_facts
  return (
    <View className='page-shell'>
      <View className='content'>
        <StepHeader step={3} title='确认行程' backUrl='/pages/attraction-select/index' />
        <View className='title'>确认后开始安排</View>
        <View className='subtitle'>系统会严格守住物理底线，并对体验上的妥协给出说明。</View>

        {review && (
          <>
            <View className='card review-summary'>
              <View><Text className='summary-key'>目的地</Text><Text>杭州</Text></View>
              <View><Text className='summary-key'>日期</Text><Text>{facts?.start_date} 至 {facts?.end_date}</Text></View>
              <View><Text className='summary-key'>到离时间</Text><Text>{facts?.arrival.arrives_at.slice(11, 16)} / {facts?.departure.departs_at.slice(11, 16)}</Text></View>
              <View><Text className='summary-key'>旅行节奏</Text><Text>适中</Text></View>
              <View><Text className='summary-key'>已选景点</Text><Text>{review.summary.selected_attraction_ids.length} 个</Text></View>
            </View>

            <View className='card'>
              <View className='section-title'>系统会自动考虑</View>
              <View className='check-list'>
                <View>✓ 闭馆日和开放时间</View>
                <View>✓ 到达与返程时间边界</View>
                <View>✓ 天气和景点间交通</View>
                <View>✓ 午餐、晚餐留白和分天节奏</View>
              </View>
            </View>

            {!review.ready_for_generation && (
              <View className='error'>仍需完善：{review.issues.join('、')}</View>
            )}
          </>
        )}
        {!review && !error && <View className='notice'>正在恢复生成前摘要…</View>}
        {(error || generation.error) && <View className='error'>{error || generation.error}</View>}
        {loading && <View className='notice'>正在获取交通并规划行程，刷新后会继续恢复同一任务。</View>}
      </View>
      <PageAction loading={loading} disabled={!review?.ready_for_generation} onClick={generate}>
        {store.pendingGeneration ? '继续等待当前任务' : '生成我的行程'}
      </PageAction>
    </View>
  )
}
