import {
  AuditOutlined,
  DashboardOutlined,
  LogoutOutlined,
  SafetyCertificateOutlined,
  TeamOutlined,
} from '@ant-design/icons'
import { Button, Layout, Menu, Space, Tag, Typography } from 'antd'
import { useMemo } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'

import { useAdminSession } from '../auth/AdminSessionProvider'

const { Header, Sider, Content } = Layout

export function AdminLayout() {
  const { principal, hasPermission, logout } = useAdminSession()
  const navigate = useNavigate()
  const location = useLocation()
  const menuItems = useMemo(
    () => [
      { key: '/', icon: <DashboardOutlined />, label: '管理首页' },
      ...(hasPermission('admin:actor:read')
        ? [{ key: '/administrators', icon: <TeamOutlined />, label: '管理员与角色' }]
        : []),
      ...(hasPermission('admin:audit:read')
        ? [{ key: '/audit', icon: <AuditOutlined />, label: '审计中心' }]
        : []),
    ],
    [hasPermission],
  )

  return (
    <Layout className="admin-shell">
      <Sider breakpoint="lg" collapsedWidth="0" theme="dark" className="admin-sider">
        <div className="admin-brand">
          <SafetyCertificateOutlined />
          <span>旅行助手管理台</span>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header className="admin-header">
          <Space size="small" wrap>
            <Tag color="green">受控研究环境</Tag>
            <Tag>M1 / OM1</Tag>
            <Typography.Text type="secondary">杭州 · candidate 数据阶段</Typography.Text>
          </Space>
          <Space size="middle" wrap>
            <Typography.Text>{principal?.login_name}</Typography.Text>
            <Button icon={<LogoutOutlined />} onClick={() => void logout()}>
              安全退出
            </Button>
          </Space>
        </Header>
        <Content className="admin-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
