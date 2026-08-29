import { Button, Result } from 'antd'
import { useNavigate } from 'react-router-dom'

export function NotFoundPage() {
  const navigate = useNavigate()
  return (
    <Result
      status="404"
      title="页面不存在"
      subTitle="该管理页面尚未开放，或地址不正确。"
      extra={<Button onClick={() => navigate('/')}>返回管理首页</Button>}
    />
  )
}
