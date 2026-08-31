import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  CloudUploadOutlined,
  EditOutlined,
  PlusOutlined,
  ReloadOutlined,
  SendOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons'
import { Alert, App as AntApp, Button, Card, Descriptions, Form, Input, InputNumber, Modal, Select, Space, Table, Tag, Typography } from 'antd'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { adminErrorMessage } from '../api/errorMessages'
import type { PlaceAccessPointEvidence, PlaceAccessPointInput, PlaceClosureEvidence, PlaceClosureInput, PlaceDateExceptionEvidence, PlaceDateExceptionInput, PlaceGeometryEvidence, PlaceGeometryInput, PlaceRevision, PlaceRevisionEvidence, PlaceTimeRuleEvidence, PlaceTimeRuleInput, PlaceTimePreview, PlaceRelationEvidence } from '../api/types'
import { useAdminSession } from '../auth/AdminSessionProvider'
import { ErrorNotice } from '../components/ErrorNotice'
import {
  accessPointKindLabel,
  dateExceptionKindLabel,
  geometryKindLabel,
  indoorOutdoorLabel,
  lifecycleStatusLabel,
  placeKindLabel,
  projectionStatusLabel,
  rainSuitabilityLabel,
  relationResolutionLabel,
  relationTypeLabel,
  reviewStatusLabel,
  sourceDecisionLabel,
  timeRuleKindLabel,
} from '../ui/displayLabels'

const reviewFlagLabels: Record<string, string> = {
  NAME_REQUIRES_HUMAN_VERIFICATION: '名称待人工核验',
  CATEGORY_REQUIRES_HUMAN_VERIFICATION: '分类待人工核验',
  GEOMETRY_UNVERIFIED: '几何待核验',
  ACCESS_POINT_UNVERIFIED: '访问点待核验',
  TIME_RULES_NOT_COLLECTED: '开放时间未采集',
  DURATION_NOT_COLLECTED: '建议时长未采集',
  PROVIDER_POINT_IS_NOT_PLACE_GEOMETRY: 'Provider 点位不是地点几何',
}

