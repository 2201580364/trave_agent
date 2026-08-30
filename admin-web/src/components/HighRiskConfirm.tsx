import { Input, Modal, Space, Typography } from 'antd'
import { useEffect, useState } from 'react'

type HighRiskConfirmProps = {
  open: boolean
  title: string
  description: string
  confirmationText: string
  loading?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function HighRiskConfirm({
  open,
  title,
  description,
  confirmationText,
  loading = false,
  onConfirm,
  onCancel,
}: HighRiskConfirmProps) {
  const [typed, setTyped] = useState('')

  useEffect(() => {
    if (!open) setTyped('')
  }, [open])

  return (
    <Modal
      open={open}
      title={title}
      okText="确认执行"
      okButtonProps={{ danger: true, disabled: typed !== confirmationText }}
      confirmLoading={loading}
      cancelButtonProps={{ disabled: loading }}
      maskClosable={!loading}
      closable={!loading}
      onOk={onConfirm}
      onCancel={onCancel}
    >
      <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
        <Typography.Paragraph>{description}</Typography.Paragraph>
        <Typography.Text type="secondary">
          请输入 <Typography.Text code>{confirmationText}</Typography.Text> 以确认：
        </Typography.Text>
        <Input
          value={typed}
          autoComplete="off"
          aria-label="高风险操作确认文本"
          onChange={(event) => setTyped(event.target.value)}
        />
      </Space>
    </Modal>
  )
}
