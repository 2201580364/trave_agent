import { Text, View } from '@tarojs/components'

export function StepHeader({ step, title }: { step: number; title: string }) {
  return (
    <View className='step-row'>
      <Text className='eyebrow'>{step}/3 {title}</Text>
      <View className='step-track' aria-label={`步骤 ${step}/3`}>
        <View className='step-fill' style={{ width: `${(step / 3) * 100}%` }} />
      </View>
    </View>
  )
}