export function RevisionDetailsPage() {
  const { api, hasPermission } = useAdminSession()
  const { message: messageApi } = AntApp.useApp()
  const navigate = useNavigate()
  const { revisionId } = useParams<{ revisionId: string }>()
  const [revision, setRevision] = useState<PlaceRevision | null>(null)
  const [evidence, setEvidence] = useState<PlaceRevisionEvidence | null>(null)
  const [loading, setLoading] = useState(true)
  const [evidenceLoading, setEvidenceLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [evidenceError, setEvidenceError] = useState<string | null>(null)
  const [editOpen, setEditOpen] = useState(false)
  const [working, setWorking] = useState(false)
  const [form] = Form.useForm()

  const load = useCallback(async () => {
    if (!revisionId) {
      setError('缺少修订版本编号')
      setLoading(false)
      return
    }
    setLoading(true)
    setEvidenceLoading(true)
    setError(null)
    setEvidenceError(null)

    const revisionRequest = api.getPlaceRevision(revisionId)
      .then((nextRevision) => {
        setRevision(nextRevision)
      })
      .catch((reason: unknown) => {
        setRevision(null)
        setError(adminErrorMessage(reason))
      })
      .finally(() => {
        setLoading(false)
      })

    const evidenceRequest = api.getPlaceRevisionEvidence(revisionId)
      .then((nextEvidence) => {
        setEvidence(nextEvidence)
      })
      .catch((reason: unknown) => {
        setEvidence(null)
        setEvidenceError(adminErrorMessage(reason))
      })
      .finally(() => {
        setEvidenceLoading(false)
      })

    await Promise.all([revisionRequest, evidenceRequest])
  }, [api, revisionId])

  useEffect(() => {
    void load()
  }, [load])

  const blockers = useMemo(() => (revision ? publicationBlockers(revision) : []), [revision])

  const createRevision = async () => {
    if (!revision) return
    setWorking(true)
    try {
      const created = await api.createPlaceRevision(revision.place_id, {
        base_revision_id: revision.place_revision_id,
        operation_intent_id: `revision-create-${crypto.randomUUID()}`,
        reason_code: 'PLACE_FACTS_REFRESH',
      })
      messageApi.success(`已创建修订版本 ${created.revision_number}`)
      navigate(`/candidates/${encodeURIComponent(created.place_revision_id)}`)
    } catch (reason) {
      setError(adminErrorMessage(reason))
    } finally {
      setWorking(false)
    }
  }

  const saveEdit = async () => {
    if (!revision) return
    setWorking(true)
    try {
      const values = await form.validateFields()
      const updated = await api.updatePlaceRevision(revision.place_revision_id, {
        expected_revision_number: revision.revision_number,
        operation_intent_id: `revision-update-${crypto.randomUUID()}`,
        reason_code: 'PLACE_FACTS_EDITED',
        ...values,
      })
      setRevision(updated)
      setEditOpen(false)
      messageApi.success('修订版本已保存，需要重新送审')
    } catch (reason) {
      if (!isFormValidationError(reason)) setError(adminErrorMessage(reason))
    } finally {
      setWorking(false)
    }
  }

  const submitReview = async () => {
    if (!revision) return
    setWorking(true)
    try {
      await api.submitPlaceReview(revision.place_revision_id, {
        operation_intent_id: `review-submit-${crypto.randomUUID()}`,
        reason_code: 'READY_FOR_REVIEW',
      })
      await load()
      messageApi.success('已送入审核队列')
    } catch (reason) {
      setError(adminErrorMessage(reason))
    } finally {
      setWorking(false)
    }
  }

  const publish = async () => {
    if (!revision) return
    setWorking(true)
    try {
      const check = await api.checkPlaceRevisionPublication(revision.place_revision_id)
      if (!check.publishable) {
        setError(`发布门禁未通过：${check.reason_codes.join('、')}`)
        return
      }
      await api.publishPlaceRevision(revision.place_revision_id, {
        operation_intent_id: `revision-publish-${crypto.randomUUID()}`,
        reason_code: 'PUBLISH_GATE_PASSED',
      })
      messageApi.success('新快照已发布')
      await load()
    } catch (reason) {
      setError(adminErrorMessage(reason))
    } finally {
      setWorking(false)
    }
  }

  const prepareProjection = async () => {
    if (!revision) return
    setWorking(true)
    try {
      const result = await api.preparePlaceRevisionProjection(revision.place_revision_id, {
        data_snapshot_version: 'hangzhou-research-candidate-v1',
        operation_intent_id: `projection-prepare-${crypto.randomUUID()}`,
        reason_code: 'PROJECTION_PREPARED',
      })
      await load()
      messageApi.success(result.gate_reason_codes.length ? `求解投影已生成，但仍有 ${result.gate_reason_codes.length} 项发布门禁阻断` : '求解投影已生成，可进入发布批次')
    } catch (reason) {
      setError(adminErrorMessage(reason))
    } finally {
      setWorking(false)
    }
  }

  return (
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      <div className="page-heading-row">
        <div>
          <Typography.Title level={2}>修订版本详情</Typography.Title>
          <Typography.Paragraph type="secondary">
            O03：核对候选地点的业务事实、生命周期和当前发布阻断摘要。
          </Typography.Paragraph>
        </div>
        <Space wrap>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/candidates')}>
            返回候选地点
          </Button>
          {revision && revision.lifecycle_status === 'candidate' &&
            (hasPermission('place:candidate:write') ||
              hasPermission('place:review:request')) && (
            <Space.Compact>
              {hasPermission('place:candidate:write') && (
                <Button icon={<EditOutlined />} onClick={() => { form.setFieldsValue({ canonical_name: revision.canonical_name, address: revision.address, duration_recommended: revision.duration_recommended }); setEditOpen(true) }}>
                  编辑候选
                </Button>
              )}
              {hasPermission('place:review:request') && (
                <Button icon={<SendOutlined />} onClick={() => void submitReview()} loading={working}>
                  送审
                </Button>
              )}
            </Space.Compact>
          )}
          {revision && revision.lifecycle_status === 'human_verified' &&
            hasPermission('place:publication:write') && (
            <Space.Compact>
              {evidence?.projection === null && <Button icon={<SafetyCertificateOutlined />} onClick={() => void prepareProjection()} loading={working}>准备求解投影</Button>}
              <Button type="primary" icon={<CloudUploadOutlined />} onClick={() => void publish()} loading={working}>发布新快照</Button>
            </Space.Compact>
          )}
          {revision && revision.lifecycle_status !== 'candidate' &&
            hasPermission('place:candidate:write') && (
            <Button icon={<PlusOutlined />} onClick={() => void createRevision()} loading={working}>
              新建修订
            </Button>
          )}
          <Button icon={<ReloadOutlined />} onClick={() => void load()} loading={loading}>
            刷新
          </Button>
        </Space>
      </div>

      {error !== null && <ErrorNotice message={error} onClose={() => setError(null)} />}
      {revision !== null && (
        <>
          <Card>
            <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
              <Space wrap>
                <Typography.Title level={3} style={{ margin: 0 }}>
                  {revision.canonical_name}
                </Typography.Title>
                <Tag color={revision.lifecycle_status === 'human_verified' ? 'success' : 'processing'}>
                  {lifecycleStatusLabel(revision.lifecycle_status)}
                </Tag>
                <Tag>修订版本 {revision.revision_number}</Tag>
              </Space>
              <Typography.Text type="secondary">
                {revision.place_revision_id} · 地点 {revision.place_id}
              </Typography.Text>
            </Space>
          </Card>

          <Card title="基础事实">
            <Descriptions bordered size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
              <Descriptions.Item label="规范名称">{revision.canonical_name}</Descriptions.Item>
              <Descriptions.Item label="别名">{revision.aliases.join('、') || '未提供'}</Descriptions.Item>
              <Descriptions.Item label="区域">{revision.admin_area}</Descriptions.Item>
              <Descriptions.Item label="类型">{placeKindLabel(revision.place_kind)}</Descriptions.Item>
              <Descriptions.Item label="分类">{revision.category}</Descriptions.Item>
              <Descriptions.Item label="地址">{revision.address ?? '未提供'}</Descriptions.Item>
              <Descriptions.Item label="几何类型">{geometryKindLabel(revision.geometry_kind)}</Descriptions.Item>
              <Descriptions.Item label="来源记录数">{revision.source_record_ids.length}</Descriptions.Item>
              <Descriptions.Item label="创建时间">{formatDateTime(revision.created_at)}</Descriptions.Item>
            </Descriptions>
          </Card>

          <Card title="体验与求解摘要">
            <Descriptions bordered size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
              <Descriptions.Item label="建议时长">
                {revision.review_flags.includes('DURATION_NOT_COLLECTED')
                  ? '未采集'
                  : `${revision.duration_min} - ${revision.duration_max} 分钟（建议 ${revision.duration_recommended} 分钟）`}
              </Descriptions.Item>
              <Descriptions.Item label="内部移动">{revision.internal_travel_min} 分钟</Descriptions.Item>
              <Descriptions.Item label="体力等级">{revision.energy_level} / 5</Descriptions.Item>
              <Descriptions.Item label="室内/室外">{indoorOutdoorLabel(revision.indoor_outdoor)}</Descriptions.Item>
              <Descriptions.Item label="适用时段">{revision.suitable_periods.map((value) => ({ morning: '上午', afternoon: '下午', evening: '晚上' }[value] ?? '其他')).join('、') || '未提供'}</Descriptions.Item>
              <Descriptions.Item label="适合人群">{revision.audience_tags.join('、') || '未提供'}</Descriptions.Item>
              <Descriptions.Item label="雨天适配">{rainSuitabilityLabel(revision.rain_suitability)}</Descriptions.Item>
              <Descriptions.Item label="全天开放">{revision.is_always_open ? '是' : '否'}</Descriptions.Item>
              <Descriptions.Item label="求解器可用">
                {revision.solver_eligible ? <Tag color="success">可用</Tag> : <Tag color="error">不可用</Tag>}
              </Descriptions.Item>
              <Descriptions.Item label="待核验项" span={3}>
                {revision.review_flags.length > 0
                  ? revision.review_flags.map((flag) => (
                      <Tag key={flag} color="warning">
                        {reviewFlagLabels[flag] ?? '待核验项'}
                      </Tag>
                    ))
                  : '无'}
              </Descriptions.Item>
            </Descriptions>
          </Card>

          <Card title="治理状态">
            <Descriptions bordered size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
              <Descriptions.Item label="当前生命周期">{lifecycleStatusLabel(revision.lifecycle_status)}</Descriptions.Item>
              <Descriptions.Item label="冲突裁决">{revision.conflicts_resolved ? '已完成' : '待处理'}</Descriptions.Item>
              <Descriptions.Item label="人工核验时间">{formatOptionalDateTime(revision.reviewed_at)}</Descriptions.Item>
              <Descriptions.Item label="发布时间">{formatOptionalDateTime(revision.published_at)}</Descriptions.Item>
              <Descriptions.Item label="修订版本编号">{revision.place_revision_id}</Descriptions.Item>
              <Descriptions.Item label="地点编号">{revision.place_id}</Descriptions.Item>
            </Descriptions>
          </Card>

          <EvidenceCard
            api={api}
            evidence={evidence}
            loading={evidenceLoading}
            error={evidenceError}
            revision={revision}
            canEdit={hasPermission('place:candidate:write')}
            canReview={hasPermission('place:review:decide')}
            onSuccess={(text) => messageApi.success(text)}
            onChanged={load}
            onError={setError}
          />
          <TimeEvidenceCard
            api={api}
            evidence={evidence}
            loading={evidenceLoading}
            error={evidenceError}
            revision={revision}
            canEdit={hasPermission('place:candidate:write')}
            canReview={hasPermission('place:review:decide')}
            onSuccess={(text) => messageApi.success(text)}
            onChanged={load}
            onError={setError}
          />
          <RelationEvidenceCard api={api} evidence={evidence} revision={revision} canEdit={hasPermission('place:candidate:write')} onChanged={load} onSuccess={(text) => messageApi.success(text)} onError={setError} />

          <Card title="发布阻断摘要">
            {blockers.length === 0 ? (
              <Alert showIcon type="success" icon={<CheckCircleOutlined />} title="当前修订版本没有从详情字段识别出的阻断项" />
            ) : (
              <Space orientation="vertical" style={{ width: '100%' }}>
                <Alert showIcon type="warning" title={`当前有 ${blockers.length} 项需要处理`} />
                {blockers.map((blocker) => (
                  <Typography.Text key={blocker} type="secondary">
                    <CloseCircleOutlined /> {blocker}
                  </Typography.Text>
                ))}
            </Space>
            )}
            <Typography.Paragraph type="secondary" style={{ marginTop: 16, marginBottom: 0 }}>
              本摘要仍只基于当前修订版本返回字段；O04 几何/访问点与 O05 时间证据已在上方展示，来源冲突和关系裁决将在 O06–O07 页面接入后显示。
            </Typography.Paragraph>
          </Card>
        </>
      )}
      {revision === null && loading && <Card loading />}
      <Modal title="编辑候选修订版本" open={editOpen} onOk={() => void saveEdit()} onCancel={() => setEditOpen(false)} confirmLoading={working}>
        <Form form={form} layout="vertical">
          <Form.Item name="canonical_name" label="规范名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="address" label="地址"><Input /></Form.Item>
          <Form.Item name="duration_recommended" label="建议时长（分钟）" rules={[{ required: true, type: 'number', min: 1, message: '建议时长至少为 1 分钟' }]}><InputNumber min={1} style={{ width: '100%' }} /></Form.Item>
        </Form>
      </Modal>
    </Space>
  )
}

function EvidenceCard({
  api,
  evidence,
  loading,
  error,
  revision,
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
  canEdit: boolean
  canReview: boolean
  onSuccess: (text: string) => void
  onChanged: () => Promise<void>
  onError: (message: string) => void
}) {
  const editable = revision.lifecycle_status === 'candidate' && canEdit
  const reviewable = revision.lifecycle_status === 'candidate' && canReview
  const [modal, setModal] = useState<'geometry' | 'access' | null>(null)
  const [editing, setEditing] = useState<PlaceGeometryEvidence | PlaceAccessPointEvidence | null>(null)
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm()
  const openGeometry = (item?: PlaceGeometryEvidence) => { setEditing(item ?? null); form.setFieldsValue(item ? { geometry_kind: item.geometry_kind, geometry: JSON.stringify(item.geometry), source_record_id: item.source_record_id } : { geometry_kind: revision.geometry_kind }); setModal('geometry') }
  const openAccess = (item?: PlaceAccessPointEvidence) => { setEditing(item ?? null); form.setFieldsValue(item ? item : {}); setModal('access') }
  const saveEvidence = async () => {
    setSaving(true)
    try {
      const values = await form.validateFields()
      const base = { expected_revision_version: revision.revision_version, operation_intent_id: `evidence-${crypto.randomUUID()}`, reason_code: editing ? 'EVIDENCE_UPDATED' : 'EVIDENCE_CREATED' }
      if (modal === 'geometry') {
        const input: PlaceGeometryInput = { ...base, geometry_kind: values.geometry_kind, geometry: JSON.parse(values.geometry), source_record_id: values.source_record_id }
        if (editing) await api.updateGeometry(revision.place_revision_id, (editing as PlaceGeometryEvidence).geometry_id, input); else await api.createGeometry(revision.place_revision_id, input)
      } else {
        const input: PlaceAccessPointInput = { ...base, access_point_kind: values.access_point_kind, name: values.name, lat: values.lat, lng: values.lng, source_record_id: values.source_record_id }
        if (editing) await api.updateAccessPoint(revision.place_revision_id, (editing as PlaceAccessPointEvidence).access_point_id, input); else await api.createAccessPoint(revision.place_revision_id, input)
      }
      setModal(null); await onChanged(); onSuccess('证据已保存，修订版本需重新送审')
    } catch (reason) { if (!isFormValidationError(reason)) onError(adminErrorMessage(reason)) } finally { setSaving(false) }
  }
  const review = async (kind: 'geometry' | 'access_point', id: string, status: 'human_verified' | 'rejected') => {
    setSaving(true)
    try { await api.reviewEvidence(revision.place_revision_id, kind, id, { review_status: status, operation_intent_id: `evidence-review-${crypto.randomUUID()}`, reason_code: status === 'human_verified' ? 'EVIDENCE_APPROVED' : 'EVIDENCE_REJECTED' }); await onChanged(); onSuccess(status === 'human_verified' ? '证据已通过核验' : '证据已驳回') } catch (reason) { onError(adminErrorMessage(reason)) } finally { setSaving(false) }
  }
  const retire = async (kind: 'geometry' | 'access', id: string) => {
    setSaving(true)
    try { const input = { expected_revision_version: revision.revision_version, operation_intent_id: `evidence-retire-${crypto.randomUUID()}`, reason_code: 'EVIDENCE_RETIRED' }; if (kind === 'geometry') await api.retireGeometry(revision.place_revision_id, id, input); else await api.retireAccessPoint(revision.place_revision_id, id, input); await onChanged(); onSuccess('证据已停用，修订版本需重新送审') } catch (reason) { onError(adminErrorMessage(reason)) } finally { setSaving(false) }
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
  return (
    <Card title="地图、几何与访问点（O04）">
      <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
        <Descriptions bordered size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
          <Descriptions.Item label="来源证据">
            {evidence.sources.length > 0
              ? evidence.sources.map((source) => (
                  <Tag key={source.source_record_id}>
                    {source.source_id} · {sourceDecisionLabel(source.source_decision)}
                    {source.source_url_redacted ? ' · URL 已脱敏' : ''}
                  </Tag>
                ))
              : '未关联来源'}
          </Descriptions.Item>
          <Descriptions.Item label="几何记录数">{evidence.geometries.length}</Descriptions.Item>
          <Descriptions.Item label="访问点记录数">{evidence.access_points.length}</Descriptions.Item>
          <Descriptions.Item label="求解投影">
            {projection ? `${projection.projection_id} · ${projectionStatusLabel(projection.status)}` : '未准备'}
          </Descriptions.Item>
          <Descriptions.Item label="到达端点">
            {projection ? projection.arrival_access_point_id : '未选择'}
          </Descriptions.Item>
          <Descriptions.Item label="离开端点">
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
                  {JSON.stringify(value)}
                </Typography.Text>
              ),
            },
            {
              title: '来源记录',
              key: 'source_record_id',
              width: 240,
              render: (_: unknown, item) => (
                <Space size={4}>
                  <Typography.Text ellipsis={{ tooltip: item.source_record_id }}>
                    {item.source_record_id}
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
            ...((editable || reviewable) ? [{ title: '操作', key: 'actions', render: (_: unknown, item: PlaceGeometryEvidence) => <Space>{editable && <><Button size="small" icon={<EditOutlined />} onClick={() => openGeometry(item)}>编辑</Button>{item.active && <Button size="small" danger onClick={() => void retire('geometry', item.geometry_id)}>停用</Button>}</>}{reviewable && item.active && <><Button size="small" type="primary" onClick={() => void review('geometry', item.geometry_id, 'human_verified')}>通过</Button><Button size="small" onClick={() => void review('geometry', item.geometry_id, 'rejected')}>驳回</Button></>}</Space> }] : []),
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
            ...((editable || reviewable) ? [{ title: '操作', key: 'actions', render: (_: unknown, item: PlaceAccessPointEvidence) => <Space>{editable && <><Button size="small" icon={<EditOutlined />} onClick={() => openAccess(item)}>编辑</Button>{item.active && <Button size="small" danger onClick={() => void retire('access', item.access_point_id)}>停用</Button>}</>}{reviewable && item.active && <><Button size="small" type="primary" onClick={() => void review('access_point', item.access_point_id, 'human_verified')}>通过</Button><Button size="small" onClick={() => void review('access_point', item.access_point_id, 'rejected')}>驳回</Button></>}</Space> }] : []),
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
                  <Typography.Text ellipsis={{ tooltip: item.source_record_id }}>
                    {item.source_record_id}
                  </Typography.Text>
                  <Tag color={item.source_record_valid ? 'success' : 'error'}>
                    {item.source_record_valid ? '有效' : '无效'}
                  </Tag>
                </Space>
              ),
            },
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
      <Modal title={modal === 'geometry' ? '几何证据' : '访问点证据'} open={modal !== null} onOk={() => void saveEvidence()} onCancel={() => setModal(null)} confirmLoading={saving} destroyOnHidden>
        <Form form={form} layout="vertical">
          {modal === 'geometry' ? <><Form.Item name="geometry_kind" label="几何类型" rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="geometry" label="GeoJSON" rules={[{ required: true }]}><Input.TextArea rows={4} /></Form.Item><Form.Item name="source_record_id" label="来源记录 ID" rules={[{ required: true }]}><Input /></Form.Item></> : <><Form.Item name="access_point_kind" label="用途" rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="name" label="名称" rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="lat" label="纬度" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} /></Form.Item><Form.Item name="lng" label="经度" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} /></Form.Item><Form.Item name="source_record_id" label="来源记录 ID" rules={[{ required: true }]}><Input /></Form.Item></>}
        </Form>
      </Modal>
    </Card>
  )
}

