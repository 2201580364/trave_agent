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
  const isDisabled = Boolean(disabled || loading)
  return (
    <View className='action-bar'>
      <View className='action-inner'>
        <Button
          className={`primary ${isDisabled ? 'primary--disabled' : ''}`}
          disabled={isDisabled}
          loading={loading}
          aria-disabled={isDisabled}
          onClick={() => {
            if (!isDisabled) onClick()
          }}
        >
          {children}
        </Button>
      </View>
    </View>
  )
}
