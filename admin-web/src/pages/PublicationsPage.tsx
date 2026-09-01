import { ReloadOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Space, Table, Tag, Typography, message, Descriptions } from 'antd'
import type { Key } from 'antd/es/table/interface'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { adminErrorMessage } from '../api/errorMessages'
import type { PlaceListFilters as PlaceListFilterValues, PlaceRevision, PublicationBatch, PublicationCheck, ResearchSnapshot } from '../api/types'
import { useAdminSession } from '../auth/AdminSessionProvider'
import { PlaceListFilters } from '../components/PlaceListFilters'
import { categoryLabel, placeKindLabel, projectionStatusLabel, reasonCodeLabel } from '../ui/displayLabels'

const PAGE_SIZE = 20

export function PublicationsPage() {
  const { api, hasPermission } = useAdminSession()
  const navigate = useNavigate()
  const [items, setItems] = useState<Array<PlaceRevision & { check?: PublicationCheck }>>([])
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
    setLoading(true); setError(null)
    try {
      const result = await api.listCandidates(
        'human_verified',
        pageSize,
        (page - 1) * pageSize,
        filters,
      )
      const checked = await Promise.all(result.items.map(async (revision) => {
        try { return { revision, check: await api.checkPlaceRevisionPublication(revision.place_revision_id) } }
        catch { return { revision, check: { revision_id: revision.place_revision_id, publishable: false, reason_codes: ['PROJECTION_DEPENDENCY_MISSING'] } } }
      }))
      setItems(checked.map(({ revision, check }) => ({ ...revision, check })))
      setTotal(result.total ?? result.items.length)
      const snapshotResult = await api.listResearchSnapshots('hangzhou', 10, 0)
      setSnapshots(snapshotResult.items)
    } catch (reason) { setError(adminErrorMessage(reason)) } finally { setLoading(false) }
  }, [api, filters, page, pageSize])
  const previewBatch = async () => {
    const revisionIds = selectedRowKeys.map(String)
    if (!revisionIds.length) return
    setBatchLoading(true); setError(null)
    try {
      const result = await api.previewPublicationBatch({ city_id: 'hangzhou', place_revision_ids: revisionIds, operation_intent_id: `publication-batch-preview-${crypto.randomUUID()}`, reason_code: 'PUBLICATION_BATCH_PREVIEW' })
      setBatch(result); message.success(`批次预览完成，共 ${result.items.length} 项`)
    } catch (reason) { setError(adminErrorMessage(reason)) } finally { setBatchLoading(false) }
  }
  const executeBatch = async () => {
    if (!batch) return
    setBatchLoading(true); setError(null)
    try {
      const result = await api.executePublicationBatch(batch.batch_id, { operation_intent_id: `publication-batch-execute-${crypto.randomUUID()}`, reason_code: 'PUBLICATION_BATCH_EXECUTE' })
      setBatch(result.batch); if (result.snapshot) setSnapshots((current) => [result.snapshot!, ...current.filter((item) => item.snapshot_id !== result.snapshot!.snapshot_id)])
      message.success(result.snapshot ? '批次已发布并生成研究快照' : '批次执行完成，但没有成功发布项')
      await load()
    } catch (reason) { setError(adminErrorMessage(reason)) } finally { setBatchLoading(false) }
  }
  useEffect(() => { void load() }, [load])
  const publish = async (revision: PlaceRevision) => {
    try { await api.publishPlaceRevision(revision.place_revision_id, { operation_intent_id: `publication-${crypto.randomUUID()}`, reason_code: 'PUBLICATION_APPROVED' }); message.success('发布请求已提交'); await load() }
    catch (reason) { setError(adminErrorMessage(reason)) }
  }
  return <Space orientation="vertical" size="large" style={{ width: '100%' }}>
    <div className="page-heading-row"><div><Typography.Title level={2}>发布中心</Typography.Title><Typography.Text type="secondary">查看人工核验修订版本的发布门禁和求解投影快照状态。</Typography.Text></div><Button icon={<ReloadOutlined />} onClick={() => void load()} loading={loading}>刷新</Button></div>
    {error && <Alert showIcon type="warning" title="发布数据暂不可用" description={error} />}
    <Card>
      <PlaceListFilters
        value={filters}
        loading={loading}
        onSearch={(value) => { setPage(1); setSelectedRowKeys([]); setFilters(value) }}
        onReset={() => { setPage(1); setSelectedRowKeys([]); setFilters({}) }}
      />
    </Card>
    <Card>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" onClick={() => void previewBatch()} disabled={!selectedRowKeys.length || !hasPermission('place:publication:write')} loading={batchLoading}>预览批次 ({selectedRowKeys.length})</Button>
        <Button onClick={() => void executeBatch()} disabled={!batch || batch.status === 'published' || !hasPermission('place:publication:write')} loading={batchLoading}>执行批次</Button>
      </Space>
      <Table rowKey="place_revision_id" loading={loading} dataSource={items} rowSelection={{ selectedRowKeys, onChange: setSelectedRowKeys, getCheckboxProps: (item) => ({ disabled: !item.check?.publishable }) }} pagination={{ current: page, pageSize, total, showSizeChanger: true, pageSizeOptions: [20, 50, 100], showTotal: (count, range) => `${range[0]}-${range[1]} / 共 ${count} 条`, onChange: (nextPage, nextPageSize) => { setSelectedRowKeys([]); setPage(nextPageSize === pageSize ? nextPage : 1); setPageSize(nextPageSize) } }} columns={[{ title: '景点名称', dataIndex: 'canonical_name', width: 220, ellipsis: true }, { title: '区域', dataIndex: 'admin_area', width: 140 }, { title: '类型', dataIndex: 'place_kind', width: 130, render: placeKindLabel }, { title: '分类', dataIndex: 'category', width: 140, ellipsis: true, render: categoryLabel }, { title: '数据版本', dataIndex: 'revision_number', width: 100, render: (value: number) => `第 ${value} 版` }, { title: '门禁', render: (_: unknown, item) => item.check?.publishable ? <Tag color="success">可发布</Tag> : <Tag color="warning">{item.check?.reason_codes.map(reasonCodeLabel).join('、') || '不可发布'}</Tag> }, { title: '操作', fixed: 'right', width: 150, render: (_: unknown, item) => <Space><Button size="small" onClick={() => navigate(`/candidates/${item.place_revision_id}`)}>查看</Button>{hasPermission('place:publication:write') && item.check?.publishable && <Button size="small" type="primary" onClick={() => void publish(item)}>发布</Button>}</Space> }]} scroll={{ x: 1100 }} />
    </Card>
    {batch && <Card title="批次预览结果">
      <Descriptions size="small" column={3} items={[{ label: '状态', children: projectionStatusLabel(batch.status) }, { label: '项目数', children: batch.items.length }, { label: '可发布', children: batch.items.filter((item) => item.status === 'publishable').length }]} />
      <Table rowKey="batch_item_id" size="small" pagination={false} dataSource={batch.items} columns={[{ title: '景点名称', dataIndex: 'canonical_name', render: (value: string | undefined) => value ?? '名称未提供' }, { title: '区域', dataIndex: 'admin_area', render: (value: string | undefined) => value ?? '未提供' }, { title: '类型', dataIndex: 'place_kind', render: (value: string | undefined) => value ? placeKindLabel(value) : '未提供' }, { title: '分类', dataIndex: 'category', render: categoryLabel }, { title: '数据版本', dataIndex: 'revision_number', render: (value: number | undefined) => value ? `第 ${value} 版` : '—' }, { title: '结果', dataIndex: 'status', render: (value: string) => <Tag color={value === 'publishable' || value === 'published' ? 'success' : 'warning'}>{projectionStatusLabel(value)}</Tag> }, { title: '原因', dataIndex: 'reason_codes', render: (value: string[]) => value.length ? value.map(reasonCodeLabel).join('、') : '无' }]} />
    </Card>}
    <Card title="研究快照历史">
      <Table rowKey="snapshot_id" size="small" loading={loading} dataSource={snapshots} pagination={false} columns={[{ title: '版本', dataIndex: 'data_snapshot_version' }, { title: 'Hash', dataIndex: 'content_sha256', ellipsis: true }, { title: '生成时间', dataIndex: 'created_at', render: (value: string) => new Date(value).toLocaleString() }]} />
    </Card>
  </Space>
}
