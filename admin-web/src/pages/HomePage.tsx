import { ArrowRightOutlined, AuditOutlined, CheckCircleOutlined, ClockCircleOutlined, DatabaseOutlined, SafetyCertificateOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Col, Row, Space, Statistic, Tag, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { adminErrorMessage } from '../api/errorMessages'
import type { DashboardSummary } from '../api/types'
import { useAdminSession } from '../auth/AdminSessionProvider'

export function HomePage() {
  const { api } = useAdminSession()
  const navigate = useNavigate()
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { void api.getDashboardSummary().then(setSummary).catch((reason) => setError(adminErrorMessage(reason))) }, [api])
  return (
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      <div className="page-heading-row">
        <div>
          <Typography.Title level={2}>管理首页</Typography.Title>
          <Typography.Paragraph type="secondary">
            掌握杭州地点数据从候选、审核到发布的实时进度。
          </Typography.Paragraph>
        </div>
        <Tag className="page-stage-tag" color="cyan">当前阶段 · G7-R0.2-07</Tag>
      </div>
      <Alert
        showIcon
        type={error ? 'warning' : (summary?.revisions.published ?? 0) > 0 ? 'success' : 'info'}
        title={error ? '数据概览暂不可用' : (summary?.revisions.published ?? 0) > 0 ? '已形成可用的发布目录' : '正在准备首批发布数据'}
        description={error ?? `当前已发布 ${summary?.revisions.published ?? 0} 个地点，审核状态以服务端聚合结果为准。`}
        action={(summary?.revisions.published ?? 0) > 0 ? <Button size="small" onClick={() => navigate('/publications?view=published')}>查看已发布数据</Button> : undefined}
      />
      <Row gutter={[18, 18]} className="dashboard-stat-grid">
        <Col xs={24} md={8}>
          <Card className="dashboard-stat-card dashboard-stat-card--candidate">
            <Statistic prefix={<DatabaseOutlined />} title="候选地点" value={summary?.revisions.candidate ?? 0} suffix="个" />
            <Button type="link" onClick={() => navigate('/candidates')}>进入候选清单 <ArrowRightOutlined /></Button>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card className="dashboard-stat-card dashboard-stat-card--review">
            <Statistic prefix={<SafetyCertificateOutlined />} title="审核待办" value={(summary?.review_tasks.ready_for_review ?? 0) + (summary?.review_tasks.in_review ?? 0)} suffix="个" />
            <Button type="link" onClick={() => navigate('/review')}>进入审核工作台 <ArrowRightOutlined /></Button>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card className="dashboard-stat-card dashboard-stat-card--published">
            <Statistic prefix={<AuditOutlined />} title="已发布" value={summary?.revisions.published ?? 0} suffix="个" />
            <Button type="link" onClick={() => navigate('/publications?view=published')}>查看发布目录 <ArrowRightOutlined /></Button>
          </Card>
        </Col>
      </Row>
      <Card title="审核流转概览" extra={<Button type="link" onClick={() => navigate('/review')}> 查看全部 </Button>}>
        <Space size={[12, 12]} wrap className="workflow-status-list">
          <Tag icon={<ClockCircleOutlined />} color="processing">待审核 {summary?.review_tasks.ready_for_review ?? 0}</Tag>
          <Tag icon={<SafetyCertificateOutlined />} color="cyan">审核中 {summary?.review_tasks.in_review ?? 0}</Tag>
          <Tag icon={<ClockCircleOutlined />} color="warning">待修改 {summary?.review_tasks.changes_requested ?? 0}</Tag>
          <Tag icon={<CheckCircleOutlined />} color="success">已通过 {summary?.review_tasks.approved ?? 0}</Tag>
        </Space>
      </Card>
    </Space>
  )
}
