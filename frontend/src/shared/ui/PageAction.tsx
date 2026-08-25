import { Button, View } from '@tarojs/components'
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
  return (
    <View className='action-bar'>
      <View className='action-inner'>
        <Button className='primary' disabled={disabled || loading} loading={loading} onClick={onClick}>
          {children}
        </Button>
      </View>
    </View>
  )
}
