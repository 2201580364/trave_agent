import { Alert } from 'antd'

export function ErrorNotice({ message, onClose }: { message: string; onClose?: () => void }) {
  return (
    <Alert
      type="error"
      showIcon
      closable={onClose !== undefined}
      onClose={onClose}
      message="操作未完成"
      description={message}
    />
  )
}
