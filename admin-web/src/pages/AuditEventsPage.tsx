import { ReloadOutlined, SearchOutlined } from '@ant-design/icons'
import {
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  type TableColumnsType,
} from 'antd'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { adminErrorMessage } from '../api/errorMessages'
import type { AdminAuditEvent, AdminAuditResult, AuditEventFilters } from '../api/types'
import { useAdminSession } from '../auth/AdminSessionProvider'
import { ErrorNotice } from '../components/ErrorNotice'

const PAGE_SIZE = 50

type FilterFields = {
  actor_id?: string
  target_type?: string
  target_id?: string
  action?: string
  result?: AdminAuditResult
}

export function AuditEventsPage() {
  const { api } = useAdminSession()
  const [searchParams, setSearchParams] = useSearchParams()
  const [form] = Form.useForm<FilterFields>()
  const [events, setEvents] = useState<AdminAuditEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const filters = useMemo<AuditEventFilters>(() => {
    const result = searchParams.get('result')
    return {
      actor_id: searchParams.get('actor_id') || undefined,
      target_type: searchParams.get('target_type') || undefined,
      target_id: searchParams.get('target_id') || undefined,
      action: searchParams.get('action') || undefined,
      result:
        result === 'succeeded' || result === 'rejected' || result === 'failed'
          ? result
          : undefined,
      limit: PAGE_SIZE,
      offset: Math.max(0, Number(searchParams.get('offset')) || 0),
    }
  }, [searchParams])

  const loadEvents = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.listAuditEvents(filters)
      setEvents(response.items)
    } catch (reason) {
      setError(adminErrorMessage(reason))
    } finally {
      setLoading(false)
    }
  }, [api, filters])

  useEffect(() => {
    form.setFieldsValue({
      actor_id: filters.actor_id,
      target_type: filters.target_type,
      target_id: filters.target_id,
      action: filters.action,
      result: filters.result,
    })
    void loadEvents()
  }, [filters, form, loadEvents])

  const applyFilters = (values: FilterFields) => {
    const next = new URLSearchParams()
    Object.entries(values).forEach(([key, value]) => {
      const normalized = value?.trim()
      if (normalized) next.set(key, normalized)
    })
    setSearchParams(next)
  }

  const resetFilters = () => {
    form.resetFields()
    setSearchParams(new URLSearchParams())
  }

  const movePage = (offset: number) => {
    const next = new URLSearchParams(searchParams)
    if (offset <= 0) next.delete('offset')
    else next.set('offset', String(offset))
    setSearchParams(next)
  }

  const columns = useMemo<TableColumnsType<AdminAuditEvent>>(
    () => [
      {
        title: '时间',
        dataIndex: 'occurred_at',
        width: 190,
        render: formatDateTime,
      },
      {
        title: '结果',
        dataIndex: 'result',
        width: 100,
        render: (result: AdminAuditResult) => (
          <Tag color={result === 'succeeded' ? 'success' : result === 'rejected' ? 'warning' : 'error'}>
            {result === 'succeeded' ? '成功' : result === 'rejected' ? '拒绝' : '失败'}
          </Tag>
        ),
      },
      {
        title: '操作者',
        dataIndex: 'actor_id',
        width: 180,
        ellipsis: true,
      },
      {
        title: '动作',
        dataIndex: 'action',
        width: 230,
        render: (value: string) => <Typography.Text code>{value}</Typography.Text>,
      },
      {
        title: '目标',
        key: 'target',
        width: 260,
        render: (_, event) => `${event.target_type} / ${event.target_id}`,
      },
      {
        title: '理由代码',
        dataIndex: 'reason_code',
        width: 220,
        render: (value: string) => <Typography.Text code>{value}</Typography.Text>,
      },
      {
        title: '请求 ID',
        dataIndex: 'request_id',
        width: 220,
        ellipsis: true,
      },
    ],
    [],
  )

  const offset = filters.offset ?? 0

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div className="page-heading-row">
        <div>
          <Typography.Title level={2}>审计中心</Typography.Title>
          <Typography.Paragraph type="secondary">
            O15 最小只读面 · 展示管理身份和安全操作审计，不提供编辑或删除能力。
          </Typography.Paragraph>
        </div>
        <Button icon={<ReloadOutlined />} onClick={() => void loadEvents()} loading={loading}>
          刷新
        </Button>
      </div>
      {error !== null && <ErrorNotice message={error} onClose={() => setError(null)} />}
      <Card>
        <Form<FilterFields>
          form={form}
          layout="inline"
          className="audit-filters"
          onFinish={applyFilters}
        >
          <Form.Item name="actor_id" label="操作者">
            <Input allowClear placeholder="actor_id" />
          </Form.Item>
          <Form.Item name="action" label="动作">
            <Input allowClear placeholder="ADMIN_…" />
          </Form.Item>
          <Form.Item name="target_type" label="目标类型">
            <Input allowClear />
          </Form.Item>
          <Form.Item name="target_id" label="目标 ID">
            <Input allowClear />
          </Form.Item>
          <Form.Item name="result" label="结果">
            <Select
              allowClear
              style={{ width: 120 }}
              options={[
                { value: 'succeeded', label: '成功' },
                { value: 'rejected', label: '拒绝' },
                { value: 'failed', label: '失败' },
              ]}
            />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" icon={<SearchOutlined />}>
                查询
              </Button>
              <Button onClick={resetFilters}>清空</Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
      <Card>
        <Table<AdminAuditEvent>
          rowKey="audit_event_id"
          columns={columns}
          dataSource={events}
          loading={loading}
          pagination={false}
          scroll={{ x: 1400 }}
          locale={{ emptyText: '当前筛选条件下没有审计事件' }}
          expandable={{ expandedRowRender: (event) => <AuditDetails event={event} /> }}
        />
        <div className="manual-pagination">
          <Typography.Text type="secondary">
            第 {Math.floor(offset / PAGE_SIZE) + 1} 页 · 本页 {events.length} 条
          </Typography.Text>
          <Space>
            <Button disabled={offset === 0 || loading} onClick={() => movePage(offset - PAGE_SIZE)}>
              上一页
            </Button>
            <Button
              disabled={events.length < PAGE_SIZE || loading}
              onClick={() => movePage(offset + PAGE_SIZE)}
            >
              下一页
            </Button>
          </Space>
        </div>
      </Card>
    </Space>
  )
}

function AuditDetails({ event }: { event: AdminAuditEvent }) {
  return (
    <Descriptions bordered size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
      <Descriptions.Item label="审计事件 ID">{event.audit_event_id}</Descriptions.Item>
      <Descriptions.Item label="操作者角色">{event.actor_role}</Descriptions.Item>
      <Descriptions.Item label="目标 Revision">{event.target_revision ?? '—'}</Descriptions.Item>
      <Descriptions.Item label="操作意图 ID">{event.operation_intent_id ?? '—'}</Descriptions.Item>
      <Descriptions.Item label="错误代码">{event.error_code ?? '—'}</Descriptions.Item>
      <Descriptions.Item label="理由说明">{event.reason_text ?? '—'}</Descriptions.Item>
      <Descriptions.Item label="Before digest">
        <Digest value={event.before_digest} />
      </Descriptions.Item>
      <Descriptions.Item label="After digest">
        <Digest value={event.after_digest} />
      </Descriptions.Item>
    </Descriptions>
  )
}

function Digest({ value }: { value: string | null }) {
  return value === null ? (
    <>—</>
  ) : (
    <Typography.Text code copyable={{ text: value }}>
      {value.slice(0, 16)}…
    </Typography.Text>
  )
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'medium',
    hour12: false,
  }).format(new Date(value))
}
