import { Button, Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'

export function StepHeader({
  step,
  title,
  backUrl,
  backLabel = '上一步'
}: {
  step: number
  title: string
  backUrl: string
  backLabel?: string
}) {
  const goBack = () => {
    Taro.navigateBack({
      delta: 1,
      fail: () => Taro.redirectTo({ url: backUrl })
    })
  }

  return (
    <View className='step-row'>
      <Button className='step-back' onClick={goBack}>‹ {backLabel}</Button>
      <Text className='eyebrow'>{step}/3 {title}</Text>
      <View className='step-track' aria-label={`步骤 ${step}/3`}>
        <View className='step-fill' style={{ width: `${(step / 3) * 100}%` }} />
      </View>
    </View>
  )
}
