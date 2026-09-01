import { FileSearchOutlined, ReloadOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Descriptions, Space, Table, Tag, Typography } from 'antd'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { adminErrorMessage } from '../api/errorMessages'
import type { PlaceListFilters as PlaceListFilterValues, PlaceRevision } from '../api/types'
import { useAdminSession } from '../auth/AdminSessionProvider'
import { ErrorNotice } from '../components/ErrorNotice'
import { PlaceListFilters } from '../components/PlaceListFilters'
import { indoorOutdoorLabel, lifecycleStatusLabel, placeKindLabel, rainSuitabilityLabel, reviewFlagLabel } from '../ui/displayLabels'

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
  const [filters, setFilters] = useState<PlaceListFilterValues>({})

  const load = useCallback(async (requestedPage: number, requestedPageSize: number) => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.listCandidates(
        'candidate',
        requestedPageSize,
        (requestedPage - 1) * requestedPageSize,
        filters,
      )
      setItems(result.items)
      setTotal(result.total ?? result.items.length)
    } catch (reason) {
      setError(adminErrorMessage(reason))
    } finally {
      setLoading(false)
    }
  }, [api, filters])

  useEffect(() => {
    void load(page, pageSize)
  }, [load, page, pageSize])

  const refresh = () => {
    setPage(1)
    void load(page, pageSize)
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
        title: '审核准备度',
        key: 'review_readiness',
        width: 180,
        render: (_: unknown, revision: PlaceRevision) => <ReadinessSummary revision={revision} />,
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

  const readinessCounts = useMemo(() => ({
    needsEvidence: items.filter((item) => item.review_readiness?.status === 'needs_evidence').length,
    readyForReview: items.filter((item) => item.review_readiness?.status === 'ready_for_review').length,
    inReview: items.filter((item) => ['under_review', 'changes_requested', 'ready_for_approval'].includes(item.review_readiness?.status ?? '')).length,
  }), [items])

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
      <Alert
        showIcon
        type={readinessCounts.needsEvidence > 0 ? 'warning' : 'success'}
        title={`本页审核准备：待补录 ${readinessCounts.needsEvidence} 条，可送审 ${readinessCounts.readyForReview} 条，审核中/可通过 ${readinessCounts.inReview} 条`}
        description="准备度按基础事实、来源、几何、访问点、开放时间和关系检查六项计算；它用于定位下一步，不会自动改变审核或发布状态。"
      />
      <Card className="filter-card">
        <PlaceListFilters
          value={filters}
          loading={loading}
          onSearch={(value) => {
            setPage(1)
            setFilters(value)
          }}
          onReset={() => {
            setPage(1)
            setFilters({})
          }}
        />
      </Card>
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
          scroll={{ x: 1260 }}
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
      <Descriptions.Item label="审核准备清单" span="filled">
        {revision.review_readiness
          ? <Space wrap>{revision.review_readiness.checks.map((check) => (
              <Tag key={check.key} color={check.verified ? 'success' : check.collected ? 'processing' : 'warning'}>
                {readinessCheckLabel(check.key)}：{check.verified ? '已核验' : check.collected ? '待审核' : '待补录'}
              </Tag>
            ))}</Space>
          : '准备度暂不可用'}
      </Descriptions.Item>
      <Descriptions.Item label="待核验项" span="filled">
        {revision.review_flags.length > 0
          ? revision.review_flags.map((flag) => <Tag key={flag} color="warning">{reviewFlagLabel(flag)}</Tag>)
          : '无'}
      </Descriptions.Item>
    </Descriptions>
  )
}

function ReadinessSummary({ revision }: { revision: PlaceRevision }) {
  const readiness = revision.review_readiness
  if (!readiness) return <Typography.Text type="secondary">暂不可用</Typography.Text>
  const statusLabels: Record<string, { label: string; color: string }> = {
    needs_evidence: { label: '待补录', color: 'warning' },
    ready_for_review: { label: '可送审', color: 'success' },
    under_review: { label: '审核中', color: 'processing' },
    changes_requested: { label: '待修改', color: 'error' },
    ready_for_approval: { label: '可审核通过', color: 'cyan' },
    human_verified: { label: '已人工核验', color: 'success' },
    published: { label: '已发布', color: 'success' },
    retired: { label: '已停用', color: 'default' },
  }
  const display = statusLabels[readiness.status] ?? { label: readiness.status, color: 'default' }
  return (
    <Space size={4} wrap>
      <Tag color={display.color}>{display.label}</Tag>
      <Typography.Text type="secondary">{readiness.completed_checks}/{readiness.total_checks} 项已准备</Typography.Text>
    </Space>
  )
}

function readinessCheckLabel(key: string): string {
  return ({
    basic: '基础事实',
    source: '来源与冲突',
    geometry: '地点几何',
    access_point: '访问点',
    time: '开放时间',
    relation: '关系检查',
  } as Record<string, string>)[key] ?? key
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'medium',
    hour12: false,
  }).format(new Date(value))
}
