import { Button, Picker, Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useState } from 'react'

import type { Draft } from '@/entities/planning/types'
import { usePlanningStore } from '@/features/trip-draft/store'
import { apiRequest } from '@/shared/api/client'
import { PageAction } from '@/shared/ui/PageAction'
import { StepHeader } from '@/shared/ui/StepHeader'

const transportOptions = [
  ['already_in_destination', '已在杭州'],
  ['high_speed_rail', '高铁'],
  ['flight', '飞机'],
  ['self_drive', '自驾']
] as const

function dateAfter(days: number) {
  const value = new Date()
  value.setDate(value.getDate() + days)
  return value.toISOString().slice(0, 10)
}

export default function TripTimePage() {
  const store = usePlanningStore()
  const [startDate, setStartDate] = useState(dateAfter(14))
  const [endDate, setEndDate] = useState(dateAfter(16))
  const [arrivalTime, setArrivalTime] = useState('09:00')
  const [departureTime, setDepartureTime] = useState('18:00')
  const [transport, setTransport] = useState('already_in_destination')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const submit = async () => {
    if (!store.token || !store.draftId) return
    setLoading(true)
    setError('')
    try {
      const local = transport === 'already_in_destination'
      const draft = await apiRequest<Draft>(
        `/api/v1/trip-drafts/${store.draftId}/travel-facts`,
        {
          method: 'PATCH',
          token: store.token,
          data: {
            expected_draft_version: store.draftVersion,
            start_date: startDate,
            end_date: endDate,
            arrival: {
              transport_type: transport,
              confirmation: 'confirmed',
              arrives_at: `${startDate}T${arrivalTime}:00+08:00`,
              station_to_city_min: local ? 0 : 45,
              station_to_city_source: local ? 'not_applicable' : 'system_default'
            },
            departure: {
              transport_type: transport,
              confirmation: 'confirmed_by_inheritance',
              departs_at: `${endDate}T${departureTime}:00+08:00`,
              station_early_min: local ? 0 : 45,
              station_early_source: local ? 'not_applicable' : 'system_default',
              last_visit_to_station_min: local ? 0 : 40,
              last_visit_to_station_source: local ? 'not_applicable' : 'system_default'
            },
            travel_mode: 'normal',
            crowd_type: 'unspecified'
          }
        }
      )
      store.setDraftVersion(draft.draft_version)
      Taro.navigateTo({ url: '/pages/attraction-select/index' })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '保存旅行时间失败。')
    } finally {
      setLoading(false)
    }
  }

  return (
    <View className='page-shell'>
      <View className='content'>
        <StepHeader step={1} title='什么时候去' />
        <View className='title'>先确定旅行边界</View>
        <View className='subtitle'>只需要确认日期、到达和返程，其余时间预留由系统先给出稳妥默认值。</View>

        <View className='card'>
          <View className='section-title'>旅行日期</View>
          <View className='date-grid'>
            <View className='field'>
              <Text className='field-label'>开始日期</Text>
              <Picker mode='date' value={startDate} onChange={(event) => setStartDate(event.detail.value)}>
                <View className='picker'>{startDate}</View>
              </Picker>
            </View>
            <View className='field'>
              <Text className='field-label'>结束日期</Text>
              <Picker mode='date' value={endDate} onChange={(event) => setEndDate(event.detail.value)}>
                <View className='picker'>{endDate}</View>
              </Picker>
            </View>
          </View>
        </View>

        <View className='card'>
          <View className='section-title'>怎样到杭州</View>
          <View className='choice-grid field'>
            {transportOptions.map(([value, label]) => (
              <Button key={value} className={`choice ${transport === value ? 'choice--active' : ''}`} onClick={() => setTransport(value)}>
                {transport === value ? '✓ ' : ''}{label}
              </Button>
            ))}
          </View>
          <View className='field'>
            <Text className='field-label'>{transport === 'already_in_destination' ? '第一天几点可以开始' : '几点到达'}</Text>
            <Picker mode='time' value={arrivalTime} onChange={(event) => setArrivalTime(event.detail.value)}>
              <View className='picker'>{arrivalTime}</View>
            </Picker>
          </View>
        </View>

        <View className='card'>
          <View className='section-title'>返程安排</View>
          <View className='notice'>返程方式沿用到达方式：{transportOptions.find(([value]) => value === transport)?.[1]}</View>
          <View className='field'>
            <Text className='field-label'>{transport === 'already_in_destination' ? '最后一天几点结束' : '几点离开杭州'}</Text>
            <Picker mode='time' value={departureTime} onChange={(event) => setDepartureTime(event.detail.value)}>
              <View className='picker'>{departureTime}</View>
            </Picker>
          </View>
          <View className='field-help'>非本地出发时默认预留 45 分钟进城、45 分钟提前到站和 40 分钟末景返程。</View>
        </View>

        {error && <View className='error'>{error}</View>}
      </View>
      <PageAction loading={loading} disabled={!startDate || !endDate} onClick={submit}>选择想去的景点</PageAction>
    </View>
  )
}
