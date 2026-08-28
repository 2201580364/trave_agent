import { Text, View } from '@tarojs/components'

import './PlanShareCard.css'

import type { PlanShareContent } from '@/entities/planning/types'

function periodLabel(period: string) {
  if (period === 'morning') return '上午'
  if (period === 'afternoon') return '下午'
  return '晚上'
}

function durationLabel(value: number | null) {
  if (!value) return ''
  if (value <= 30) return '约半小时'
  if (value <= 60) return '约 1 小时'
  if (value <= 90) return '约 1–1.5 小时'
  if (value <= 120) return '约 2 小时'
  return `约 ${Math.round(value / 30) / 2} 小时`
}

function dateRange(content: PlanShareContent) {
  if (!content.start_date || !content.end_date) return '日期待确认'
  return content.start_date === content.end_date
    ? content.start_date
    : `${content.start_date} 至 ${content.end_date}`
}

export function PlanShareCard({ content }: { content: PlanShareContent }) {
  return (
    <View className='plan-share-card'>
      <View className='plan-share-card__hero'>
        <Text className='plan-share-card__eyebrow'>TRIP PLAN · 出发前计划</Text>
        <View className='plan-share-card__title'>{content.title}</View>
        <View className='plan-share-card__date'>{dateRange(content)}</View>
        <View className='plan-share-card__metrics'>
          <View><Text>{content.days.length}</Text><Text>天</Text></View>
          <View><Text>{content.scheduled_count}</Text><Text>项安排</Text></View>
          <View><Text>{content.revision_number}</Text><Text>计划版本</Text></View>
        </View>
      </View>

      <View className='plan-share-card__days'>
        {content.days.map((day, index) => (
          <View key={day.date} className='plan-share-day'>
            <View className='plan-share-day__heading'>
              <View className='plan-share-day__index'>DAY {index + 1}</View>
              <View className='plan-share-day__date'>{day.date}</View>
            </View>
            {day.weather.condition && (
              <View className='plan-share-day__weather'>天气参考：{day.weather.condition}</View>
            )}
            <View className='plan-share-day__items'>
              {day.items.map((item, itemIndex) => (
                <View key={`${item.name}-${itemIndex}`} className='plan-share-item'>
                  <View className='plan-share-item__period'>
                    {item.fixed_time ?? periodLabel(item.period)}
                  </View>
                  <View className='plan-share-item__body'>
                    <View className='plan-share-item__name'>{item.name}</View>
                    <View className='plan-share-item__meta'>
                      {item.timing_kind === 'fixed_event' ? '固定场次' : periodLabel(item.period)}
                      {durationLabel(item.duration_min) ? ` · ${durationLabel(item.duration_min)}` : ''}
                    </View>
                  </View>
                </View>
              ))}
              {!day.items.length && <View className='plan-share-empty'>当天暂无景点安排</View>}
            </View>
          </View>
        ))}
      </View>

      <View className='plan-share-card__footer'>
        <View>{content.data_notice}</View>
        <View className='plan-share-card__privacy'>{content.privacy_notice}</View>
      </View>
    </View>
  )
}