function RelationEvidenceCard({ api, evidence, revision, canEdit, onChanged, onSuccess, onError }: {
  api: ReturnType<typeof useAdminSession>['api']
  evidence: PlaceRevisionEvidence | null
  revision: PlaceRevision
  canEdit: boolean
  onChanged: () => Promise<void>
  onSuccess: (text: string) => void
  onError: (message: string) => void
}) {
  const [editing, setEditing] = useState<PlaceRelationEvidence | null>(null)
  const [status, setStatus] = useState('resolved')
  const [note, setNote] = useState('')
  const [working, setWorking] = useState(false)
  const relations = evidence?.relations ?? []
  const save = async () => {
    if (!editing) return
    setWorking(true)
    try {
      await api.resolvePlaceRelation(revision.place_revision_id, editing.relation_id, {
        expected_revision_version: revision.revision_version,
        resolution_status: status,
        decision_note: note || null,
        operation_intent_id: `relation-resolution-${crypto.randomUUID()}`,
        reason_code: 'RELATION_RESOLUTION_UPDATED',
      })
      setEditing(null)
      await onChanged()
      onSuccess('关系裁决已保存，修订版本需重新送审')
    } catch (reason) { onError(adminErrorMessage(reason)) } finally { setWorking(false) }
  }
  return <Card title="地点关系与裁决（O07）">
    <Table<PlaceRelationEvidence> rowKey="relation_id" dataSource={relations} pagination={false} locale={{ emptyText: '当前地点暂无关系证据' }} columns={[
      { title: '关系类型', dataIndex: 'relation_type', render: relationTypeLabel },
      { title: '目标地点', render: (_: unknown, item: PlaceRelationEvidence) => `${item.from_place_id} → ${item.to_place_id}` },
      { title: '审核', dataIndex: 'review_status', render: reviewStatusLabel },
      { title: '裁决', dataIndex: 'resolution_status', render: relationResolutionLabel },
      { title: '来源', dataIndex: 'source_record_id' },
      ...(canEdit ? [{ title: '操作', render: (_: unknown, item: PlaceRelationEvidence) => <Button size="small" onClick={() => { setEditing(item); setStatus(item.resolution_status); setNote(item.decision_note ?? '') }}>裁决</Button> }] : []),
    ]} />
    <Modal title="关系裁决" open={editing !== null} onOk={() => void save()} onCancel={() => setEditing(null)} confirmLoading={working}>
      <Space orientation="vertical" style={{ width: '100%' }}>
        <Select value={status} onChange={setStatus} options={[{ value: 'resolved', label: '已裁决' }, { value: 'not_required', label: '无需裁决' }, { value: 'pending', label: '待处理' }]} />
        <Input.TextArea value={note} onChange={(event) => setNote(event.target.value)} placeholder="裁决说明（已裁决时必填）" rows={4} />
      </Space>
    </Modal>
  </Card>
}

