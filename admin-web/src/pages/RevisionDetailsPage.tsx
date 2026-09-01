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
  ExclamationCircleFilled,
} from '@ant-design/icons'
import { Alert, App as AntApp, Button, Card, Collapse, Descriptions, Form, Input, InputNumber, Modal, Select, Space, Switch, Table, Tag, Tooltip, Typography } from 'antd'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'

import { adminErrorMessage } from '../api/errorMessages'
import type { PlaceAccessPointEvidence, PlaceAccessPointInput, PlaceClosureEvidence, PlaceClosureInput, PlaceDateExceptionEvidence, PlaceDateExceptionInput, PlaceGeometryEvidence, PlaceGeometryInput, PlaceRevision, PlaceRevisionEvidence, PlaceTimeRuleEvidence, PlaceTimeRuleInput, PlaceTimePreview, PlaceRelationEvidence, ReviewTask, PublicationCheck, SourceConflict } from '../api/types'
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
  relationReviewStatusLabel,
  relationTypeLabel,
  reasonCodeLabel,
  reviewFlagLabel,
  reviewStatusLabel,
  sourceDecisionLabel,
  timeRuleKindLabel,
} from '../ui/displayLabels'

export type GeometryFormValues = {
  geometry_kind: 'point' | 'area' | 'route'
  geometry_lat?: number
  geometry_lng?: number
  geometry_coordinates?: string
  source_record_id: string
}

export function geometryFormValues(item: PlaceGeometryEvidence | undefined, fallbackKind: string, sourceRecordId?: string): Partial<GeometryFormValues> {
  if (!item) return { geometry_kind: fallbackKind as GeometryFormValues['geometry_kind'], source_record_id: sourceRecordId }
  const payload = item.geometry as { type?: string; coordinates?: unknown; lat?: number; lng?: number }
  const coordinates = payload.coordinates
  if (item.geometry_kind === 'point') {
    const point = Array.isArray(coordinates) && coordinates.length >= 2
      ? coordinates
      : [payload.lng, payload.lat]
    return {
      geometry_kind: 'point',
      geometry_lng: typeof point[0] === 'number' ? point[0] : undefined,
      geometry_lat: typeof point[1] === 'number' ? point[1] : undefined,
      source_record_id: item.source_record_id,
    }
  }
  const line = item.geometry_kind === 'area'
    ? (Array.isArray(coordinates) && Array.isArray(coordinates[0]) ? coordinates[0] : coordinates)
    : coordinates
  const lines = Array.isArray(line)
    ? line.filter((pair): pair is [number, number] => Array.isArray(pair) && pair.length >= 2 && typeof pair[0] === 'number' && typeof pair[1] === 'number').map((pair) => `${pair[0]}, ${pair[1]}`).join('\n')
    : ''
  return { geometry_kind: item.geometry_kind as GeometryFormValues['geometry_kind'], geometry_coordinates: lines, source_record_id: item.source_record_id }
}

export function geometryPayload(values: GeometryFormValues): Record<string, unknown> {
  if (values.geometry_kind === 'point') {
    if (typeof values.geometry_lng !== 'number' || typeof values.geometry_lat !== 'number') throw new Error('请填写完整的经度和纬度')
    if (values.geometry_lng < -180 || values.geometry_lng > 180) throw new Error('请输入 -180 到 180 之间的经度')
    if (values.geometry_lat < -90 || values.geometry_lat > 90) throw new Error('请输入 -90 到 90 之间的纬度')
    return { type: 'Point', coordinates: [values.geometry_lng, values.geometry_lat] }
  }
  const points = (values.geometry_coordinates ?? '').split(/\r?\n/).map((line) => line.trim()).filter(Boolean).map((line) => {
    const pair = line.split(/[,，\s]+/).filter(Boolean).map(Number)
    if (pair.length !== 2 || pair.some((value) => !Number.isFinite(value) || value < -180 || value > 180)) throw new Error('边界/路线坐标必须逐行填写“经度, 纬度”')
    if (pair[1] < -90 || pair[1] > 90) throw new Error('纬度必须在 -90 到 90 之间')
    return pair
  })
  const minimum = values.geometry_kind === 'area' ? 3 : 2
  if (points.length < minimum) throw new Error(`${values.geometry_kind === 'area' ? '区域边界' : '路线轨迹'}至少需要 ${minimum} 个坐标点`)
  if (values.geometry_kind === 'area' && (points[0][0] !== points.at(-1)?.[0] || points[0][1] !== points.at(-1)?.[1])) points.push(points[0])
  return values.geometry_kind === 'area'
    ? { type: 'Polygon', coordinates: [points] }
    : { type: 'LineString', coordinates: points }
}

export function geometrySummary(value: Record<string, unknown>): string {
  const type = typeof value.type === 'string' ? value.type : ''
  const coordinates = value.coordinates
  if (Array.isArray(coordinates) && coordinates.length >= 2 && (type === 'Point' || !type)) {
    return `点位：经度 ${coordinates[0]}，纬度 ${coordinates[1]}`
  }
  if ((type === 'Point' || !type) && typeof value.lat === 'number' && typeof value.lng === 'number') {
    return `点位：经度 ${value.lng}，纬度 ${value.lat}`
  }
  if (type === 'Polygon' && Array.isArray(coordinates) && Array.isArray(coordinates[0])) {
    return `区域边界：${coordinates[0].length} 个坐标点`
  }
  if (type === 'LineString' && Array.isArray(coordinates)) {
    return `路线轨迹：${coordinates.length} 个坐标点`
  }
  return '图形数据已保存（可在编辑中查看原始数据）'
}

