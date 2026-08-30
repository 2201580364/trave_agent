import { ReloadOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Space, Table, Tag, Typography, message } from 'antd'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { adminErrorMessage } from '../api/errorMessages'
import type { PlaceRevision, PublicationCheck } from '../api/types'
import { useAdminSession } from '../auth/AdminSessionProvider'

export function PublicationsPage() {
  const { api, hasPermission } = useAdminSession()
  const navigate = useNavigate()
  const [items, setItems] = useState<Array<PlaceRevision & { check?: PublicationCheck }>>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const result = await api.listCandidates('human_verified', 100)
      const checked = await Promise.all(result.items.map(async (revision) => {
        try { return { revision, check: await api.checkPlaceRevisionPublication(revision.place_revision_id) } }
        catch { return { revision, check: { revision_id: revision.place_revision_id, publishable: false, reason_codes: ['PROJECTION_DEPENDENCY_MISSING'] } } }
      }))
      setItems(checked.map(({ revision, check }) => ({ ...revision, check })))
    } catch (reason) { setError(adminErrorMessage(reason)) } finally { setLoading(false) }
  }, [api])
  useEffect(() => { void load() }, [load])
  const publish = async (revision: PlaceRevision) => {
    try { await api.publishPlaceRevision(revision.place_revision_id, { operation_intent_id: `publication-${crypto.randomUUID()}`, reason_code: 'PUBLICATION_APPROVED' }); message.success('发布请求已提交'); await load() }
    catch (reason) { setError(adminErrorMessage(reason)) }
  }
  return <Space orientation="vertical" size="large" style={{ width: '100%' }}>
    <div className="page-heading-row"><div><Typography.Title level={2}>发布中心</Typography.Title><Typography.Text type="secondary">查看人工核验 Revision 的发布门禁和 Projection 快照状态。</Typography.Text></div><Button icon={<ReloadOutlined />} onClick={() => void load()} loading={loading}>刷新</Button></div>
    {error && <Alert showIcon type="warning" title="发布数据暂不可用" description={error} />}
    <Card><Table rowKey="place_revision_id" loading={loading} dataSource={items} pagination={{ pageSize: 20 }} columns={[{ title: 'Revision', dataIndex: 'place_revision_id', ellipsis: true }, { title: '版本', dataIndex: 'revision_number' }, { title: '门禁', render: (_: unknown, item) => item.check?.publishable ? <Tag color="success">可发布</Tag> : <Tag color="warning">{item.check?.reason_codes.join('、') || '不可发布'}</Tag> }, { title: '操作', render: (_: unknown, item) => <Space><Button size="small" onClick={() => navigate(`/candidates/${item.place_revision_id}`)}>查看</Button>{hasPermission('place:publication:write') && item.check?.publishable && <Button size="small" type="primary" onClick={() => void publish(item)}>发布</Button>}</Space> }]} /></Card>
  </Space>
}
