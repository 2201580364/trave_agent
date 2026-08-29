import { LockOutlined, SafetyCertificateOutlined, UserOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Form, Input, Space, Typography } from 'antd'
import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

import { adminErrorMessage } from '../api/errorMessages'
import { useAdminSession } from '../auth/AdminSessionProvider'

type LoginFields = { login_name: string; password: string }

export function LoginPage() {
  const { principal, sessionReason, login } = useAdminSession()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  if (principal !== null) return <Navigate to="/" replace />

  const submit = async (values: LoginFields) => {
    setSubmitting(true)
    setError(null)
    try {
      await login(values.login_name, values.password)
      navigate(from, { replace: true })
    } catch (reason) {
      setError(adminErrorMessage(reason))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <Card className="login-card" bordered={false}>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div className="login-heading">
            <SafetyCertificateOutlined className="login-mark" />
            <div>
              <Typography.Title level={2}>管理控制台</Typography.Title>
              <Typography.Text type="secondary">独立身份 · 最小权限 · 全程审计</Typography.Text>
            </div>
          </div>
          {sessionReason === 'expired' && (
            <Alert showIcon type="warning" message="会话已到期，请重新登录。" />
          )}
          {sessionReason === 'signed-out' && (
            <Alert showIcon type="success" message="已安全退出管理会话。" />
          )}
          {error !== null && <Alert showIcon type="error" message={error} />}
          <Form<LoginFields> layout="vertical" requiredMark={false} onFinish={submit}>
            <Form.Item
              name="login_name"
              label="管理员登录名"
              rules={[{ required: true, min: 3, max: 64, message: '请输入有效管理员登录名' }]}
            >
              <Input prefix={<UserOutlined />} autoComplete="username" size="large" />
            </Form.Item>
            <Form.Item
              name="password"
              label="密码"
              rules={[{ required: true, min: 14, max: 256, message: '密码至少 14 位' }]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                autoComplete="current-password"
                size="large"
              />
            </Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              size="large"
              block
              loading={submitting}
            >
              登录受控环境
            </Button>
          </Form>
          <Typography.Paragraph type="secondary" className="security-note">
            管理会话只保存在当前页面内存中；刷新页面后需要重新登录。请勿在理由字段中填写密码、Token、API Key 或私钥。
          </Typography.Paragraph>
        </Space>
      </Card>
    </main>
  )
}