function TimeEvidenceCard({
  api,
  evidence,
  loading,
  error,
  revision,
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
  canEdit: boolean
  canReview: boolean
  onSuccess: (text: string) => void
  onChanged: () => Promise<void>
  onError: (message: string) => void
}) {
  const editable = revision.lifecycle_status === 'candidate' && canEdit
  const reviewable = revision.lifecycle_status === 'candidate' && canReview
  const [modal, setModal] = useState<'time_rule' | 'closure' | 'date_exception' | null>(null)
  const [editing, setEditing] = useState<PlaceTimeRuleEvidence | PlaceClosureEvidence | PlaceDateExceptionEvidence | null>(null)
  const [saving, setSaving] = useState(false)
  const [previewDate, setPreviewDate] = useState('')
  const [preview, setPreview] = useState<PlaceTimePreview | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [form] = Form.useForm()

  const openEditor = (
    kind: 'time_rule' | 'closure' | 'date_exception',
    item?: PlaceTimeRuleEvidence | PlaceClosureEvidence | PlaceDateExceptionEvidence,
  ) => {
    setEditing(item ?? null)
    form.resetFields()
    if (kind === 'time_rule') {
      const rule = item as PlaceTimeRuleEvidence | undefined
      form.setFieldsValue(rule ?? { rule_kind: 'opening_hours', weekdays: [1, 2, 3, 4, 5] })
    } else if (kind === 'closure') {
      const closure = item as PlaceClosureEvidence | undefined
      form.setFieldsValue(closure ?? { weekday: 1 })
    } else {
      const exception = item as PlaceDateExceptionEvidence | undefined
      form.setFieldsValue(exception ?? { exception_kind: 'closed' })
    }
    setModal(kind)
  }

  const save = async () => {
    setSaving(true)
    try {
      const values = await form.validateFields()
      const base = {
        expected_revision_version: revision.revision_version,
        operation_intent_id: `time-evidence-${crypto.randomUUID()}`,
        reason_code: editing ? 'TIME_EVIDENCE_UPDATED' : 'TIME_EVIDENCE_CREATED',
      }
      if (modal === 'time_rule') {
        const input: PlaceTimeRuleInput = {
          ...base,
          rule_kind: values.rule_kind,
          weekdays: values.weekdays,
          start_minute: values.start_minute ?? null,
          end_minute: values.end_minute ?? null,
          last_entry_minute: values.last_entry_minute ?? null,
          valid_from: values.valid_from || null,
          valid_to: values.valid_to || null,
          source_record_id: values.source_record_id,
        }
        if (editing) await api.updateTimeRule(revision.place_revision_id, (editing as PlaceTimeRuleEvidence).time_rule_id, input)
        else await api.createTimeRule(revision.place_revision_id, input)
      } else if (modal === 'closure') {
        const input: PlaceClosureInput = {
          ...base,
          weekday: values.weekday,
          source_record_id: values.source_record_id,
        }
        if (editing) await api.updateClosure(revision.place_revision_id, (editing as PlaceClosureEvidence).closure_id, input)
        else await api.createClosure(revision.place_revision_id, input)
      } else if (modal === 'date_exception') {
        const input: PlaceDateExceptionInput = {
          ...base,
          service_date: values.service_date,
          exception_kind: values.exception_kind,
          start_minute: values.start_minute ?? null,
          end_minute: values.end_minute ?? null,
          last_entry_minute: values.last_entry_minute ?? null,
          source_record_id: values.source_record_id,
        }
        if (editing) await api.updateDateException(revision.place_revision_id, (editing as PlaceDateExceptionEvidence).date_exception_id, input)
        else await api.createDateException(revision.place_revision_id, input)
      }
      setModal(null)
      await onChanged()
      onSuccess('时间证据已保存，修订版本需重新送审')
    } catch (reason) {
      if (!isFormValidationError(reason)) onError(adminErrorMessage(reason))
    } finally {
      setSaving(false)
    }
  }

  const review = async (
    kind: 'time_rule' | 'closure' | 'date_exception',
    id: string,
    status: 'human_verified' | 'rejected',
  ) => {
    setSaving(true)
    try {
      await api.reviewEvidence(revision.place_revision_id, kind, id, {
        review_status: status,
        operation_intent_id: `time-evidence-review-${crypto.randomUUID()}`,
        reason_code: status === 'human_verified' ? 'EVIDENCE_APPROVED' : 'EVIDENCE_REJECTED',
      })
      await onChanged()
      onSuccess(status === 'human_verified' ? '时间证据已通过核验' : '时间证据已驳回')
    } catch (reason) {
      onError(adminErrorMessage(reason))
    } finally {
      setSaving(false)
    }
  }

  const retire = async (
    kind: 'time_rule' | 'closure' | 'date_exception',
    id: string,
  ) => {
    setSaving(true)
    try {
      const input = {
        expected_revision_version: revision.revision_version,
        operation_intent_id: `time-evidence-retire-${crypto.randomUUID()}`,
        reason_code: 'TIME_EVIDENCE_RETIRED',
      }
      if (kind === 'time_rule') await api.retireTimeRule(revision.place_revision_id, id, input)
      else if (kind === 'closure') await api.retireClosure(revision.place_revision_id, id, input)
      else await api.retireDateException(revision.place_revision_id, id, input)
      await onChanged()
      onSuccess('时间证据已停用，修订版本需重新送审')
    } catch (reason) {
      onError(adminErrorMessage(reason))
    } finally {
      setSaving(false)
    }
  }
  const runPreview = async () => {
    if (!previewDate) return
    setPreviewLoading(true)
    try { setPreview(await api.previewPlaceRevisionTime(revision.place_revision_id, previewDate)) }
    catch (reason) { onError(adminErrorMessage(reason)) }
    finally { setPreviewLoading(false) }
  }
  if (loading) return <Card title="开放时间与固定场次（O05）" loading />
  if (error !== null || evidence === null) {
    return (
      <Card title="开放时间与固定场次（O05）">
        <Alert
          showIcon
          type="warning"
          title="O05 时间证据暂不可用"
            description={error ?? '当前修订版本没有可读取的时间证据'}
        />
      </Card>
    )
  }
  return (
    <Card title="开放时间与固定场次（O05）">
      <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
        <Alert
          showIcon
          type="info"
          title="时间证据严格绑定当前修订版本"
          description="编辑会递增修订版本并清除既有审核/求解资格；逐项核验要求先建立开放审核任务。解析预览由后端按已核验证据计算。"
        />
        <Space wrap>
          <Input type="date" value={previewDate} onChange={(event) => setPreviewDate(event.target.value)} />
          <Button onClick={() => void runPreview()} loading={previewLoading} disabled={!previewDate}>解析预览</Button>
        </Space>
        {preview && <Card size="small" title={`${preview.service_date}：${preview.open ? '开放' : '闭馆'}`}>
          <Space orientation="vertical">
            <Typography.Text>时间窗口：{preview.windows.length ? preview.windows.map((window) => `${window.start_minute ?? '-'}–${window.end_minute ?? '-'}（末入 ${window.last_entry_minute ?? '-'}）`).join('；') : '无'}</Typography.Text>
            <Typography.Text>固定场次：{preview.fixed_sessions.length ? preview.fixed_sessions.map((session) => `${session.start_minute}–${session.end_minute}`).join('；') : '无'}</Typography.Text>
            <Typography.Text>解析码：{preview.reason_codes.length ? preview.reason_codes.join('、') : '无'}</Typography.Text>
          </Space>
        </Card>}
        <Space style={{ width: '100%', justifyContent: 'space-between' }}><Typography.Title level={5} style={{ margin: 0 }}>周规则与固定场次</Typography.Title>{editable && <Button size="small" icon={<PlusOutlined />} onClick={() => openEditor('time_rule')}>新增</Button>}</Space>
        <Table<PlaceTimeRuleEvidence>
          rowKey="time_rule_id"
          size="small"
          pagination={false}
          dataSource={evidence.time_rules}
          scroll={{ x: 1050 }}
          columns={[
            { title: '规则类型', dataIndex: 'rule_kind', width: 150, render: timeRuleKindLabel },
            { title: '适用星期', dataIndex: 'weekdays', width: 180, render: (days: number[]) => days.map(weekdayLabel).join('、') },
            { title: '开放/场次', key: 'window', width: 190, render: (_: unknown, item) => `${minuteLabel(item.start_minute)} – ${minuteLabel(item.end_minute)}` },
            { title: '最晚入园', dataIndex: 'last_entry_minute', width: 120, render: minuteLabel },
            { title: '有效期', key: 'validity', width: 220, render: (_: unknown, item) => `${item.valid_from ?? '不限'} – ${item.valid_to ?? '不限'}` },
            { title: '状态', dataIndex: 'review_status', width: 130, render: (value: string, item) => <Space size={4}><Tag color={reviewStatusColor(value)}>{reviewStatusLabel(value)}</Tag>{!item.active && <Tag>已停用</Tag>}</Space> },
            { title: '来源', key: 'source', width: 220, render: (_: unknown, item) => <Space size={4}><Typography.Text>{item.source_record_id}</Typography.Text><Tag color={item.source_record_valid ? 'success' : 'error'}>{item.source_record_valid ? '有效' : '无效'}</Tag></Space> },
            ...((editable || reviewable) ? [{ title: '操作', key: 'actions', width: 280, render: (_: unknown, item: PlaceTimeRuleEvidence) => <Space>{editable && <><Button size="small" icon={<EditOutlined />} onClick={() => openEditor('time_rule', item)}>编辑</Button>{item.active && <Button size="small" danger onClick={() => void retire('time_rule', item.time_rule_id)}>停用</Button>}</>}{reviewable && item.active && <><Button size="small" type="primary" onClick={() => void review('time_rule', item.time_rule_id, 'human_verified')}>通过</Button><Button size="small" onClick={() => void review('time_rule', item.time_rule_id, 'rejected')}>驳回</Button></>}</Space> }] : []),
          ]}
          locale={{ emptyText: evidence.revision.is_always_open ? '全天开放，无需周时间窗' : '尚未采集周规则或固定场次' }}
        />
        <Space style={{ width: '100%', justifyContent: 'space-between' }}><Typography.Title level={5} style={{ margin: 0 }}>固定闭馆日</Typography.Title>{editable && <Button size="small" icon={<PlusOutlined />} onClick={() => openEditor('closure')}>新增</Button>}</Space>
        <Table<PlaceClosureEvidence>
          rowKey="closure_id"
          size="small"
          pagination={false}
          dataSource={evidence.closures}
          columns={[
            { title: '闭馆星期', dataIndex: 'weekday', render: weekdayLabel },
            { title: '状态', dataIndex: 'review_status', render: (value: string, item) => <Space size={4}><Tag color={reviewStatusColor(value)}>{reviewStatusLabel(value)}</Tag>{!item.active && <Tag>已停用</Tag>}</Space> },
            { title: '来源', key: 'source', render: (_: unknown, item) => <Space size={4}>{item.source_record_id}<Tag color={item.source_record_valid ? 'success' : 'error'}>{item.source_record_valid ? '有效' : '无效'}</Tag></Space> },
            ...((editable || reviewable) ? [{ title: '操作', key: 'actions', width: 280, render: (_: unknown, item: PlaceClosureEvidence) => <Space>{editable && <><Button size="small" icon={<EditOutlined />} onClick={() => openEditor('closure', item)}>编辑</Button>{item.active && <Button size="small" danger onClick={() => void retire('closure', item.closure_id)}>停用</Button>}</>}{reviewable && item.active && <><Button size="small" type="primary" onClick={() => void review('closure', item.closure_id, 'human_verified')}>通过</Button><Button size="small" onClick={() => void review('closure', item.closure_id, 'rejected')}>驳回</Button></>}</Space> }] : []),
          ]}
          locale={{ emptyText: '没有固定闭馆日记录' }}
        />
        <Space style={{ width: '100%', justifyContent: 'space-between' }}><Typography.Title level={5} style={{ margin: 0 }}>日期例外</Typography.Title>{editable && <Button size="small" icon={<PlusOutlined />} onClick={() => openEditor('date_exception')}>新增</Button>}</Space>
        <Table<PlaceDateExceptionEvidence>
          rowKey="date_exception_id"
          size="small"
          pagination={false}
          dataSource={evidence.date_exceptions}
          scroll={{ x: 900 }}
          columns={[
            { title: '日期', dataIndex: 'service_date', width: 130 },
            { title: '例外类型', dataIndex: 'exception_kind', width: 150, render: dateExceptionKindLabel },
            { title: '覆盖时间', key: 'window', width: 190, render: (_: unknown, item) => item.exception_kind === 'closed' ? '全天关闭' : `${minuteLabel(item.start_minute)} – ${minuteLabel(item.end_minute)}` },
            { title: '最晚入园', dataIndex: 'last_entry_minute', width: 120, render: minuteLabel },
            { title: '状态', dataIndex: 'review_status', width: 130, render: (value: string, item) => <Space size={4}><Tag color={reviewStatusColor(value)}>{reviewStatusLabel(value)}</Tag>{!item.active && <Tag>已停用</Tag>}</Space> },
            { title: '来源', key: 'source', width: 220, render: (_: unknown, item) => <Space size={4}>{item.source_record_id}<Tag color={item.source_record_valid ? 'success' : 'error'}>{item.source_record_valid ? '有效' : '无效'}</Tag></Space> },
            ...((editable || reviewable) ? [{ title: '操作', key: 'actions', width: 280, render: (_: unknown, item: PlaceDateExceptionEvidence) => <Space>{editable && <><Button size="small" icon={<EditOutlined />} onClick={() => openEditor('date_exception', item)}>编辑</Button>{item.active && <Button size="small" danger onClick={() => void retire('date_exception', item.date_exception_id)}>停用</Button>}</>}{reviewable && item.active && <><Button size="small" type="primary" onClick={() => void review('date_exception', item.date_exception_id, 'human_verified')}>通过</Button><Button size="small" onClick={() => void review('date_exception', item.date_exception_id, 'rejected')}>驳回</Button></>}</Space> }] : []),
          ]}
          locale={{ emptyText: '没有日期例外记录' }}
        />
      </Space>
      <Modal title={timeEvidenceModalTitle(modal)} open={modal !== null} onOk={() => void save()} onCancel={() => setModal(null)} confirmLoading={saving} forceRender>
        <Form form={form} layout="vertical">
          {modal === 'time_rule' && <>
            <Form.Item name="rule_kind" label="规则类型" rules={[{ required: true }]}><Select options={[{ value: 'opening_hours', label: '开放时间' }, { value: 'fixed_session', label: '固定场次' }, { value: 'last_entry', label: '最晚入园规则' }]} /></Form.Item>
            <Form.Item name="weekdays" label="适用星期" rules={[{ required: true }]}><Select mode="multiple" options={weekdayOptions()} /></Form.Item>
            <MinuteFields />
            <Form.Item name="valid_from" label="有效期开始"><Input placeholder="YYYY-MM-DD" /></Form.Item>
            <Form.Item name="valid_to" label="有效期结束"><Input placeholder="YYYY-MM-DD" /></Form.Item>
            <SourceRecordField />
          </>}
          {modal === 'closure' && <>
            <Form.Item name="weekday" label="闭馆星期" rules={[{ required: true }]}><Select options={weekdayOptions()} /></Form.Item>
            <SourceRecordField />
          </>}
          {modal === 'date_exception' && <>
            <Form.Item name="service_date" label="例外日期" rules={[{ required: true }]}><Input placeholder="YYYY-MM-DD" /></Form.Item>
            <Form.Item name="exception_kind" label="例外类型" rules={[{ required: true }]}><Select options={[{ value: 'closed', label: '临时关闭' }, { value: 'open_override', label: '开放覆盖' }, { value: 'session_override', label: '场次覆盖' }]} /></Form.Item>
            <MinuteFields />
            <SourceRecordField />
          </>}
        </Form>
      </Modal>
    </Card>
  )
}

