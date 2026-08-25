import { Button, Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useState } from 'react'

import type { AnonymousSession, Draft } from '@/entities/planning/types'
import { usePlanningStore } from '@/features/trip-draft/store'
import { apiRequest } from '@/shared/api/client'

export default function HomePage() {
  const store = usePlanningStore()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const start = async () => {
    setLoading(true)
    setError('')
    try {
      let token = store.token
      let principalId = store.principalId
      if (!token) {
        const session = await apiRequest<AnonymousSession>('/api/v1/anonymous-sessions', {
          method: 'POST',
          data: { device_installation_id: `h5_${Date.now()}` }
        })
        token = session.access_token
        principalId = session.principal_id
        store.setSession(token, principalId)
      }
      if (!store.draftId) {
        const draft = await apiRequest<Draft>('/api/v1/trip-drafts', {
          method: 'POST',
          token,
          data: { city_id: 'hangzhou' }
        })
        store.setDraft(draft.draft_id, draft.draft_version)
      }
      Taro.navigateTo({ url: '/pages/trip-time/index' })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '暂时无法开始规划。')
    } finally {
      setLoading(false)
    }
  }

  return (
    <View className='page-shell'>
      <View className='content'>
        <Text className='eyebrow'>TRAVEL WITH CONFIDENCE</Text>
        <View className='title'>少一点来回折腾，{`\n`}多一点杭州好时光</View>
        <View className='subtitle'>
          系统会检查闭馆、开放时间、到离边界、天气和交通衔接，先给你一份真正能走的行程。
        </View>

        <View className='card hero-card'>
          <View className='hero-mark'>杭</View>
          <View>
            <View className='section-title'>从杭州开始</View>
            <View className='field-help'>三步完成首次规划，细节随时可以调整。</View>
          </View>
        </View>

        <View className='card promise-list'>
          <View>✓ 自动避开闭馆和入园冲突</View>
          <View>✓ 为到达、返程和晚餐留出时间</View>
          <View>✓ 未排入的景点会说明原因</View>
        </View>

        {error && <View className='error'>{error}</View>}
        {store.draftId && <View className='notice'>发现未完成的规划，可以从上次保存的位置继续。</View>}

        <Button className='primary home-primary' loading={loading} onClick={start}>
          {store.draftId ? '继续规划' : '规划杭州行程'}
        </Button>
      </View>
    </View>
  )
}
