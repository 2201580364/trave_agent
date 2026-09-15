import { Text, View } from '@tarojs/components'
import type { PropsWithChildren } from 'react'

export function PageAction({
  children,
  disabled,
  loading,
  onClick
}: PropsWithChildren<{
  disabled?: boolean
  loading?: boolean
  onClick: () => void
}>) {
  const isDisabled = Boolean(disabled || loading)
  return (
    <View className='action-bar'>
      <View className='action-inner'>
        <View
          className={`primary ${isDisabled ? 'primary--disabled' : ''}`}
          aria-disabled={isDisabled}
          onClick={() => { if (!isDisabled) onClick() }}
        >
          <Text>{loading ? '处理中…' : children}</Text>
        </View>
      </View>
    </View>
  )
}