function minuteLabel(value: number | null): string {
  if (value === null) return '未设置'
  const dayOffset = Math.floor(value / 1440)
  const minute = value % 1440
  const time = `${String(Math.floor(minute / 60)).padStart(2, '0')}:${String(minute % 60).padStart(2, '0')}`
  return dayOffset > 0 ? `次日 ${time} (+${dayOffset * 1440})` : time
}

function MinuteFields() {
  return <>
    <Alert showIcon type="info" title="时间使用 0–2880 分钟" description="例如 09:30 = 570；跨午夜后的次日 00:30 = 1470。临时关闭无需填写时间。" />
    <Form.Item name="start_minute" label="开始分钟"><InputNumber min={0} max={2880} style={{ width: '100%' }} /></Form.Item>
    <Form.Item name="end_minute" label="结束分钟"><InputNumber min={0} max={2880} style={{ width: '100%' }} /></Form.Item>
    <Form.Item name="last_entry_minute" label="最晚入园分钟"><InputNumber min={0} max={2880} style={{ width: '100%' }} /></Form.Item>
  </>
}

function SourceRecordField() {
  return <Form.Item name="source_record_id" label="来源记录 ID" rules={[{ required: true }]}><Input /></Form.Item>
}

function weekdayOptions() {
  return [1, 2, 3, 4, 5, 6, 7].map((value) => ({ value, label: weekdayLabel(value) }))
}

