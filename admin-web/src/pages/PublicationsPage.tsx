import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloudUploadOutlined,
  EyeOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd'
import type { Key } from 'antd/es/table/interface'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { adminErrorMessage } from '../api/errorMessages'
import type {
  PlaceListFilters as PlaceListFilterValues,
  PlaceRevision,
  PublicationBatch,
  PublicationCheck,
  ResearchSnapshot,
} from '../api/types'
import { useAdminSession } from '../auth/AdminSessionProvider'
import { PlaceListFilters } from '../components/PlaceListFilters'
import {
  categoryLabel,
  placeKindLabel,
  projectionStatusLabel,
  reasonCodeLabel,
} from '../ui/displayLabels'

const PAGE_SIZE = 20

type PublicationView = 'pending' | 'published'
type PublicationRevision = PlaceRevision & { check?: PublicationCheck }

export function PublicationsPage() {
  const { api, hasPermission } = useAdminSession()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const view: PublicationView = searchParams.get('view') === 'published' ? 'published' : 'pending'
  const [items, setItems] = useState<PublicationRevision[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedRowKeys, setSelectedRowKeys] = useState<Key[]>([])
  const [batch, setBatch] = useState<PublicationBatch | null>(null)
  const [snapshots, setSnapshots] = useState<ResearchSnapshot[]>([])
  const [batchLoading, setBatchLoading] = useState(false)
  const [filters, setFilters] = useState<PlaceListFilterValues>({})
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE)
  const [total, setTotal] = useState(0)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const lifecycleStatus = view === 'published' ? 'published' : 'human_verified'
      const result = await api.listCandidates(
        lifecycleStatus,
        pageSize,
        (page - 1) * pageSize,
        filters,
      )
      if (view === 'pending') {
        const checked = await Promise.all(
          result.items.map(async (revision) => {
            try {
              return {
                ...revision,
                check: await api.checkPlaceRevisionPublication(revision.place_revision_id),
              }
            } catch {
              return {
                ...revision,
                check: {
                  revision_id: revision.place_revision_id,
                  publishable: false,
                  reason_codes: ['PROJECTION_DEPENDENCY_MISSING'],
                },
              }
            }
          }),
        )
        setItems(checked)
      } else {
        setItems(result.items)
      }
      setTotal(result.total ?? result.items.length)
      const snapshotResult = await api.listResearchSnapshots('hangzhou', 10, 0)
      setSnapshots(snapshotResult.items)
    } catch (reason) {
      setError(adminErrorMessage(reason))
    } finally {
      setLoading(false)
    }
  }, [api, filters, page, pageSize, view])

  useEffect(() => {
    void load()
  }, [load])

  const changeView = (next: string) => {
    setPage(1)
    setSelectedRowKeys([])
    setBatch(null)
    setSearchParams(next === 'published' ? { view: 'published' } : {})
  }

  const previewBatch = async () => {
    const revisionIds = selectedRowKeys.map(String)
    if (!revisionIds.length) return
    setBatchLoading(true)
    setError(null)
    try {
      const result = await api.previewPublicationBatch({
        city_id: 'hangzhou',
        place_revision_ids: revisionIds,
        operation_intent_id: `publication-batch-preview-${crypto.randomUUID()}`,
        reason_code: 'PUBLICATION_BATCH_PREVIEW',
      })
      setBatch(result)
      message.success(`批次预览完成，共 ${result.items.length} 项`)
    } catch (reason) {
      setError(adminErrorMessage(reason))
    } finally {
      setBatchLoading(false)
    }
  }

  const executeBatch = async () => {
    if (!batch) return
    setBatchLoading(true)
    setError(null)
    try {
      const result = await api.executePublicationBatch(batch.batch_id, {
        operation_intent_id: `publication-batch-execute-${crypto.randomUUID()}`,
        reason_code: 'PUBLICATION_BATCH_EXECUTE',
      })
      setBatch(result.batch)
      if (result.snapshot) {
        setSnapshots((current) => [
          result.snapshot!,
          ...current.filter((item) => item.snapshot_id !== result.snapshot!.snapshot_id),
        ])
        message.success('批次已发布；正在打开已发布地点目录')
        changeView('published')
      } else {
        message.warning('批次执行完成，但没有成功发布项')
        await load()
      }
    } catch (reason) {
      setError(adminErrorMessage(reason))
    } finally {
      setBatchLoading(false)
    }
  }

  const publish = async (revision: PlaceRevision) => {
    setError(null)
    try {
      await api.publishPlaceRevision(revision.place_revision_id, {
        operation_intent_id: `publication-${crypto.randomUUID()}`,
        reason_code: 'PUBLICATION_APPROVED',
      })
      message.success('地点已发布；正在打开已发布地点目录')
      changeView('published')
    } catch (reason) {
      setError(adminErrorMessage(reason))
    }
  }

  const commonColumns = [
    {
      title: '景点名称',
      dataIndex: 'canonical_name',
      width: 250,
      fixed: 'left' as const,
      render: (value: string, revision: PlaceRevision) => (
        <Space orientation="vertical" size={0}>
          <Typography.Text strong>{value}</Typography.Text>
          <Typography.Text type="secondary" ellipsis style={{ maxWidth: 230 }}>
            {revision.address ?? '地址未提供'}
          </Typography.Text>
        </Space>
      ),
    },
    { title: '区域', dataIndex: 'admin_area', width: 130 },
    { title: '类型', dataIndex: 'place_kind', width: 140, render: placeKindLabel },
    { title: '分类', dataIndex: 'category', width: 140, ellipsis: true, render: categoryLabel },
    {
      title: '数据版本',
      dataIndex: 'revision_number',
      width: 110,
      render: (value: number) => <Tag>第 {value} 版</Tag>,
    },
  ]

  const pendingColumns = [
    ...commonColumns,
    {
      title: '发布门禁',
      width: 300,
      render: (_: unknown, item: PublicationRevision) =>
        item.check?.publishable ? (
          <Tag icon={<CheckCircleOutlined />} color="success">可发布</Tag>
        ) : (
          <Typography.Text type="warning">
            {item.check?.reason_codes.map(reasonCodeLabel).join('、') || '不可发布'}
          </Typography.Text>
        ),
    },
    {
      title: '操作',
      fixed: 'right' as const,
      width: 170,
      render: (_: unknown, item: PublicationRevision) => (
        <Space>
          <Button type="link" icon={<EyeOutlined />} onClick={() => navigate(`/candidates/${item.place_revision_id}`)}>
            查看
          </Button>
          {hasPermission('place:publication:write') && item.check?.publishable && (
            <Button size="small" type="primary" onClick={() => void publish(item)}>发布</Button>
          )}
        </Space>
      ),
    },
  ]

  const publishedColumns = [
    ...commonColumns,
    {
      title: '发布状态',
      width: 120,
      render: () => <Tag icon={<CheckCircleOutlined />} color="success">已发布</Tag>,
    },
    {
      title: '发布时间',
      dataIndex: 'published_at',
      width: 190,
      render: (value: string | null) => value ? formatDateTime(value) : '时间未记录',
    },
    {
      title: '操作',
      fixed: 'right' as const,
      width: 120,
      render: (_: unknown, item: PublicationRevision) => (
        <Button type="link" icon={<EyeOutlined />} onClick={() => navigate(`/candidates/${item.place_revision_id}`)}>
          查看详情
        </Button>
      ),
    },
  ]

  return (
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      <div className="page-heading-row">
        <div>
          <Typography.Title level={2}>发布中心</Typography.Title>
          <Typography.Paragraph type="secondary">
            管理通过人工核验的待发布地点，并持续查看已经进入用户目录的数据版本。
          </Typography.Paragraph>
        </div>
        <Button icon={<ReloadOutlined />} onClick={() => void load()} loading={loading}>刷新数据</Button>
      </div>

      {error && <Alert showIcon type="warning" title="发布数据暂不可用" description={error} />}

      <Card className="publication-workspace">
        <Tabs
          activeKey={view}
          onChange={changeView}
          items={[
            { key: 'pending', label: <span><ClockCircleOutlined /> 待发布地点</span> },
            { key: 'published', label: <span><CheckCircleOutlined /> 已发布地点</span> },
          ]}
        />

        <Alert
          className="publication-view-notice"
          showIcon
          type={view === 'published' ? 'success' : 'info'}
          title={view === 'published' ? '这里展示已经进入用户端目录的地点' : '这里展示已经人工核验、正在等待发布的地点'}
          description={view === 'published'
            ? '发布后的数据不会消失；可继续按名称、区域和地点类型查询，并打开当时发布的数据版本。'
            : '先检查发布门禁；只有门禁通过的数据才可单独发布或加入发布批次。'}
        />

        <div className="filter-panel">
          <PlaceListFilters
            value={filters}
            loading={loading}
            onSearch={(value) => {
              setPage(1)
              setSelectedRowKeys([])
              setFilters(value)
            }}
            onReset={() => {
              setPage(1)
              setSelectedRowKeys([])
              setFilters({})
            }}
          />
        </div>

        {view === 'pending' && (
          <div className="publication-actions">
            <Space wrap>
              <Button
                type="primary"
                icon={<CloudUploadOutlined />}
                onClick={() => void previewBatch()}
                disabled={!selectedRowKeys.length || !hasPermission('place:publication:write')}
                loading={batchLoading}
              >
                预览发布批次 ({selectedRowKeys.length})
              </Button>
              <Button
                onClick={() => void executeBatch()}
                disabled={!batch || batch.status === 'published' || !hasPermission('place:publication:write')}
                loading={batchLoading}
              >
                执行已预览批次
              </Button>
            </Space>
          </div>
        )}

        <Table<PublicationRevision>
          rowKey="place_revision_id"
          loading={loading}
          dataSource={items}
          rowSelection={view === 'pending' ? {
            selectedRowKeys,
            onChange: setSelectedRowKeys,
            getCheckboxProps: (item) => ({ disabled: !item.check?.publishable }),
          } : undefined}
          title={() => (
            <div className="table-section-heading">
              <span>
                <strong>{view === 'published' ? '已发布地点目录' : '待发布地点清单'}</strong>
                <small>{view === 'published' ? '用户端可见的数据版本' : '人工核验后的发布候选'}</small>
              </span>
              <Tag color={view === 'published' ? 'success' : 'processing'}>共 {total} 条</Tag>
            </div>
          )}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            pageSizeOptions: [20, 50, 100],
            showTotal: (count, range) => `${range[0]}-${range[1]} / 共 ${count} 条`,
            onChange: (nextPage, nextPageSize) => {
              setSelectedRowKeys([])
              setPage(nextPageSize === pageSize ? nextPage : 1)
              setPageSize(nextPageSize)
            },
          }}
          columns={view === 'published' ? publishedColumns : pendingColumns}
          scroll={{ x: view === 'published' ? 1120 : 1240 }}
          locale={{
            emptyText: view === 'published'
              ? '当前查询条件下没有已发布地点'
              : '当前查询条件下没有待发布地点',
          }}
        />
      </Card>

      {batch && view === 'pending' && (
        <Card title="批次预览结果" className="publication-batch-card">
          <Descriptions
            size="small"
            column={3}
            items={[
              { label: '状态', children: projectionStatusLabel(batch.status) },
              { label: '项目数', children: batch.items.length },
              { label: '可发布', children: batch.items.filter((item) => item.status === 'publishable').length },
            ]}
          />
          <Table
            rowKey="batch_item_id"
            size="small"
            pagination={false}
            dataSource={batch.items}
            columns={[
              { title: '景点名称', dataIndex: 'canonical_name', render: (value: string | undefined) => value ?? '名称未提供' },
              { title: '区域', dataIndex: 'admin_area', render: (value: string | undefined) => value ?? '未提供' },
              { title: '类型', dataIndex: 'place_kind', render: (value: string | undefined) => value ? placeKindLabel(value) : '未提供' },
              { title: '分类', dataIndex: 'category', render: categoryLabel },
              { title: '数据版本', dataIndex: 'revision_number', render: (value: number | undefined) => value ? `第 ${value} 版` : '—' },
              { title: '结果', dataIndex: 'status', render: (value: string) => <Tag color={value === 'publishable' || value === 'published' ? 'success' : 'warning'}>{projectionStatusLabel(value)}</Tag> },
              { title: '原因', dataIndex: 'reason_codes', render: (value: string[]) => value.length ? value.map(reasonCodeLabel).join('、') : '无' },
            ]}
          />
        </Card>
      )}

      <Card
        title="研究快照历史"
        extra={<Typography.Text type="secondary">最近 {snapshots.length} 个不可变快照</Typography.Text>}
      >
        <Table
          rowKey="snapshot_id"
          size="small"
          loading={loading}
          dataSource={snapshots}
          pagination={false}
          columns={[
            { title: '版本', dataIndex: 'data_snapshot_version' },
            { title: '内容摘要 Hash', dataIndex: 'content_sha256', ellipsis: true },
            { title: '生成时间', dataIndex: 'created_at', render: formatDateTime },
          ]}
        />
      </Card>
    </Space>
  )
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'medium',
    hour12: false,
  }).format(new Date(value))
}
