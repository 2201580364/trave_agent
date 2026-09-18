import { Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useState } from 'react'

import './index.css'

import type { AnonymousSession, Draft } from '@/entities/planning/types'
import { usePlanningStore } from '@/features/trip-draft/store'
import { apiRequest } from '@/shared/api/client'

export default function HomePage() {
  const store = usePlanningStore()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const ensureSession = async () => {
    if (store.token) {
      await apiRequest('/api/v1/me', { token: store.token })
      return { token: store.token, principalId: store.principalId }
    }
    const session = await apiRequest<AnonymousSession>('/api/v1/anonymous-sessions', {
      method: 'POST',
      data: { device_installation_id: `h5_${Date.now()}` }
    })
    store.setSession(session.access_token, session.principal_id)
    return { token: session.access_token, principalId: session.principal_id }
  }

  const start = async (newPlan = false) => {
    setLoading(true)
    setError('')
    try {
      const { token } = await ensureSession()
      if (newPlan || !store.draftId) {
        const draft = await apiRequest<Draft>('/api/v1/trip-drafts', {
          method: 'POST',
          token,
          data: { city_id: 'hangzhou' }
        })
        if (newPlan) {
          store.replacePlan(draft.draft_id, draft.draft_version)
        } else {
          store.setDraft(draft.draft_id, draft.draft_version)
        }
      }
      Taro.navigateTo({ url: '/pages/trip-time/index' })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '暂时无法开始规划。')
    } finally {
      setLoading(false)
    }
  }

  const openTrips = async () => {
    setLoading(true)
    setError('')
    try {
      await ensureSession()
      Taro.navigateTo({ url: '/pages/trip-list/index' })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '暂时无法打开我的行程。')
    } finally {
      setLoading(false)
    }
  }

  return (
    <View className='page-shell'>
      <View className='content'>
        <Text className='eyebrow'>TRAVEL WITH CONFIDENCE</Text>
        <Text className='auth-link' onClick={() => Taro.navigateTo({ url: '/pages/auth/index' })}>登录 / 注册</Text>
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
          <View>✓ 为到达、返程和午晚餐留出时间</View>
          <View>✓ 未排入的景点会说明原因</View>
        </View>

        {error && <View className='error'>{error}</View>}
        {store.draftId && <View className='notice'>发现未完成的规划，可以从上次保存的位置继续。</View>}

        <View className={`primary home-primary ${loading ? 'primary--disabled' : ''}`} onClick={() => !loading && start()}>
          <Text>{loading ? '正在准备…' : store.draftId ? '继续规划' : '规划杭州行程'}</Text>
        </View>
        {store.draftId && (
          <View className={`secondary home-secondary ${loading ? 'primary--disabled' : ''}`} onClick={() => !loading && start(true)}>
            <Text>新建行程</Text>
          </View>
        )}
        <View className={`secondary home-secondary ${loading ? 'primary--disabled' : ''}`} onClick={() => !loading && openTrips()}>
          <Text>我的行程</Text>
        </View>
      </View>
    </View>
  )
}
