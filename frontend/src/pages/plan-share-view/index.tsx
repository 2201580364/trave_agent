import { Button, Text, View } from '@tarojs/components'
import Taro, { getCurrentInstance, useDidShow } from '@tarojs/taro'
import { useState } from 'react'

import './index.css'

import type { AnonymousSession, Draft, PublicPlanShare } from '@/entities/planning/types'
import { PlanShareCard } from '@/features/plan-share/PlanShareCard'
import { usePlanningStore } from '@/features/trip-draft/store'
import { apiRequest } from '@/shared/api/client'

export default function PlanShareViewPage() {
  const store = usePlanningStore()
  const [share, setShare] = useState<PublicPlanShare | null>(null)
  const [loading, setLoading] = useState(false)
  const [copying, setCopying] = useState(false)
  const [error, setError] = useState('')
  const token = getCurrentInstance().router?.params?.token ?? ''

  useDidShow(() => {
    if (!token) {
      setError('分享链接不完整或已经失效。')
      return
    }
    setLoading(true)
    setError('')
    setShare(null)
    apiRequest<PublicPlanShare>(`/api/v1/plan-shares/${encodeURIComponent(token)}`)
      .then(setShare)
      .catch((cause) => setError(cause instanceof Error ? cause.message : '分享计划读取失败。'))
      .finally(() => setLoading(false))
  })

  const copyAsDraft = async () => {
    if (!token || copying) return
    setCopying(true)
    setError('')
    try {
      let accessToken = store.token
      let principalId = store.principalId
      if (!accessToken) {
        const session = await apiRequest<AnonymousSession>('/api/v1/anonymous-sessions', {
          method: 'POST',
          data: { device_installation_id: `h5_share_${Date.now()}` }
        })
        accessToken = session.access_token
        principalId = session.principal_id
        store.setSession(accessToken, principalId)
      }
      const draft = await apiRequest<Draft>(
        `/api/v1/plan-shares/${encodeURIComponent(token)}/draft-copies`,
        { method: 'POST', token: accessToken }
      )
      store.replacePlan(draft.draft_id, draft.draft_version)
      store.setSelectedAttractions(draft.selected_attraction_ids)
      Taro.redirectTo({ url: '/pages/trip-time/index' })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '暂时无法复制这份计划。')
    } finally {
      setCopying(false)
    }
  }

  return (
    <View className='page-shell plan-share-view-page'>
      <View className='content'>
        <Text className='eyebrow'>SHARED TRIP PLAN</Text>
        <View className='title'>一份杭州出发前计划</View>
        <View className='subtitle'>这是他人分享的计划版本，不代表已经实际到访；开放、天气和交通请在出发前重新确认。</View>

        {loading && <View className='notice'>正在打开分享计划…</View>}
        {error && <View className='error'>{error}</View>}
        {share && (
          <>
            <PlanShareCard content={share.content} />
            <View className='reference-copy-card card'>
              <View className='section-title'>想按这份路线规划自己的行程？</View>
              <View className='field-help'>系统只复制景点集合。你的日期、到达方式、离开方式和旅行节奏仍由你自己确认。</View>
              <Button className='primary reference-copy-button' loading={copying} disabled={copying} onClick={copyAsDraft}>
                以此为参考新建行程
              </Button>
            </View>
          </>
        )}
      </View>
    </View>
  )
}
