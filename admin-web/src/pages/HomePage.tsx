import { AuditOutlined, DatabaseOutlined, SafetyCertificateOutlined } from '@ant-design/icons'
import { Alert, Card, Col, Row, Space, Statistic, Typography } from 'antd'

export function HomePage() {
  return (
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      <div>
        <Typography.Title level={2}>管理首页</Typography.Title>
        <Typography.Paragraph type="secondary">
          当前切片提供管理身份、角色安全操作和最小审计查询；地点审核工作台将在下一节点接入。
        </Typography.Paragraph>
      </div>
      <Alert
        showIcon
        type="warning"
        title="研究数据尚未发布"
        description="现有 72 个地点均为 candidate，不能描述为 human_verified 或 published；本页不伪造审核通过率、待办量或发布版本。"
      />
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card>
            <Statistic prefix={<DatabaseOutlined />} title="候选地点" value={72} suffix="个" />
            <Typography.Text type="secondary">来自已版本化候选目录，不代表审核通过。</Typography.Text>
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
            <Statistic prefix={<AuditOutlined />} title="当前节点" value="05-01B" />
            <Typography.Text type="secondary">安全操作面，不包含地点审核决定。</Typography.Text>
          </Card>
        </Col>
      </Row>
    </Space>
  )
}
