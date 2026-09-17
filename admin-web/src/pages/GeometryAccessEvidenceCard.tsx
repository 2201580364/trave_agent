// H3 / S7-4: complete O04 evidence editing and review panel.
import { EditOutlined, PlusOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Collapse, Descriptions, Form, Input, InputNumber, Modal, Select, Space, Table, Tag, Typography } from 'antd'
import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { adminErrorMessage } from '../api/errorMessages'
import { createOperationIntent } from '../api/adminApi'
import type { PlaceAccessPointEvidence, PlaceAccessPointInput, PlaceGeometryEvidence, PlaceGeometryInput, PlaceRevision, PlaceRevisionEvidence, SourceChannel } from '../api/types'
import type { useAdminSession } from '../auth/AdminSessionProvider'
import { accessPointKindLabel, geometryKindLabel, projectionStatusLabel, reviewStatusLabel, sourceDecisionLabel } from '../ui/displayLabels'
import { geometryFormValues, geometryPayload, geometrySummary, parseCoordinateLines } from './revisionDetailHelpers'
import type { GeometryFormValues } from './revisionDetailHelpers'
import { formatOptionalDateTime, sourceLabelById, sourceRecordBusinessLabel, isFormValidationError, reviewStatusColor } from './revisionDetailDisplay'
import { FieldLabel, InstructionHint } from './revisionDetailFields'

