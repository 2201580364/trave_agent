import { Text, View } from '@tarojs/components'
import Taro, { useRouter } from '@tarojs/taro'
import { useState } from 'react'

import './index.css'

import type { AnonymousSession, Draft } from '@/entities/planning/types'
import { usePlanningStore } from '@/features/trip-draft/store'
import { apiRequest, errorMessageForCode } from '@/shared/api/client'

export default function AuthPage() {
  const expired = useRouter().params.expired === '1'
  const store = usePlanningStore()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const enter = async () => {
    setLoading(true)
    setError('')
    try {
      const session = await apiRequest<AnonymousSession>('/api/v1/anonymous-sessions', {
        method: 'POST',
        data: { device_installation_id: `h5_${Date.now()}` }
      })
      store.setSession(session.access_token, session.principal_id)
      const draft = await apiRequest<Draft>('/api/v1/trip-drafts', {
        method: 'POST',
        token: session.access_token,
        data: { city_id: 'hangzhou' }
      })
      store.replacePlan(draft.draft_id, draft.draft_version)
      Taro.navigateTo({ url: '/pages/trip-time/index' })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '暂时无法进入旅行助手。')
    } finally {
      setLoading(false)
    }
  }

  return (
    <View className='page-shell auth-page'>
      <View className='content'>
        <Text className='eyebrow'>YOUR HANGZHOU COMPANION</Text>
        <View className='auth-orb'>杭</View>
        <View className='title'>登录旅行助手</View>
        <View className='subtitle'>保存你的行程，从上次规划的位置继续。</View>
        <View className='card auth-card'>
          {expired && <View className='notice'>{errorMessageForCode('authentication_required')}</View>}
          <View className='section-title'>轻松开始，不必先填表</View>
          <View className='field-help'>当前版本使用游客身份登录，设备会保存你的规划进度；账号注册功能将在正式账号体系接入后开放。</View>
          <View className={`primary auth-primary ${loading ? 'primary--disabled' : ''}`} onClick={() => !loading && enter()}>
            {loading ? '正在进入…' : '游客登录并开始'}
          </View>
        </View>
        {error && <View className='error'>{error}</View>}
        <View className='secondary auth-back' onClick={() => Taro.navigateBack()}>返回首页</View>
      </View>
    </View>
  )
}
