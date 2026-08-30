import { AuditOutlined, DatabaseOutlined, SafetyCertificateOutlined } from '@ant-design/icons'
import { Alert, Card, Col, Row, Space, Statistic, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { adminErrorMessage } from '../api/errorMessages'
import type { DashboardSummary } from '../api/types'
import { useAdminSession } from '../auth/AdminSessionProvider'

export function HomePage() {
  const { api } = useAdminSession()
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { void api.getDashboardSummary().then(setSummary).catch((reason) => setError(adminErrorMessage(reason))) }, [api])
  return (
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      <div>
        <Typography.Title level={2}>管理首页</Typography.Title>
        <Typography.Paragraph type="secondary">
          研究数据治理与受控发布概览。
        </Typography.Paragraph>
      </div>
      <Alert
        showIcon
        type="warning"
        title="研究数据尚未发布"
        description={error ?? '统计来自当前数据库，审核状态以服务端聚合结果为准。'}
      />
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card>
            <Statistic prefix={<DatabaseOutlined />} title="候选地点" value={summary?.revisions.candidate ?? 0} suffix="个" />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic prefix={<SafetyCertificateOutlined />} title="管理里程碑" value="OM1" />
            <Typography.Text type="secondary">研究数据治理与受控发布。</Typography.Text>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic prefix={<AuditOutlined />} title="已发布" value={summary?.revisions.published ?? 0} suffix="个" />
          </Card>
        </Col>
      </Row>
      <Card title="审核待办"><Typography.Text>待审核 {summary?.review_tasks.ready_for_review ?? 0} 个，审核中 {summary?.review_tasks.in_review ?? 0} 个，需修改 {summary?.review_tasks.changes_requested ?? 0} 个。</Typography.Text></Card>
    </Space>
  )
}
