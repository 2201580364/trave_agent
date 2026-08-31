import { FileSearchOutlined, ReloadOutlined } from '@ant-design/icons'
import { Button, Card, Descriptions, Space, Table, Tag, Typography } from 'antd'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { adminErrorMessage } from '../api/errorMessages'
import type { PlaceRevision } from '../api/types'
import { useAdminSession } from '../auth/AdminSessionProvider'
import { ErrorNotice } from '../components/ErrorNotice'
import { indoorOutdoorLabel, lifecycleStatusLabel, placeKindLabel, rainSuitabilityLabel } from '../ui/displayLabels'

const PAGE_SIZE = 20
const PAGE_SIZE_OPTIONS = [20, 50, 100]

export function CandidatesPage() {
  const { api } = useAdminSession()
  const navigate = useNavigate()
  const [items, setItems] = useState<PlaceRevision[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE)
  const [total, setTotal] = useState(0)

  const load = useCallback(async (requestedPage: number, requestedPageSize: number) => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.listCandidates(
        'candidate',
        requestedPageSize,
        (requestedPage - 1) * requestedPageSize,
      )
      setItems(result.items)
      setTotal(result.total ?? result.items.length)
    } catch (reason) {
      setError(adminErrorMessage(reason))
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => {
    void load(page, pageSize)
  }, [load, page, pageSize])

  const refresh = () => {
    setPage(1)
    setPageSize(PAGE_SIZE)
    void load(1, PAGE_SIZE)
  }

  const columns = useMemo(
    () => [
      { title: '名称', dataIndex: 'canonical_name', width: 220, ellipsis: true },
      { title: '区域', dataIndex: 'admin_area', width: 150 },
      { title: '类型', dataIndex: 'place_kind', width: 130, render: placeKindLabel },
      {
        title: '建议时长',
        dataIndex: 'duration_recommended',
        width: 120,
        render: (value: number, revision: PlaceRevision) =>
          revision.review_flags.includes('DURATION_NOT_COLLECTED') ? '未采集' : `${value} 分钟`,
      },
      {
        title: '状态',
        dataIndex: 'lifecycle_status',
        width: 120,
        render: (v: PlaceRevision['lifecycle_status']) => <Tag>{lifecycleStatusLabel(v)}</Tag>,
      },
      { title: '创建时间', dataIndex: 'created_at', width: 210, render: formatDateTime },
      {
        title: '操作',
        key: 'actions',
        width: 130,
        render: (_: unknown, revision: PlaceRevision) => (
          <Button
            type="link"
            icon={<FileSearchOutlined />}
            onClick={() => navigate(`/candidates/${encodeURIComponent(revision.place_revision_id)}`)}
          >
            查看详情
          </Button>
        ),
      },
    ],
    [navigate],
  )

  return (
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      <div className="page-heading-row">
        <div>
          <Typography.Title level={2}>候选地点清单</Typography.Title>
          <Typography.Paragraph type="secondary">
            O02：查看候选修订版本的基础事实；审核和发布必须通过对应工作流。
          </Typography.Paragraph>
        </div>
        <Space wrap>
          <Typography.Text type="secondary">共 {total} 条</Typography.Text>
          <Button icon={<ReloadOutlined />} onClick={refresh} loading={loading}>
            刷新
          </Button>
        </Space>
      </div>
      {error !== null && <ErrorNotice message={error} onClose={() => setError(null)} />}
      <Card>
        <Table<PlaceRevision>
          rowKey="place_revision_id"
          columns={columns}
          dataSource={items}
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            pageSizeOptions: PAGE_SIZE_OPTIONS,
            showTotal: (total, range) => `${range[0]}-${range[1]} / 共 ${total} 条`,
            onChange: (nextPage, nextPageSize) => {
              setPage(nextPageSize === pageSize ? nextPage : 1)
              setPageSize(nextPageSize)
            },
          }}
          scroll={{ x: 1080 }}
          expandable={{ expandedRowRender: (revision) => <RevisionDetails revision={revision} /> }}
          locale={{ emptyText: '当前没有候选修订版本' }}
        />
      </Card>
    </Space>
  )
}

function RevisionDetails({ revision }: { revision: PlaceRevision }) {
  return (
    <Descriptions bordered size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
      <Descriptions.Item label="修订版本编号">{revision.place_revision_id}</Descriptions.Item>
      <Descriptions.Item label="地点编号">{revision.place_id}</Descriptions.Item>
      <Descriptions.Item label="地址">{revision.address ?? '未提供'}</Descriptions.Item>
      <Descriptions.Item label="游览范围">
        {revision.review_flags.includes('DURATION_NOT_COLLECTED')
          ? '未采集'
          : `${revision.duration_min} - ${revision.duration_max} 分钟`}
      </Descriptions.Item>
      <Descriptions.Item label="室内/室外">{indoorOutdoorLabel(revision.indoor_outdoor)}</Descriptions.Item>
      <Descriptions.Item label="雨天适配">{rainSuitabilityLabel(revision.rain_suitability)}</Descriptions.Item>
      <Descriptions.Item label="来源记录数">{revision.source_record_ids.length}</Descriptions.Item>
      <Descriptions.Item label="冲突已裁决">{revision.conflicts_resolved ? '是' : '否'}</Descriptions.Item>
      <Descriptions.Item label="求解器可用">{revision.solver_eligible ? '是' : '否'}</Descriptions.Item>
      <Descriptions.Item label="待核验项" span={3}>
        {revision.review_flags.length > 0
          ? revision.review_flags.map((flag) => <Tag key={flag} color="warning">{reviewFlagLabel(flag)}</Tag>)
          : '无'}
      </Descriptions.Item>
    </Descriptions>
  )
}

function reviewFlagLabel(flag: string): string {
  const labels: Record<string, string> = {
    NAME_REQUIRES_HUMAN_VERIFICATION: '名称待人工核验',
    CATEGORY_REQUIRES_HUMAN_VERIFICATION: '分类待人工核验',
    GEOMETRY_UNVERIFIED: '几何待核验',
    ACCESS_POINT_UNVERIFIED: '访问点待核验',
    TIME_RULES_NOT_COLLECTED: '开放时间未采集',
    DURATION_NOT_COLLECTED: '建议时长未采集',
    PROVIDER_POINT_IS_NOT_PLACE_GEOMETRY: 'Provider 点位不是地点几何',
  }
  return labels[flag] ?? flag
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'medium',
    hour12: false,
  }).format(new Date(value))
}
