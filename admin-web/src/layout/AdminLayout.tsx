import {
  AuditOutlined,
  CalendarOutlined,
  CheckSquareOutlined,
  CloudUploadOutlined,
  DatabaseOutlined,
  DashboardOutlined,
  EnvironmentOutlined,
  ExperimentOutlined,
  LogoutOutlined,
  SafetyCertificateOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { Avatar, Button, Layout, Menu, Space, Tag, Typography } from 'antd'
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
      ...(hasPermission('place:review:read')
        ? [{ key: '/review', icon: <CheckSquareOutlined />, label: '地点审核' }]
        : []),
      ...(hasPermission('place:publication:check')
        ? [{ key: '/publications', icon: <CloudUploadOutlined />, label: '发布中心' }]
        : []),
      ...(hasPermission('place:candidate:read')
        ? [{ key: '/candidates', icon: <DatabaseOutlined />, label: '候选地点' }]
        : []),
      ...(hasPermission('holiday:calendar:read')
        ? [{ key: '/holiday-calendars', icon: <CalendarOutlined />, label: '节假日历' }]
        : []),
    ],
    [hasPermission],
  )
  const selectedKey = location.pathname.startsWith('/candidates/')
    ? '/candidates'
    : location.pathname
  const currentLabel = menuItems.find((item) => item.key === selectedKey)?.label ?? '管理控制台'

  return (
    <Layout className="admin-shell">
      <Sider breakpoint="lg" collapsedWidth="0" theme="dark" className="admin-sider">
        <div className="admin-brand">
          <span className="admin-brand-mark"><SafetyCertificateOutlined /></span>
          <span className="admin-brand-copy">
            <strong>旅行助手</strong>
            <small>数据治理控制台</small>
          </span>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
        <div className="admin-sider-footer">
          <ExperimentOutlined />
          <span>
            <strong>OM1 受控环境</strong>
            <small>操作全程记录审计</small>
          </span>
        </div>
      </Sider>
      <Layout>
        <Header className="admin-header">
          <div className="admin-header-context">
            <Typography.Text type="secondary">管理工作台</Typography.Text>
            <Typography.Text strong>{currentLabel}</Typography.Text>
          </div>
          <Space size="middle" className="admin-header-actions">
            <Space size="small" className="admin-environment-meta">
              <Tag icon={<EnvironmentOutlined />} color="cyan">杭州</Tag>
              <Tag color="green">M1 / OM1</Tag>
            </Space>
            <span className="admin-account">
              <Avatar size={34} icon={<UserOutlined />} />
              <span>
                <Typography.Text strong>{principal?.login_name}</Typography.Text>
                <Typography.Text type="secondary">已登录管理员</Typography.Text>
              </span>
            </span>
            <Button className="admin-logout" icon={<LogoutOutlined />} onClick={() => void logout()}>
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