function timeEvidenceModalTitle(kind: 'time_rule' | 'closure' | 'date_exception' | null): string {
  if (kind === 'time_rule') return '周规则或固定场次'
  if (kind === 'closure') return '固定闭馆日'
  if (kind === 'date_exception') return '日期例外'
  return '时间证据'
}

function weekdayLabel(value: number): string {
  return ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][value - 1] ?? `星期${value}`
}

function reviewStatusColor(value: string): string | undefined {
  if (value === 'human_verified') return 'success'
  if (value === 'rejected') return 'error'
  return undefined
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

function publicationBlockers(revision: PlaceRevision): string[] {
  const blockers: string[] = []
  if (revision.lifecycle_status === 'candidate') blockers.push('尚未完成人工核验，当前仍为候选状态')
  if (revision.source_record_ids.length === 0) blockers.push('缺少来源记录')
  if (!revision.conflicts_resolved) blockers.push('存在未完成裁决的冲突')
  if (!revision.solver_eligible) blockers.push('当前修订版本尚不满足求解器使用条件')
  return blockers
}

function formatOptionalDateTime(value: string | null): string {
  return value ? formatDateTime(value) : '未发生'
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'medium',
    hour12: false,
  }).format(new Date(value))
}

function isFormValidationError(value: unknown): boolean {
  return typeof value === 'object' && value !== null && 'errorFields' in value
}