export function RevisionDetailsPage() {
  const { api, hasPermission } = useAdminSession()
  const { message: messageApi } = AntApp.useApp()
  const navigate = useNavigate()
  const location = useLocation()
  const { revisionId } = useParams<{ revisionId: string }>()
  const reviewQuery = useMemo(() => new URLSearchParams(location.search), [location.search])
  const reviewContext = reviewQuery.get('from') === 'review'
  const reviewTaskId = reviewQuery.get('task')
  const canCheckPublication = hasPermission('place:publication:check')
  const [revision, setRevision] = useState<PlaceRevision | null>(null)
  const [evidence, setEvidence] = useState<PlaceRevisionEvidence | null>(null)
  const [reviewTask, setReviewTask] = useState<ReviewTask | null>(null)
  const [sourceConflicts, setSourceConflicts] = useState<SourceConflict[]>([])
  const [sourceConflictError, setSourceConflictError] = useState<string | null>(null)
  const [publicationCheck, setPublicationCheck] = useState<PublicationCheck | null>(null)
  const [publicationCheckError, setPublicationCheckError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [evidenceLoading, setEvidenceLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [evidenceError, setEvidenceError] = useState<string | null>(null)
  const [editOpen, setEditOpen] = useState(false)
  const [resolveConflictOpen, setResolveConflictOpen] = useState(false)
  const [resolveConflictNote, setResolveConflictNote] = useState('')
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
    setSourceConflictError(null)
    setPublicationCheckError(null)
    setSourceConflicts([])
    setPublicationCheck(null)
    setReviewTask(null)

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

    const reviewTaskRequest = reviewContext && reviewTaskId
      ? api.getReviewTask(reviewTaskId)
        .then((task) => {
          if (task.place_revision_id !== revisionId) throw new Error('审核任务与修订版本不匹配')
          setReviewTask(task)
        })
        .catch((reason: unknown) => setError(adminErrorMessage(reason)))
      : Promise.resolve()

    const sourceConflictRequest = typeof api.listSourceConflicts === 'function'
      ? api.listSourceConflicts(revisionId)
        .then((result) => setSourceConflicts(result.items))
        .catch((reason: unknown) => setSourceConflictError(adminErrorMessage(reason)))
      : Promise.resolve()

    const publicationCheckRequest = canCheckPublication && typeof api.checkPlaceRevisionPublication === 'function'
      ? api.checkPlaceRevisionPublication(revisionId)
        .then((result) => setPublicationCheck(result))
        .catch((reason: unknown) => setPublicationCheckError(adminErrorMessage(reason)))
      : Promise.resolve()

    await Promise.all([revisionRequest, evidenceRequest, reviewTaskRequest, sourceConflictRequest, publicationCheckRequest])
  }, [api, canCheckPublication, revisionId, reviewContext, reviewTaskId])

  useEffect(() => {
    void load()
  }, [load])

  const blockers = useMemo(
    () => revision ? buildPublicationBlockers(revision, evidence, sourceConflicts, publicationCheck) : [],
    [revision, evidence, sourceConflicts, publicationCheck],
  )
  const canReviewThisRevision = reviewContext && hasPermission('place:review:decide')
  const reviewTaskOpen = reviewTask !== null && ['ready_for_review', 'in_review', 'changes_requested'].includes(reviewTask.status)

  const decideReview = async (decisionKind: 'approve' | 'request_changes' | 'cancel') => {
    if (!reviewTask) return
    setWorking(true)
    try {
      await api.decidePlaceReview(reviewTask.review_task_id, {
        expected_version: reviewTask.version,
        decision_kind: decisionKind,
        reason_code: decisionKind === 'approve' ? 'OM1_FACTS_VERIFIED' : decisionKind === 'request_changes' ? 'OM1_REVIEW_CHANGES' : 'OM1_REVIEW_CANCELLED',
      })
      messageApi.success(decisionKind === 'approve' ? '审核已通过' : decisionKind === 'request_changes' ? '已退回修改' : '审核任务已关闭')
      await load()
    } catch (reason) {
      setError(adminErrorMessage(reason))
    } finally {
      setWorking(false)
    }
  }

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

  const resolveSourceConflicts = async () => {
    if (!revision || !resolveConflictNote.trim() || typeof api.resolveSourceConflicts !== 'function') return
    setWorking(true)
    try {
      await api.resolveSourceConflicts(revision.place_revision_id, {
        expected_revision_number: revision.revision_number,
        expected_revision_version: revision.revision_version,
        resolved: true,
        operation_intent_id: `source-conflicts-resolve-${crypto.randomUUID()}`,
        reason_code: 'SOURCE_CONFLICTS_REVIEWED',
        reason_text: resolveConflictNote.trim(),
      })
      setResolveConflictOpen(false)
      setResolveConflictNote('')
      messageApi.success('来源冲突已标记为处理完成，修订版本需要重新送审')
      await load()
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
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(reviewContext ? '/review' : '/candidates')}>
            {reviewContext ? '返回地点审核' : '返回候选地点'}
          </Button>
          {canReviewThisRevision && reviewTaskOpen && (
            <Space.Compact id="review-actions">
              <Button type="primary" icon={<CheckCircleOutlined />} onClick={() => void decideReview('approve')} loading={working}>
                审核通过
              </Button>
              <Button icon={<EditOutlined />} onClick={() => void decideReview('request_changes')} loading={working}>
                退回修改
              </Button>
              <Button danger onClick={() => void decideReview('cancel')} loading={working}>
                关闭任务
              </Button>
            </Space.Compact>
          )}
          {!reviewContext && revision && revision.lifecycle_status === 'candidate' &&
            (hasPermission('place:candidate:write') ||
              hasPermission('place:review:request')) && (
            <Space.Compact>
              {hasPermission('place:candidate:write') && (
              <Button icon={<EditOutlined />} onClick={() => { form.setFieldsValue({
                canonical_name: revision.canonical_name,
                aliases: revision.aliases,
                place_kind: revision.place_kind,
                category: revision.category,
                admin_area: revision.admin_area,
                address: revision.address,
                geometry_kind: revision.geometry_kind,
                duration_min: revision.duration_min,
                duration_recommended: revision.duration_recommended,
                duration_max: revision.duration_max,
                internal_travel_min: revision.internal_travel_min,
                energy_level: revision.energy_level,
                indoor_outdoor: revision.indoor_outdoor,
                suitable_periods: revision.suitable_periods,
                audience_tags: revision.audience_tags,
                rain_suitability: revision.rain_suitability,
                is_always_open: revision.is_always_open,
              }); setEditOpen(true) }}>
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
                        {reviewFlagLabel(flag)}
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

          <VerificationSummaryCard evidence={evidence} revision={revision} />

          <div id="o04-evidence"><EvidenceCard
            api={api}
            evidence={evidence}
            loading={evidenceLoading}
            error={evidenceError}
            revision={revision}
            canEdit={hasPermission('place:candidate:write')}
            canReview={canReviewThisRevision}
            onSuccess={(text) => messageApi.success(text)}
            onChanged={load}
            onError={setError}
          /></div>
          <div id="o05-evidence"><TimeEvidenceCard
            api={api}
            evidence={evidence}
            loading={evidenceLoading}
            error={evidenceError}
            revision={revision}
            canEdit={hasPermission('place:candidate:write')}
            canReview={canReviewThisRevision}
            onSuccess={(text) => messageApi.success(text)}
            onChanged={load}
            onError={setError}
          /></div>
          <div id="o07-evidence"><RelationEvidenceCard api={api} evidence={evidence} revision={revision} canEdit={hasPermission('place:candidate:write')} onChanged={load} onSuccess={(text) => messageApi.success(text)} onError={setError} /></div>
          <div id="o06-source-conflicts"><SourceConflictCard
            conflicts={sourceConflicts}
            loading={loading}
            error={sourceConflictError}
            unresolved={!revision.conflicts_resolved}
            canResolve={revision.lifecycle_status === 'candidate' && hasPermission('place:candidate:write')}
            onResolve={() => { setResolveConflictNote(''); setResolveConflictOpen(true) }}
          /></div>

          <Card title="发布阻断摘要">
            {blockers.length === 0 ? (
              <Alert showIcon type="success" icon={<CheckCircleOutlined />} title={publicationCheck?.publishable === false ? '当前仍有发布门禁原因，请查看下方明细' : '当前修订版本没有识别出的阻断项'} />
            ) : (
              <Space orientation="vertical" style={{ width: '100%' }}>
                <Alert showIcon type="warning" title={`当前有 ${blockers.length} 项需要处理`} />
                {blockers.map((blocker) => (
                  <div key={blocker.code} className="publication-blocker-item">
                    <Space orientation="vertical" size={4} style={{ width: '100%' }}>
                      <Typography.Text strong><CloseCircleOutlined style={{ color: '#cf1322' }} /> {blocker.title}</Typography.Text>
                      <Typography.Text type="secondary">{blocker.description}</Typography.Text>
                      {blocker.actionLabel && blocker.target && <Button size="small" type="link" onClick={() => document.getElementById(blocker.target!)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>{blocker.actionLabel}</Button>}
                    </Space>
                  </div>
                ))}
            </Space>
            )}
            {publicationCheckError && <Alert showIcon type="info" title="发布门禁暂时无法读取" description={publicationCheckError} />}
            {publicationCheck && publicationCheck.reason_codes.length > 0 && (
              <Alert
                showIcon
                type="warning"
                title="发布门禁检查结果"
                description={<Space wrap>{publicationCheck.reason_codes.map((code) => <Tag key={code} color="warning">{reasonCodeLabel(code)}</Tag>)}</Space>}
                style={{ marginTop: 12 }}
              />
            )}
            <Typography.Paragraph type="secondary" style={{ marginTop: 16, marginBottom: 0 }}>
              每个阻断项都对应一个证据区域。数据编辑员处理证据或来源冲突后需要重新送审；审核员完成逐项核验并通过修订版本审核；发布员再准备求解投影、通过发布门禁并发布新快照。
            </Typography.Paragraph>
          </Card>
        </>
      )}
      {revision === null && loading && <Card loading />}
      <Modal
        title="编辑候选修订版本"
        open={editOpen}
        onOk={() => void saveEdit()}
        onCancel={() => setEditOpen(false)}
        confirmLoading={working}
        width={760}
        className="revision-edit-modal"
        forceRender
      >
        <Form form={form} layout="vertical">
          <section className="revision-edit-section">
            <Typography.Title level={5}>基础信息</Typography.Title>
            <div className="revision-edit-grid">
              <Form.Item name="canonical_name" label="规范名称" rules={[{ required: true }]}><Input /></Form.Item>
              <Form.Item name="place_kind" label="地点类型" rules={[{ required: true }]}><Select options={[
                ['attraction', '景点'], ['scenic_area', '景区'], ['neighborhood', '街区'],
                ['walking_route', '步行路线'], ['market', '市集'], ['show', '演出/固定场次'], ['experience', '体验'],
              ].map(([value, label]) => ({ value, label }))} /></Form.Item>
              <Form.Item name="aliases" label="别名"><Select mode="tags" tokenSeparators={[',', '，']} placeholder="可输入多个别名" /></Form.Item>
              <Form.Item name="category" label="分类" rules={[{ required: true }]}><Input /></Form.Item>
              <Form.Item name="admin_area" label="所属区域" rules={[{ required: true }]}><Input /></Form.Item>
              <Form.Item name="geometry_kind" label="几何类型" rules={[{ required: true }]}><Select options={[{ value: 'point', label: '点' }, { value: 'area', label: '区域' }, { value: 'route', label: '路线' }]} /></Form.Item>
              <Form.Item name="address" label="地址" className="revision-edit-wide"><Input /></Form.Item>
            </div>
          </section>

          <section className="revision-edit-section">
            <Typography.Title level={5}>游览与求解</Typography.Title>
            <div className="revision-edit-grid revision-edit-duration-grid">
              <Form.Item name="duration_min" label="最短时长（分钟）" rules={[{ required: true, type: 'number', min: 0 }]}><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
              <Form.Item name="duration_recommended" label="建议时长（分钟）" rules={[{ required: true, type: 'number', min: 1, message: '建议时长至少为 1 分钟' }]}><InputNumber min={1} style={{ width: '100%' }} /></Form.Item>
              <Form.Item name="duration_max" label="最长时长（分钟）" rules={[{ required: true, type: 'number', min: 0 }]}><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
              <Form.Item name="internal_travel_min" label="内部移动时长（分钟）" rules={[{ required: true, type: 'number', min: 0 }]}><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
              <Form.Item name="energy_level" label="体力等级" rules={[{ required: true, type: 'number', min: 1, max: 5 }]}><InputNumber min={1} max={5} style={{ width: '100%' }} /></Form.Item>
              <Form.Item name="is_always_open" label="全天开放" valuePropName="checked"><Switch /></Form.Item>
            </div>
            <Typography.Text type="secondary">建议时长必须位于最短和最长时长之间；求解器会优先采用建议时长，并在时间窗不足时按区间进行调整。</Typography.Text>
          </section>

          <section className="revision-edit-section">
            <Typography.Title level={5}>体验标签</Typography.Title>
            <div className="revision-edit-grid">
              <Form.Item name="indoor_outdoor" label="室内/室外" rules={[{ required: true }]}><Select options={[{ value: 'indoor', label: '室内' }, { value: 'outdoor', label: '室外' }, { value: 'mixed', label: '室内外兼有' }]} /></Form.Item>
              <Form.Item name="rain_suitability" label="雨天适配" rules={[{ required: true }]}><Select options={[{ value: 'suitable', label: '适合' }, { value: 'conditional', label: '有条件通过' }, { value: 'unsuitable', label: '不适合' }]} /></Form.Item>
              <Form.Item name="suitable_periods" label="适用时段"><Select mode="multiple" options={[{ value: 'morning', label: '上午' }, { value: 'afternoon', label: '下午' }, { value: 'evening', label: '晚上' }]} /></Form.Item>
              <Form.Item name="audience_tags" label="适合人群"><Select mode="tags" tokenSeparators={[',', '，']} placeholder="可输入多个标签" /></Form.Item>
            </div>
          </section>
        </Form>
      </Modal>
      <Modal
        title="处理来源冲突"
        open={resolveConflictOpen}
        onOk={() => void resolveSourceConflicts()}
        onCancel={() => setResolveConflictOpen(false)}
        confirmLoading={working}
        okButtonProps={{ disabled: !resolveConflictNote.trim() }}
      >
        <Typography.Paragraph type="secondary">
          请先在 O06 区域核对每条来源记录，再填写裁决依据。提交后会递增修订版本并清除当前审核/求解资格，需要重新送审。
        </Typography.Paragraph>
        <Input.TextArea value={resolveConflictNote} onChange={(event) => setResolveConflictNote(event.target.value)} placeholder="例如：以景区官方公告为准，第三方记录为旧版本" rows={4} maxLength={500} showCount />
      </Modal>
    </Space>
  )
}

function SourceConflictCard({
  conflicts,
  loading,
  error,
  unresolved,
  canResolve,
  onResolve,
}: {
  conflicts: SourceConflict[]
  loading: boolean
  error: string | null
  unresolved: boolean
  canResolve: boolean
  onResolve: () => void
}) {
  return (
    <Card title="来源冲突与裁决（O06）">
      {loading ? <Card loading size="small" /> : error ? (
        <Alert showIcon type="warning" title="来源冲突暂不可用" description={error} />
      ) : conflicts.length === 0 ? (
        <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
          <Alert showIcon type={unresolved ? 'warning' : 'success'} title={unresolved ? '尚未确认来源冲突检查结果' : '当前没有检测到来源内容冲突'} description={unresolved ? '系统按来源标识和内容指纹分组检查，目前没有发现具体冲突，但仍需要数据编辑员确认本次检查结果并完成裁决。' : '系统按来源标识和内容指纹分组检查；没有冲突时无需额外裁决。'} />
          {unresolved && canResolve && <Button type="primary" onClick={onResolve}>确认无冲突并完成裁决</Button>}
          {unresolved && !canResolve && <Typography.Text type="secondary">当前账号只有查看权限，请由数据编辑员确认来源冲突检查结果。</Typography.Text>}
        </Space>
      ) : (
        <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
          <Alert
            showIcon
            type={conflicts.every((item) => item.resolved) ? 'success' : 'warning'}
            title={conflicts.every((item) => item.resolved) ? '来源冲突已完成裁决' : `检测到 ${conflicts.length} 组来源冲突`}
            description="同一来源标识下存在不同内容版本。请逐组核对来源 URL、观察时间和来源决策，再确认处理结果。"
          />
          {conflicts.map((conflict) => (
            <Card key={conflict.source_id} size="small" type="inner" title={<Space><span>来源组：{conflict.source_id}</span>{conflict.resolved ? <Tag color="success">已处理</Tag> : <Tag color="warning">待处理</Tag>}</Space>}>
              <Table
                rowKey="source_record_id"
                size="small"
                pagination={false}
                dataSource={conflict.records}
                columns={[
                  { title: '来源记录', dataIndex: 'source_record_id', ellipsis: true },
                  { title: '来源地址', dataIndex: 'source_url', ellipsis: true },
                  { title: '来源决策', dataIndex: 'source_decision', render: (value: string) => sourceDecisionLabel(value) },
                  { title: '观察时间', dataIndex: 'observed_at', render: (value: string) => formatDateTime(value) },
                  { title: '状态', dataIndex: 'status', render: (value: string) => reviewStatusLabel(value) },
                ]}
                scroll={{ x: 760 }}
              />
            </Card>
          ))}
          {!conflicts.every((item) => item.resolved) && canResolve && <Button type="primary" onClick={onResolve}>标记冲突已处理</Button>}
          {!conflicts.every((item) => item.resolved) && !canResolve && <Typography.Text type="secondary">当前账号只有查看权限，请由数据编辑员处理冲突后再继续审核。</Typography.Text>}
        </Space>
      )}
    </Card>
  )
}

function VerificationSummaryCard({ evidence, revision }: { evidence: PlaceRevisionEvidence | null; revision: PlaceRevision }) {
  if (!evidence) return null
  const groups = [
    { label: '地图与访问点（O04）', target: 'o04-evidence', items: [...evidence.geometries, ...evidence.access_points] },
    { label: '开放时间（O05）', target: 'o05-evidence', items: [...evidence.time_rules, ...evidence.closures, ...evidence.date_exceptions] },
    { label: '关系裁决（O07）', target: 'o07-evidence', items: evidence.relations ?? [] },
  ]
  return (
    <Card title="人工核验进度">
      <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
        先看这张清单，再进入具体区域处理；只有“已核验”的有效证据才会计入求解器资格。系统不会因为表格中存在记录就默认它已核验。
      </Typography.Paragraph>
      <Space wrap>
        {groups.map((group) => {
          const active = group.items.filter((item) => item.active)
          const noRelationsConfirmed = group.target === 'o07-evidence' && active.length === 0 && revision.relation_review_status === 'no_relations'
          const verified = noRelationsConfirmed ? 1 : active.filter((item) => item.review_status === 'human_verified').length
          const total = noRelationsConfirmed ? 1 : active.length
          return <Button key={group.target} size="small" onClick={() => document.getElementById(group.target)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>
            {group.label}：{verified}/{total} 已核验
          </Button>
        })}
        <Tag color={revision.solver_eligible ? 'success' : 'warning'}>{revision.solver_eligible ? '已具备求解资格' : '尚未具备求解资格'}</Tag>
      </Space>
    </Card>
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
  const openGeometry = (item?: PlaceGeometryEvidence) => {
    setEditing(item ?? null)
    form.resetFields()
    form.setFieldsValue(geometryFormValues(item, revision.geometry_kind, evidence?.sources[0]?.source_record_id))
    setModal('geometry')
  }
  const openAccess = (item?: PlaceAccessPointEvidence) => {
    setEditing(item ?? null)
    form.resetFields()
    form.setFieldsValue(item ? item : { access_point_kind: 'visitor_entrance', source_record_id: evidence?.sources[0]?.source_record_id })
    setModal('access')
  }
  const saveEvidence = async () => {
    setSaving(true)
    try {
      const values = await form.validateFields()
      const base = { expected_revision_version: revision.revision_version, operation_intent_id: `evidence-${crypto.randomUUID()}`, reason_code: editing ? 'EVIDENCE_UPDATED' : 'EVIDENCE_CREATED' }
      if (modal === 'geometry') {
        const geometryValues = values as GeometryFormValues
        const input: PlaceGeometryInput = { ...base, geometry_kind: geometryValues.geometry_kind, geometry: geometryPayload(geometryValues), source_record_id: geometryValues.source_record_id }
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
  const sourceOptions = evidence.sources.map((source) => ({
    value: source.source_record_id,
    label: `${source.source_id} · ${source.source_record_id}`,
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
                    {source.source_id} · {sourceDecisionLabel(source.source_decision)}
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
            ...((editable || reviewable) ? [{ title: '操作', key: 'actions', width: 280, render: (_: unknown, item: PlaceAccessPointEvidence) => <Space>{editable && <><Button size="small" icon={<EditOutlined />} onClick={() => openAccess(item)}>编辑</Button>{item.active && <Button size="small" danger onClick={() => void retire('access', item.access_point_id)}>停用</Button>}</>}{reviewable && item.active && <><Button size="small" type="primary" onClick={() => void review('access_point', item.access_point_id, 'human_verified')}>通过</Button><Button size="small" onClick={() => void review('access_point', item.access_point_id, 'rejected')}>驳回</Button></>}</Space> }] : []),
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
      <Modal title={modal === 'geometry' ? '新增/编辑几何证据' : '新增/编辑访问点证据'} open={modal !== null} onOk={() => void saveEvidence()} onCancel={() => setModal(null)} confirmLoading={saving} forceRender>
        <Form form={form} layout="vertical">
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
              </Space> : <Form.Item name="geometry_coordinates" label={<FieldLabel label={getFieldValue('geometry_kind') === 'area' ? '边界坐标点' : '路线坐标点'} hint={getFieldValue('geometry_kind') === 'area' ? '每行一个边界点，格式为“经度, 纬度”，至少 3 个点；系统会自动闭合边界。' : '每行一个轨迹点，格式为“经度, 纬度”，至少 2 个点；按行填写行进顺序。'} />} rules={[{ required: true, message: '请至少填写所需坐标点' }]}>
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
  const [confirmingNone, setConfirmingNone] = useState(false)
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
  const confirmNone = async () => {
    setConfirmingNone(true)
    try {
      await api.confirmNoPlaceRelations(revision.place_revision_id, {
        expected_revision_number: revision.revision_number,
        expected_revision_version: revision.revision_version,
        operation_intent_id: `relation-review-none-${crypto.randomUUID()}`,
        reason_code: 'RELATION_REVIEW_CONFIRMED_NONE',
      })
      await onChanged()
      onSuccess('已记录当前地点无需要裁决的关系，修订版本需重新送审')
    } catch (reason) { onError(adminErrorMessage(reason)) } finally { setConfirmingNone(false) }
  }
  return <Card title="地点关系与裁决（O07）">
    <InstructionHint text="关系记录由系统根据地点归一与去重线索自动发现，不在此处手工新增。存在关系时请逐条裁决；没有关系记录时，数据编辑员需要确认“已检查，无关系”，该结论会写入当前修订版本并保留审计记录。" />
    <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
      <Alert showIcon type={revision.relation_review_status === 'no_relations' || relations.length > 0 ? 'success' : 'warning'} title={`关系检查：${relationReviewStatusLabel(revision.relation_review_status)}`} description={relations.length > 0 ? '系统已发现关系记录，请确认每条记录的关系类型和裁决状态。' : revision.relation_review_status === 'no_relations' ? '本次修订已记录当前地点没有需要裁决的关系。' : canEdit ? '当前没有关系记录。请确认本次检查完成，系统会保留操作人和时间。' : '当前账号只有查看权限，请由数据编辑员确认“无关系”。'} />
      {relations.length === 0 && canEdit && (revision.relation_review_status ?? 'pending') !== 'no_relations' && <Button type="primary" onClick={() => void confirmNone()} loading={confirmingNone}>确认无关系</Button>}
    <Table<PlaceRelationEvidence> rowKey="relation_id" dataSource={relations} pagination={false} locale={{ emptyText: '当前地点暂无关系证据' }} columns={[
      { title: '关系类型', dataIndex: 'relation_type', render: relationTypeLabel },
      { title: '目标地点', render: (_: unknown, item: PlaceRelationEvidence) => `${item.from_place_id} → ${item.to_place_id}` },
      { title: '审核', dataIndex: 'review_status', render: reviewStatusLabel },
      { title: '裁决', dataIndex: 'resolution_status', render: relationResolutionLabel },
      { title: '来源', dataIndex: 'source_record_id' },
      ...(canEdit ? [{ title: '操作', key: 'actions', width: 110, render: (_: unknown, item: PlaceRelationEvidence) => <Button size="small" onClick={() => { setEditing(item); setStatus(item.resolution_status); setNote(item.decision_note ?? '') }}>裁决</Button> }] : []),
    ]} />
    <Modal title="关系裁决" open={editing !== null} onOk={() => void save()} onCancel={() => setEditing(null)} confirmLoading={working}>
      <Space orientation="vertical" style={{ width: '100%' }}>
        <Select value={status} onChange={setStatus} options={[{ value: 'resolved', label: '已裁决' }, { value: 'not_required', label: '无需裁决' }, { value: 'pending', label: '待处理' }]} />
        <Input.TextArea value={note} onChange={(event) => setNote(event.target.value)} placeholder="裁决说明（已裁决时必填）" rows={4} />
      </Space>
    </Modal>
    </Space>
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
        {revision.place_kind === 'show' && (
          <Alert
            showIcon
            type="warning"
            title="演出地点必须使用固定场次规则"
            description="开放时间只能说明可营业时段；演出、灯光秀等地点还需要明确的开始时间和结束时间，并将规则类型设置为“固定场次”。"
          />
        )}
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
            <SourceRecordField sources={evidence.sources} />
          </>}
          {modal === 'closure' && <>
            <Form.Item name="weekday" label="闭馆星期" rules={[{ required: true }]}><Select options={weekdayOptions()} /></Form.Item>
            <SourceRecordField sources={evidence.sources} />
          </>}
          {modal === 'date_exception' && <>
            <Form.Item name="service_date" label="例外日期" rules={[{ required: true }]}><Input placeholder="YYYY-MM-DD" /></Form.Item>
            <Form.Item name="exception_kind" label="例外类型" rules={[{ required: true }]}><Select options={[{ value: 'closed', label: '临时关闭' }, { value: 'open_override', label: '开放覆盖' }, { value: 'session_override', label: '场次覆盖' }]} /></Form.Item>
            <MinuteFields />
            <SourceRecordField sources={evidence.sources} />
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
    <Form.Item name="start_minute" label={<FieldLabel label="开始时间（分钟）" hint="当天 09:30 填 570；跨午夜次日 00:30 填 1470。范围 0–2880。" />}><InputNumber min={0} max={2880} style={{ width: '100%' }} /></Form.Item>
    <Form.Item name="end_minute" label={<FieldLabel label="结束时间（分钟）" hint="与开始时间相同的分钟表示；结束值必须晚于开始值。" />}><InputNumber min={0} max={2880} style={{ width: '100%' }} /></Form.Item>
    <Form.Item name="last_entry_minute" label={<FieldLabel label="最晚入园时间（分钟）" hint="游客最晚允许进入的时间；没有限制时可留空。" />}><InputNumber min={0} max={2880} style={{ width: '100%' }} /></Form.Item>
  </>
}

function SourceRecordField({ sources = [] }: { sources?: PlaceRevisionEvidence['sources'] }) {
  return <Form.Item name="source_record_id" label={<FieldLabel label="来源记录" hint="只能选择当前地点的有效来源记录；来源 URL、观察时间和采集方式请在来源证据区域核对。" />} rules={[{ required: true }]}>
    <Select showSearch optionFilterProp="label" options={sources.map((source) => ({ value: source.source_record_id, label: `${source.source_id} · ${source.source_record_id}` }))} placeholder="选择当前地点的有效来源" />
  </Form.Item>
}

function FieldLabel({ label, hint }: { label: string; hint: string }) {
  return <span>{label} <Tooltip title={hint}><ExclamationCircleFilled style={{ color: '#d89614', cursor: 'help' }} aria-label={`${label}填写提示`} /></Tooltip></span>
}

function InstructionHint({ text }: { text: string }) {
  return <Tooltip title={text}><ExclamationCircleFilled style={{ color: '#d89614', fontSize: 17, cursor: 'help' }} aria-label="填写提示" /></Tooltip>
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

type PublicationBlocker = {
  code: string
  title: string
  description: string
  actionLabel?: string
  target?: 'review-actions' | 'o04-evidence' | 'o05-evidence' | 'o06-source-conflicts' | 'o07-evidence'
}

function buildPublicationBlockers(
  revision: PlaceRevision,
  evidence: PlaceRevisionEvidence | null,
  sourceConflicts: SourceConflict[],
  publicationCheck: PublicationCheck | null,
): PublicationBlocker[] {
  const codes: string[] = []
  if (revision.lifecycle_status === 'candidate') codes.push('REVISION_NOT_HUMAN_VERIFIED')
  if (revision.source_record_ids.length === 0) codes.push('MISSING_SOURCE_RECORD')
  if (!revision.conflicts_resolved || sourceConflicts.some((item) => !item.resolved)) codes.push('SOURCE_CONFLICT_UNRESOLVED')

  const validSourceIds = new Set((evidence?.sources ?? []).filter((item) => item.status === 'active').map((item) => item.source_record_id))
  if (evidence) {
    const verifiedGeometry = evidence.geometries.some((item) => item.active && item.review_status === 'human_verified' && item.geometry_kind === revision.geometry_kind && validSourceIds.has(item.source_record_id))
    const verifiedAccessPoint = evidence.access_points.some((item) => item.active && item.review_status === 'human_verified' && validSourceIds.has(item.source_record_id))
    const verifiedTimeRules = evidence.time_rules.filter((item) => item.active && item.review_status === 'human_verified' && validSourceIds.has(item.source_record_id))
    const verifiedTimeRule = revision.is_always_open || verifiedTimeRules.length > 0
    if (!verifiedGeometry) codes.push('MISSING_VERIFIED_GEOMETRY')
    if (!verifiedAccessPoint) codes.push('MISSING_VERIFIED_ACCESS_POINT')
    if (!verifiedTimeRule) codes.push('TIME_RULE_UNRESOLVED')
    if (revision.place_kind === 'show' && verifiedTimeRules.filter((item) => item.rule_kind === 'fixed_session').length === 0) codes.push('FIXED_SESSION_REQUIRED')
    if (evidence.relations?.some((item) => item.active && ['overlaps', 'same_experience'].includes(item.relation_type) && item.resolution_status === 'pending')) codes.push('OVERLAPPING_SELECTION_UNRESOLVED')
    if ((evidence.relations ?? []).filter((item) => item.active).length === 0 && revision.relation_review_status === 'pending') codes.push('RELATION_REVIEW_REQUIRED')
  }
  if (!revision.solver_eligible) codes.push('PLACE_NOT_SOLVER_ELIGIBLE')
  if (publicationCheck && !publicationCheck.publishable) codes.push(...publicationCheck.reason_codes)

  const uniqueCodes = [...new Set(codes)]
  return uniqueCodes.map((code): PublicationBlocker => {
    if (code === 'REVISION_NOT_HUMAN_VERIFIED') return {
      code, title: '尚未完成人工核验',
      description: '当前仍是候选修订版本。数据编辑员先补齐证据并送审，审核员逐项核验后点击“审核通过”。',
      actionLabel: '查看审核操作', target: 'review-actions',
    }
    if (code === 'MISSING_SOURCE_RECORD' || code === 'SOURCE_RECORD_INVALID' || code === 'SOURCE_RECORD_PLACE_MISMATCH') return {
      code, title: reasonCodeLabel(code),
      description: '求解器只接受当前地点仍生效的来源记录。请在 O04/O05 证据中选择有效来源，并核对来源地址、观察时间和状态。',
      actionLabel: '查看证据与来源', target: 'o04-evidence',
    }
    if (code === 'SOURCE_CONFLICT_UNRESOLVED') return {
      code, title: '存在未完成裁决的来源冲突',
      description: sourceConflicts.some((item) => !item.resolved)
        ? `检测到 ${sourceConflicts.filter((item) => !item.resolved).length} 组来源内容不一致。请打开 O06 查看每条来源记录，核对后由数据编辑员标记处理完成。`
        : '当前修订版本尚未完成来源冲突状态确认。请打开 O06 刷新并核对来源记录；如确认没有冲突，由数据编辑员标记处理完成。',
      actionLabel: '查看来源冲突（O06）', target: 'o06-source-conflicts',
    }
    if (code === 'MISSING_VERIFIED_GEOMETRY' || code === 'MISSING_VERIFIED_ACCESS_POINT' || code === 'MISSING_ARRIVAL_ACCESS_POINT' || code === 'MISSING_DEPARTURE_ACCESS_POINT' || code === 'ACCESS_POINT_NOT_HUMAN_VERIFIED' || code === 'ACCESS_POINT_REVISION_MISMATCH') return {
      code, title: reasonCodeLabel(code),
      description: code.includes('ACCESS') || code.includes('ARRIVAL') || code.includes('DEPARTURE')
        ? '至少需要一个当前修订版本下、来源有效且已人工核验的访问点，供系统确定游客到达和离开端点。'
        : '需要一条与地点几何类型一致、来源有效且已人工核验的几何记录。',
      actionLabel: '查看地图与访问点（O04）', target: 'o04-evidence',
    }
    if (code === 'FIXED_SESSION_REQUIRED') return {
      code, title: reasonCodeLabel(code),
      description: '该地点类型是演出/固定场次。无论当前是否已有普通开放时间，求解器都需要一条明确开始和结束时间的“固定场次”规则；请在 O05 新增或编辑规则，并重新送审。',
      actionLabel: '处理固定场次（O05）', target: 'o05-evidence',
    }
    if (code === 'TIME_RULE_UNRESOLVED' || code === 'MISSING_VERIFIED_TIME_RULE' || code === 'FIXED_SESSION_AMBIGUOUS') return {
      code, title: reasonCodeLabel(code),
      description: revision.is_always_open
        ? '当前标记为全天开放；请在 O05 核对该事实是否有来源支持。'
        : `当前读取到 ${evidence?.time_rules.filter((item) => item.active).length ?? 0} 条有效开放时间规则，其中 ${evidence?.time_rules.filter((item) => item.active && item.review_status === 'human_verified').length ?? 0} 条已人工核验。需要至少一条当前有效来源支持、并已人工核验的规则；固定场次地点还必须只有一条明确场次。`,
      actionLabel: '查看开放时间（O05）', target: 'o05-evidence',
    }
    if (code === 'OVERLAPPING_SELECTION_UNRESOLVED') return {
      code, title: reasonCodeLabel(code),
      description: '存在“重叠”或“同一体验”关系尚未裁决。请在 O07 选择已裁决或无需裁决，并填写裁决说明。',
      actionLabel: '查看关系裁决（O07）', target: 'o07-evidence',
    }
    if (code === 'RELATION_REVIEW_REQUIRED') return {
      code, title: reasonCodeLabel(code),
      description: '当前没有系统发现的关系记录，但 O07 尚未登记检查结论。请进入 O07，由数据编辑员确认“无关系”；如发现关系，应补录后逐条裁决。',
      actionLabel: '处理关系检查（O07）', target: 'o07-evidence',
    }
    if (code === 'PLACE_NOT_SOLVER_ELIGIBLE' || code === 'REVISION_NOT_HUMAN_VERIFIED') return {
      code, title: '当前修订版本尚不满足求解器使用条件',
      description: '求解资格不是手工勾选项，而是证据核验、冲突裁决和修订审核通过后的结果。请按上方具体阻断项处理，完成后重新送审或重新准备求解投影。',
    }
    return {
      code, title: reasonCodeLabel(code),
      description: '该项由发布门禁检查发现，请按对应证据区域核对并刷新页面。',
    }
  })
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
