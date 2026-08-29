import { ReloadOutlined } from '@ant-design/icons'
import { Button, Card, Descriptions, Space, Table, Tag, Typography } from 'antd'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { adminErrorMessage } from '../api/errorMessages'
import type { PlaceRevision } from '../api/types'
import { useAdminSession } from '../auth/AdminSessionProvider'
import { ErrorNotice } from '../components/ErrorNotice'

export function CandidatesPage() {
  const { api } = useAdminSession()
  const [items, setItems] = useState<PlaceRevision[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.listCandidates()
      setItems(result.items)
    } catch (reason) {
      setError(adminErrorMessage(reason))
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => {
    void load()
  }, [load])

  const columns = useMemo(
    () => [
      { title: '名称', dataIndex: 'canonical_name', width: 220, ellipsis: true },
      { title: '区域', dataIndex: 'admin_area', width: 150 },
      { title: '类型', dataIndex: 'place_kind', width: 130 },
      { title: '建议时长', dataIndex: 'duration_recommended', width: 120, render: (v: number) => `${v} 分钟` },
      {
        title: '状态',
        dataIndex: 'lifecycle_status',
        width: 120,
        render: (v: PlaceRevision['lifecycle_status']) => <Tag>{v}</Tag>,
      },
      { title: '创建时间', dataIndex: 'created_at', width: 210, render: formatDateTime },
    ],
    [],
  )

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div className="page-heading-row">
        <div>
          <Typography.Title level={2}>候选地点清单</Typography.Title>
          <Typography.Paragraph type="secondary">
            O02：只读查看 candidate Revision 的基础事实，审核和发布必须通过对应工作流。
          </Typography.Paragraph>
        </div>
        <Button icon={<ReloadOutlined />} onClick={() => void load()} loading={loading}>
          刷新
        </Button>
      </div>
      {error !== null && <ErrorNotice message={error} onClose={() => setError(null)} />}
      <Card>
        <Table<PlaceRevision>
          rowKey="place_revision_id"
          columns={columns}
          dataSource={items}
          loading={loading}
          pagination={false}
          scroll={{ x: 950 }}
          expandable={{ expandedRowRender: (revision) => <RevisionDetails revision={revision} /> }}
          locale={{ emptyText: '当前没有 candidate Revision' }}
        />
      </Card>
    </Space>
  )
}

function RevisionDetails({ revision }: { revision: PlaceRevision }) {
  return (
    <Descriptions bordered size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
      <Descriptions.Item label="Revision ID">{revision.place_revision_id}</Descriptions.Item>
      <Descriptions.Item label="Place ID">{revision.place_id}</Descriptions.Item>
      <Descriptions.Item label="地址">{revision.address ?? '未提供'}</Descriptions.Item>
      <Descriptions.Item label="游览范围">
        {revision.duration_min} - {revision.duration_max} 分钟
      </Descriptions.Item>
      <Descriptions.Item label="室内/室外">{revision.indoor_outdoor}</Descriptions.Item>
      <Descriptions.Item label="雨天适配">{revision.rain_suitability}</Descriptions.Item>
      <Descriptions.Item label="来源记录数">{revision.source_record_ids.length}</Descriptions.Item>
      <Descriptions.Item label="冲突已裁决">{revision.conflicts_resolved ? '是' : '否'}</Descriptions.Item>
      <Descriptions.Item label="求解器可用">{revision.solver_eligible ? '是' : '否'}</Descriptions.Item>
    </Descriptions>
  )
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'medium',
    hour12: false,
  }).format(new Date(value))
}
