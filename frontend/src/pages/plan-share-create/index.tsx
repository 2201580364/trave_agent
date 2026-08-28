import { Button, Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useState } from 'react'

import './index.css'

import type { CreatedPlanShare } from '@/entities/planning/types'
import { PlanShareCard } from '@/features/plan-share/PlanShareCard'
import { usePlanningStore } from '@/features/trip-draft/store'
import { apiRequest } from '@/shared/api/client'

function publicLink(share: CreatedPlanShare) {
  if (typeof window === 'undefined') return share.share_path
  const base = window.location.href.split('#')[0]
  return `${base}#${share.share_path}`
}

export default function PlanShareCreatePage() {
  const store = usePlanningStore()
  const [intentId] = useState(() => `share_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`)
  const [share, setShare] = useState<CreatedPlanShare | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const createShare = async () => {
    if (loading) return
    if (!store.token || !store.tripId || !store.revisionId) {
      setError('当前行程信息不完整，请从行程详情重新进入。')
      return
    }
    setLoading(true)
    setError('')
    try {
      const created = await apiRequest<CreatedPlanShare>(
        `/api/v1/trips/${store.tripId}/plan-shares`,
        {
          method: 'POST',
          token: store.token,
          data: {
            plan_share_intent_id: intentId,
            revision_id: store.revisionId,
            template: 'simple'
          }
        }
      )
      setShare(created)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '分享计划生成失败。')
    } finally {
      setLoading(false)
    }
  }

  const copyLink = async () => {
    if (!share) return
    await Taro.setClipboardData({ data: publicLink(share) })
    Taro.showToast({ title: '分享链接已复制', icon: 'success' })
  }

  const openPublicPreview = () => {
    if (!share) return
    Taro.navigateTo({
      url: `/pages/plan-share-view/index?token=${encodeURIComponent(share.share_token)}`
    })
  }

  return (
    <View className='page-shell plan-share-create-page'>
      <View className='content'>
        <Text className='eyebrow'>SHARE THE PLAN</Text>
        <View className='title'>分享这份行程计划</View>
        <View className='subtitle'>分享的是当前版本的只读计划摘要，不会公开你的账号、到离交通详情或私人信息。</View>

        {!share && (
          <View className='card share-safety-card'>
            <View className='section-title'>分享前说明</View>
            <View className='share-safety-list'>
              <View>✓ 固定到当前第 {store.currentRevisionNumber || '—'} 版，不随以后修改漂移</View>
              <View>✓ 只展示日期、每日景点概览和天气参考</View>
              <View>✓ 不展示匿名访问令牌、交通锚点、OD 明细和内部节点 ID</View>
              <View>✓ 访客只能查看或复制为自己的新草稿，不能修改原行程</View>
            </View>
          </View>
        )}

        {error && <View className='error'>{error}</View>}

        {!share && (
          <Button className='primary share-create-button' loading={loading} disabled={loading} onClick={createShare}>
            生成安全分享预览
          </Button>
        )}

        {share && (
          <>
            <View className='notice'>分享对象已生成。以后调整原行程不会改变这张第 {share.content.revision_number} 版计划卡。</View>
            <PlanShareCard content={share.content} />
            <View className='share-actions'>
              <Button className='primary' onClick={copyLink}>复制分享链接</Button>
              <Button className='secondary' onClick={openPublicPreview}>查看访客页面</Button>
            </View>
          </>
        )}
      </View>
    </View>
  )
}