export function GeometryAccessEvidenceCard({
  api,
  evidence,
  loading,
  error,
  revision,
  sourceChannels,
  canEdit,
  canReview,
  onSuccess,
  onChanged,
  onError,
}: {
  api: ReturnType<typeof useAdminSession>['api']
  evidence: PlaceRevisionEvidence | null
  loading: boolean
  error: string | null
  revision: PlaceRevision
  sourceChannels: SourceChannel[]
  canEdit: boolean
  canReview: boolean
  onSuccess: (text: string) => void
  onChanged: () => Promise<void>
  onError: (message: string) => void
}) {
  const reviewContext = new URLSearchParams(useLocation().search).get('from') === 'review'
  const editable = revision.lifecycle_status === 'candidate' && canEdit
  const reviewable = revision.lifecycle_status === 'candidate' && canReview
  const [modal, setModal] = useState<'geometry' | 'access' | null>(null)
  const [editing, setEditing] = useState<PlaceGeometryEvidence | PlaceAccessPointEvidence | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [form] = Form.useForm()
  const openGeometry = (item?: PlaceGeometryEvidence) => {
    setEditing(item ?? null)
    setSaveError(null)
    form.resetFields()
    form.setFieldsValue(geometryFormValues(item, revision.geometry_kind, evidence?.sources[0]?.source_record_id))
    setModal('geometry')
  }
  const openAccess = (item?: PlaceAccessPointEvidence) => {
    setEditing(item ?? null)
    setSaveError(null)
    form.resetFields()
    form.setFieldsValue(item ? item : { access_point_kind: 'visitor_entrance', source_record_id: evidence?.sources[0]?.source_record_id })
    setModal('access')
  }
  const saveEvidence = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const values = await form.validateFields()
      const base = { expected_revision_version: revision.revision_version, operation_intent_id: createOperationIntent('evidence'), reason_code: editing ? 'EVIDENCE_UPDATED' : 'EVIDENCE_CREATED' }
      if (modal === 'geometry') {
        const geometryValues = values as GeometryFormValues
        const input: PlaceGeometryInput = { ...base, geometry_kind: geometryValues.geometry_kind, geometry: geometryPayload(geometryValues), source_record_id: geometryValues.source_record_id }
        if (editing) await api.updateGeometry(revision.place_revision_id, (editing as PlaceGeometryEvidence).geometry_id, input); else await api.createGeometry(revision.place_revision_id, input)
      } else {
        const input: PlaceAccessPointInput = { ...base, access_point_kind: values.access_point_kind, name: values.name, lat: values.lat, lng: values.lng, source_record_id: values.source_record_id }
        if (editing) await api.updateAccessPoint(revision.place_revision_id, (editing as PlaceAccessPointEvidence).access_point_id, input); else await api.createAccessPoint(revision.place_revision_id, input)
      }
      setModal(null); await onChanged(); onSuccess('证据已保存，修订版本需重新送审')
    } catch (reason) {
      if (isFormValidationError(reason)) return
      // 客户端构造 payload 时的普通 Error（如坐标数量不足）：原样显示在弹窗内，
      // 不走 adminErrorMessage——那是 API 错误翻译管线，会把普通 Error 变成「服务不可用」。
      if (reason instanceof Error && !('code' in reason)) { setSaveError(reason.message); return }
      setSaveError(adminErrorMessage(reason))
    } finally { setSaving(false) }
  }
  const review = async (kind: 'geometry' | 'access_point', id: string, status: 'human_verified' | 'rejected') => {
    setSaving(true)
    try { await api.reviewEvidence(revision.place_revision_id, kind, id, { review_status: status, operation_intent_id: createOperationIntent('evidence-review'), reason_code: status === 'human_verified' ? 'EVIDENCE_APPROVED' : 'EVIDENCE_REJECTED' }); await onChanged(); onSuccess(status === 'human_verified' ? '证据已通过核验' : '证据已驳回') } catch (reason) { onError(adminErrorMessage(reason)) } finally { setSaving(false) }
  }
  const retire = async (kind: 'geometry' | 'access', id: string) => {
    setSaving(true)
    try { const input = { expected_revision_version: revision.revision_version, operation_intent_id: createOperationIntent('evidence-retire'), reason_code: 'EVIDENCE_RETIRED' }; if (kind === 'geometry') await api.retireGeometry(revision.place_revision_id, id, input); else await api.retireAccessPoint(revision.place_revision_id, id, input); await onChanged(); onSuccess('证据已停用，修订版本需重新送审') } catch (reason) { onError(adminErrorMessage(reason)) } finally { setSaving(false) }
  }
  if (loading) return <Card title="地图、几何与访问点（O04）" loading />
  if (error !== null) {
    return (
      <Card title="地图、几何与访问点（O04）">
        <Alert showIcon type="warning" title="O04 证据暂不可用" description={error} />
      </Card>
    )
  }
  if (evidence === null) {
    return (
      <Card title="地图、几何与访问点（O04）">
        <Alert showIcon type="warning" title="当前修订版本没有可读取的 O04 证据" />
      </Card>
    )
  }

  const projection = evidence.projection
  const sourceOptions = evidence.sources.map((source) => ({
    value: source.source_record_id,
    label: sourceRecordBusinessLabel(source, sourceChannels),
  }))
  return (
    <Card title="地图、几何与访问点（O04）">
      <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
        <InstructionHint text="几何是地点本体的地图形状；访问点是游客真正到达或离开的入口/出口；来源记录是证明该事实的采集记录。来源只能选择当前地点已有的有效记录，不能随意填写编号。" />
        <Descriptions bordered size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
          <Descriptions.Item label="来源证据">
            {evidence.sources.length > 0
              ? evidence.sources.map((source) => (
                  <Tag key={source.source_record_id}>
                    {sourceRecordBusinessLabel(source, sourceChannels)} · {sourceDecisionLabel(source.source_decision)}
                    {source.source_url_redacted ? ' · URL 已脱敏' : ''}
                  </Tag>
                ))
              : '未关联来源'}
          </Descriptions.Item>
          <Descriptions.Item label="几何记录数">{evidence.geometries.length}</Descriptions.Item>
          <Descriptions.Item label="访问点记录数">{evidence.access_points.length}</Descriptions.Item>
          <Descriptions.Item label="求解投影（发布后使用）">
            {projection ? `${projection.projection_id} · ${projectionStatusLabel(projection.status)}` : '未准备'}
          </Descriptions.Item>
          <Descriptions.Item label="到达端点（游客进入）">
            {projection ? projection.arrival_access_point_id : '未选择'}
          </Descriptions.Item>
          <Descriptions.Item label="离开端点（游客离开）">
            {projection ? projection.departure_access_point_id : '未选择'}
          </Descriptions.Item>
        </Descriptions>

        {evidence.missing_source_record_ids.length > 0 && (
          <Alert
            showIcon
            type="warning"
            title="来源证据不完整"
              description={`以下来源记录缺失或不属于当前地点：${evidence.missing_source_record_ids.join('、')}`}
          />
        )}

        <Space style={{ width: '100%', justifyContent: 'space-between' }}><Typography.Title level={5} style={{ margin: 0 }}>几何证据</Typography.Title>{editable && <Button size="small" icon={<PlusOutlined />} onClick={() => openGeometry()}>新增</Button>}</Space>
        <Table<PlaceGeometryEvidence>
          rowKey="geometry_id"
          size="small"
          pagination={false}
          dataSource={evidence.geometries}
          scroll={{ x: 900 }}
          columns={[
            { title: '类型', dataIndex: 'geometry_kind', width: 110, render: geometryKindLabel },
            {
              title: '状态',
              dataIndex: 'review_status',
              width: 120,
              render: (value: string, item) => (
                <Space size={4}>
                  <Tag color={reviewStatusColor(value)}>{reviewStatusLabel(value)}</Tag>
                  {!item.active && <Tag>已停用</Tag>}
                </Space>
              ),
            },
            {
              title: '图形数据',
              dataIndex: 'geometry',
              width: 390,
              render: (value: Record<string, unknown>) => (
                <Typography.Text code style={{ wordBreak: 'break-all' }}>
                  {geometrySummary(value)}
                </Typography.Text>
              ),
            },
            {
              title: '来源记录',
              key: 'source_record_id',
              width: 240,
              render: (_: unknown, item) => (
                <Space size={4}>
                  <Typography.Text ellipsis={{ tooltip: `内部记录：${item.source_record_id}` }}>
                    {sourceLabelById(evidence, item.source_record_id, sourceChannels)}
                  </Typography.Text>
                  <Tag color={item.source_record_valid ? 'success' : 'error'}>
                    {item.source_record_valid ? '有效' : '无效'}
                  </Tag>
                </Space>
              ),
            },
            {
              title: '核验时间',
              dataIndex: 'reviewed_at',
              width: 260,
              render: (value: string | null) => formatOptionalDateTime(value),
            },
            ...((editable || reviewable) ? [{ title: '操作', key: 'actions', render: (_: unknown, item: PlaceGeometryEvidence) => <Space>{editable && <><Button size="small" icon={<EditOutlined />} onClick={() => openGeometry(item)}>编辑</Button>{reviewContext && item.active && <Button size="small" danger onClick={() => void retire('geometry', item.geometry_id)}>停用</Button>}</>}{reviewable && item.active && <><Button size="small" type="primary" onClick={() => void review('geometry', item.geometry_id, 'human_verified')}>通过</Button><Button size="small" onClick={() => void review('geometry', item.geometry_id, 'rejected')}>驳回</Button></>}</Space> }] : []),
          ]}
          locale={{ emptyText: '当前没有几何证据' }}
        />

        <Space style={{ width: '100%', justifyContent: 'space-between' }}><Typography.Title level={5} style={{ margin: 0 }}>访问点证据</Typography.Title>{editable && <Button size="small" icon={<PlusOutlined />} onClick={() => openAccess()}>新增</Button>}</Space>
        <Table<PlaceAccessPointEvidence>
          rowKey="access_point_id"
          size="small"
          pagination={false}
          dataSource={evidence.access_points}
          scroll={{ x: 1000 }}
          columns={[
            { title: '名称', dataIndex: 'name', width: 180 },
            {
              title: '用途',
              dataIndex: 'access_point_kind',
              width: 150,
              render: (value: string) => accessPointKindLabel(value),
            },
            {
              title: '坐标',
              key: 'coordinate',
              width: 190,
              render: (_: unknown, item) => `${item.lat.toFixed(6)}, ${item.lng.toFixed(6)}`,
            },
            {
              title: '求解投影端点',
              key: 'projection_role',
              width: 170,
              render: (_: unknown, item) => projectionRole(item.access_point_id, projection),
            },
            {
              title: '状态',
              dataIndex: 'review_status',
              width: 120,
              render: (value: string, item) => (
                <Space size={4}>
                  <Tag color={reviewStatusColor(value)}>{reviewStatusLabel(value)}</Tag>
                  {!item.active && <Tag>已停用</Tag>}
                </Space>
              ),
            },
            {
              title: '来源记录',
              key: 'source_record_id',
              width: 240,
              render: (_: unknown, item) => (
                <Space size={4}>
                  <Typography.Text ellipsis={{ tooltip: `内部记录：${item.source_record_id}` }}>
                    {sourceLabelById(evidence, item.source_record_id, sourceChannels)}
                  </Typography.Text>
                  <Tag color={item.source_record_valid ? 'success' : 'error'}>
                    {item.source_record_valid ? '有效' : '无效'}
                  </Tag>
                </Space>
              ),
            },
            ...((editable || reviewable) ? [{ title: '操作', key: 'actions', width: 280, render: (_: unknown, item: PlaceAccessPointEvidence) => <Space>{editable && <><Button size="small" icon={<EditOutlined />} onClick={() => openAccess(item)}>编辑</Button>{reviewContext && item.active && <Button size="small" danger onClick={() => void retire('access', item.access_point_id)}>停用</Button>}</>}{reviewable && item.active && <><Button size="small" type="primary" onClick={() => void review('access_point', item.access_point_id, 'human_verified')}>通过</Button><Button size="small" onClick={() => void review('access_point', item.access_point_id, 'rejected')}>驳回</Button></>}</Space> }] : []),
          ]}
          locale={{ emptyText: '当前没有访问点证据' }}
        />

        {projection === null ? (
          <Alert showIcon type="info" title="尚未准备求解投影，访问点不会被自动选作求解端点" />
        ) : (
          <Alert
            showIcon
            type="info"
            title={`求解投影已明确绑定到达端点 ${projection.arrival_access_point_id} 和离开端点 ${projection.departure_access_point_id}`}
          />
        )}
      </Space>
      <Modal title={modal === 'geometry' ? '新增/编辑几何证据' : '新增/编辑访问点证据'} open={modal !== null} onOk={() => void saveEvidence()} onCancel={() => { setModal(null); setSaveError(null) }} confirmLoading={saving} forceRender>
        {saveError !== null && <Alert showIcon type="error" title={saveError} style={{ marginBottom: 16 }} closable onClose={() => setSaveError(null)} />}
        <Form form={form} layout="vertical" onValuesChange={() => { if (saveError !== null) setSaveError(null) }}>
          {modal === 'geometry' ? <>
            <Form.Item name="geometry_kind" label={<FieldLabel label="几何类型" hint="点状景点选“点”；景区/街区边界选“区域”；步行路线选“路线”。" />} rules={[{ required: true }]}>
              <Select options={[{ value: 'point', label: '点（地点代表点）' }, { value: 'area', label: '区域（边界或范围）' }, { value: 'route', label: '路线（起终点或轨迹）' }]} />
            </Form.Item>
            <Form.Item noStyle shouldUpdate={(previous, current) => previous.geometry_kind !== current.geometry_kind}>
              {({ getFieldValue }) => getFieldValue('geometry_kind') === 'point' ? <Space style={{ width: '100%' }} size="middle">
                <Form.Item name="geometry_lng" label={<FieldLabel label="经度" hint="填写地图上的经度，范围 -180 至 180，例如 120.160970。" />} rules={[{ required: true, type: 'number', min: -180, max: 180, message: '请输入 -180 到 180 之间的经度' }]} style={{ flex: 1 }}>
                  <InputNumber style={{ width: '100%' }} placeholder="120.160970" />
                </Form.Item>
                <Form.Item name="geometry_lat" label={<FieldLabel label="纬度" hint="填写地图上的纬度，范围 -90 至 90，例如 30.253778。" />} rules={[{ required: true, type: 'number', min: -90, max: 90, message: '请输入 -90 到 90 之间的纬度' }]} style={{ flex: 1 }}>
                  <InputNumber style={{ width: '100%' }} placeholder="30.253778" />
                </Form.Item>
              </Space> : <Form.Item name="geometry_coordinates" label={<FieldLabel label={getFieldValue('geometry_kind') === 'area' ? '边界坐标点' : '路线坐标点'} hint={getFieldValue('geometry_kind') === 'area' ? '每行一个边界点，格式为“经度, 纬度”，至少 3 个点；系统会自动闭合边界。' : '每行一个轨迹点，格式为“经度, 纬度”，至少 2 个点；按行填写行进顺序。'} />} rules={[{ required: true, message: '请至少填写所需坐标点' }, {
                // 与 geometryPayload 同口径的即时校验：格式/范围/数量错误直接显示在字段下。
                // 此前只校验非空，点数不足等错误在提交后才抛出且渲染在弹窗之外，用户看到「没反应」。
                validator: (_rule: unknown, value: string | undefined) => {
                  try {
                    parseCoordinateLines(getFieldValue('geometry_kind'), value)
                    return Promise.resolve()
                  } catch (reason) {
                    return Promise.reject(reason instanceof Error ? reason : new Error(String(reason)))
                  }
                },
              }]}>
                <Input.TextArea rows={5} placeholder={'例如：\n120.160970, 30.253778\n120.161200, 30.254100\n120.161500, 30.253900'} />
              </Form.Item>}
            </Form.Item>
            <Alert type="info" showIcon title="系统会根据上面的坐标自动生成标准图形数据，坐标顺序为“经度, 纬度”。审核员无需填写技术格式。" />
            {editing && modal === 'geometry' && <Collapse ghost items={[{ key: 'raw', label: '查看原始图形数据（仅供追溯）', children: <Typography.Paragraph copyable={{ text: JSON.stringify((editing as PlaceGeometryEvidence).geometry, null, 2) }} code style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{JSON.stringify((editing as PlaceGeometryEvidence).geometry, null, 2)}</Typography.Paragraph> }]} />}
            <Form.Item name="source_record_id" label={<FieldLabel label="来源记录" hint="选择证明这条几何数据的来源；来源详情可在上方来源证据中查看。" />} rules={[{ required: true }]}>
              <Select showSearch optionFilterProp="label" options={sourceOptions} placeholder="选择当前地点的有效来源" />
            </Form.Item>
          </> : <>
            <Form.Item name="access_point_kind" label={<FieldLabel label="访问点用途" hint="访问点是游客实际进出的端点，不是地点本体中心点。" />} rules={[{ required: true, message: '请选择访问点用途' }]}>
              <Select options={[
                { value: 'visitor_entrance', label: '游客入口（到达）' },
                { value: 'visitor_exit', label: '游客出口（离开）' },
                { value: 'route_start', label: '路线起点' },
                { value: 'route_end', label: '路线终点' },
                { value: 'performance_location', label: '演出地点' },
                { value: 'meeting_point', label: '集合点' },
                { value: 'area_representative', label: '区域代表点' },
              ]} />
            </Form.Item>
            <Form.Item name="name" label={<FieldLabel label="访问点名称" hint="填写地图或现场可识别的入口/出口名称，例如“灵隐寺进口”。" />} rules={[{ required: true }]}><Input /></Form.Item>
            <Space style={{ width: '100%' }}>
              <Form.Item name="lat" label={<FieldLabel label="纬度" hint="纬度范围为 -90 至 90。" />} rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} /></Form.Item>
              <Form.Item name="lng" label={<FieldLabel label="经度" hint="经度范围为 -180 至 180。" />} rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} /></Form.Item>
            </Space>
            <Form.Item name="source_record_id" label={<FieldLabel label="来源记录" hint="选择证明这个入口坐标的来源；不要填高德 POI ID 或内部编号。" />} rules={[{ required: true }]}>
              <Select showSearch optionFilterProp="label" options={sourceOptions} placeholder="选择当前地点的有效来源" />
            </Form.Item>
          </>}
        </Form>
      </Modal>
    </Card>
  )
}


function projectionRole(
  accessPointId: string,
  projection: PlaceRevisionEvidence['projection'],
): string {
  if (projection === null) return '未选择'
  const roles: string[] = []
  if (projection.arrival_access_point_id === accessPointId) roles.push('到达')
  if (projection.departure_access_point_id === accessPointId) roles.push('离开')
  return roles.length > 0 ? roles.join(' / ') : '未选择'
}
