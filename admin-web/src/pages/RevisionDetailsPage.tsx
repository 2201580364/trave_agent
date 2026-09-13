import { GeometryAccessEvidenceCard } from './GeometryAccessEvidenceCard'
import { InstructionHint } from './revisionDetailFields'
import { reviewStatusColor, formatOptionalDateTime } from './revisionDetailDisplay'
import { SourceEvidenceCard } from './SourceEvidenceCard'
import { FieldLabel, SourceRecordField, TimeField } from './revisionDetailFields'
import { isFormValidationError } from './revisionDetailDisplay'
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
import { Alert, App as AntApp, Button, Card, Checkbox, Collapse, Descriptions, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Switch, Table, Tag, Tooltip, Typography } from 'antd'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'

import { adminErrorMessage } from '../api/errorMessages'
import type { PlaceAccessPointEvidence, PlaceAccessPointInput, PlaceClosureEvidence, PlaceClosureInput, PlaceDateExceptionEvidence, PlaceDateExceptionInput, PlaceEvidenceSource, PlaceGeometryEvidence, PlaceGeometryInput, PlaceRevision, PlaceRevisionEvidence, PlaceTimeRuleEvidence, PlaceTimeRuleInput, PlaceTimePreview, PlaceRelationEvidence, ReviewTask, PublicationCheck, SourceChannel, SourceConflict, HolidayCalendar } from '../api/types'
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

import type { GeometryFormValues } from './revisionDetailHelpers'
import { geometryFormValues, geometryPayload, geometrySummary, parseCoordinateLines } from './revisionDetailHelpers'
export type { GeometryFormValues } from './revisionDetailHelpers'
export { geometryFormValues, geometryPayload, geometrySummary, parseCoordinateLines } from './revisionDetailHelpers'

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
  const [sourceChannels, setSourceChannels] = useState<SourceChannel[]>([])
  const [holidayCalendars, setHolidayCalendars] = useState<HolidayCalendar[]>([])
  const [holidayCalendarsLoading, setHolidayCalendarsLoading] = useState(false)
  const [holidayCalendarsError, setHolidayCalendarsError] = useState<string | null>(null)
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

    const sourceChannelsRequest = typeof api.listSourceChannels === 'function'
      ? api.listSourceChannels()
        .then((result) => setSourceChannels(result.items))
        .catch(() => setSourceChannels([]))
      : Promise.resolve()
    setHolidayCalendarsLoading(true)
    setHolidayCalendarsError(null)
    const holidayCalendarsRequest = typeof api.listHolidayCalendars === 'function'
      ? api.listHolidayCalendars()
        .then((result) => setHolidayCalendars(result.items))
        .catch((reason: unknown) => { setHolidayCalendars([]); setHolidayCalendarsError(adminErrorMessage(reason)) })
        .finally(() => setHolidayCalendarsLoading(false))
      : Promise.resolve().then(() => setHolidayCalendarsLoading(false))

    await Promise.all([revisionRequest, evidenceRequest, reviewTaskRequest, sourceConflictRequest, publicationCheckRequest, sourceChannelsRequest, holidayCalendarsRequest])
  }, [api, canCheckPublication, revisionId, reviewContext, reviewTaskId])

  useEffect(() => {
    void load()
  }, [load])

  const blockers = useMemo(
    () => revision ? buildPublicationBlockers(revision, evidence, sourceConflicts, publicationCheck) : [],
    [revision, evidence, sourceConflicts, publicationCheck],
  )
  const hasSourceConflicts = sourceConflicts.length > 0
  const hasUnresolvedSourceConflicts = sourceConflicts.some((item) => !item.resolved)
  const verificationProgress = useMemo(() => {
    if (!evidence) return { verified: 0, total: 0 }
    const items = [
      ...evidence.geometries,
      ...evidence.access_points,
      ...evidence.time_rules,
      ...evidence.closures,
      ...evidence.date_exceptions,
      ...(evidence.relations ?? []),
    ].filter((item) => item.active)
    const relationConfirmation = (evidence.relations ?? []).length === 0 && revision?.relation_review_status === 'no_relations' ? 1 : 0
    return {
      verified: items.filter((item) => item.review_status === 'human_verified').length + relationConfirmation,
      total: items.length + relationConfirmation,
    }
  }, [evidence, revision?.relation_review_status])
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
          <Card className="revision-overview-card">
            <div className="revision-overview-heading">
              <div>
                <Space wrap size={8}>
                  <Typography.Title level={3} style={{ margin: 0 }}>{revision.canonical_name}</Typography.Title>
                  <Tag color={revision.lifecycle_status === 'human_verified' ? 'success' : 'processing'}>{lifecycleStatusLabel(revision.lifecycle_status)}</Tag>
                  <Tag>第 {revision.revision_number} 版</Tag>
                </Space>
                <Typography.Paragraph type="secondary" style={{ margin: '8px 0 0' }}>
                  {revision.admin_area} · {placeKindLabel(revision.place_kind)} · {revision.category}
                  {revision.address ? ` · ${revision.address}` : ''}
                </Typography.Paragraph>
              </div>
              <div className="revision-status-grid">
                <div className="revision-status-tile"><span>证据核验</span><strong>{verificationProgress.verified}/{verificationProgress.total}</strong></div>
                <div className={`revision-status-tile ${hasUnresolvedSourceConflicts ? 'is-warning' : 'is-success'}`}><span>来源冲突</span><strong>{hasUnresolvedSourceConflicts ? '待裁决' : hasSourceConflicts ? '已裁决' : '未发现'}</strong></div>
                <div className={`revision-status-tile ${revision.solver_eligible ? 'is-success' : 'is-warning'}`}><span>求解资格</span><strong>{revision.solver_eligible ? '已具备' : '未具备'}</strong></div>
                <div className={`revision-status-tile ${blockers.length === 0 ? 'is-success' : 'is-warning'}`}><span>发布待办</span><strong>{blockers.length} 项</strong></div>
              </div>
            </div>
          </Card>

          <Card title="地点资料" className="revision-profile-card">
            <div id="revision-basic-facts" />
            <Descriptions size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
              <Descriptions.Item label="别名">{revision.aliases.join('、') || '未提供'}</Descriptions.Item>
              <Descriptions.Item label="地址">{revision.address ?? '未提供'}</Descriptions.Item>
              <Descriptions.Item label="地图表达">{geometryKindLabel(revision.geometry_kind)}</Descriptions.Item>
              <Descriptions.Item label="建议游览时长">
                {revision.review_flags.includes('DURATION_NOT_COLLECTED') ? '未采集' : `${revision.duration_min}–${revision.duration_max} 分钟，建议 ${revision.duration_recommended} 分钟`}
              </Descriptions.Item>
              <Descriptions.Item label="室内/室外">{indoorOutdoorLabel(revision.indoor_outdoor)}</Descriptions.Item>
              <Descriptions.Item label="全天开放">{revision.is_always_open ? '是' : '否'}</Descriptions.Item>
            </Descriptions>
            <Collapse
              ghost
              className="revision-technical-collapse"
              items={[{
                key: 'more',
                label: '查看更多体验与技术信息',
                children: <Descriptions size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
                  <Descriptions.Item label="内部移动">{revision.internal_travel_min} 分钟</Descriptions.Item>
                  <Descriptions.Item label="体力等级">{revision.energy_level} / 5</Descriptions.Item>
                  <Descriptions.Item label="适用时段">{revision.suitable_periods.map((value) => ({ morning: '上午', afternoon: '下午', evening: '晚上' }[value] ?? '其他')).join('、') || '未提供'}</Descriptions.Item>
                  <Descriptions.Item label="适合人群">{revision.audience_tags.join('、') || '未提供'}</Descriptions.Item>
                  <Descriptions.Item label="雨天适配">{rainSuitabilityLabel(revision.rain_suitability)}</Descriptions.Item>
                  <Descriptions.Item label="来源记录">{revision.source_record_ids.length} 条</Descriptions.Item>
                  <Descriptions.Item label="创建时间">{formatDateTime(revision.created_at)}</Descriptions.Item>
                  <Descriptions.Item label="人工核验时间">{formatOptionalDateTime(revision.reviewed_at)}</Descriptions.Item>
                  <Descriptions.Item label="发布时间">{formatOptionalDateTime(revision.published_at)}</Descriptions.Item>
                  <Descriptions.Item label="修订版本编号">{revision.place_revision_id}</Descriptions.Item>
                  <Descriptions.Item label="地点编号">{revision.place_id}</Descriptions.Item>
                  <Descriptions.Item label="待核验提示">{revision.review_flags.length ? revision.review_flags.map(reviewFlagLabel).join('、') : '无'}</Descriptions.Item>
                </Descriptions>,
              }]}
            />
          </Card>

          <VerificationSummaryCard evidence={evidence} revision={revision} />

          <div id="source-evidence"><SourceEvidenceCard
            api={api}
            evidence={evidence}
            revision={revision}
            sourceChannels={sourceChannels}
            canEdit={!reviewContext && hasPermission('place:candidate:write')}
            onChanged={load}
            onSuccess={(text) => messageApi.success(text)}
            onError={setError}
          /></div>

          <div id="o04-evidence"><GeometryAccessEvidenceCard
            api={api}
            evidence={evidence}
            loading={evidenceLoading}
            error={evidenceError}
            revision={revision}
            sourceChannels={sourceChannels}
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
            sourceChannels={sourceChannels}
            holidayCalendars={holidayCalendars}
            holidayCalendarsLoading={holidayCalendarsLoading}
            holidayCalendarsError={holidayCalendarsError}
            onReloadHolidayCalendars={load}
            canEdit={hasPermission('place:candidate:write')}
            canReview={canReviewThisRevision}
            onSuccess={(text) => messageApi.success(text)}
            onChanged={load}
            onError={setError}
          /></div>
          <div id="o07-evidence"><RelationEvidenceCard api={api} evidence={evidence} revision={revision} sourceChannels={sourceChannels} canEdit={hasPermission('place:candidate:write')} canReview={canReviewThisRevision} onChanged={load} onSuccess={(text) => messageApi.success(text)} onError={setError} /></div>
          <div id="o06-source-conflicts"><SourceConflictCard
            conflicts={sourceConflicts}
            loading={loading}
            error={sourceConflictError}
            canResolve={revision.lifecycle_status === 'candidate' && hasPermission('place:candidate:write')}
            onResolve={() => { setResolveConflictNote(''); setResolveConflictOpen(true) }}
          /></div>

          <Card title="发布准备" className="publication-readiness-card">
            {blockers.length === 0 ? (
              <Alert showIcon type="success" icon={<CheckCircleOutlined />} title={publicationCheck?.publishable === false ? '当前仍有发布门禁原因，请查看下方明细' : '当前修订版本没有识别出的阻断项'} />
            ) : (
              <Space orientation="vertical" style={{ width: '100%' }}>
                <Alert showIcon type="warning" title={`当前有 ${blockers.length} 项需要处理`} />
                {blockers.slice(0, 3).map((blocker) => (
                  <div key={blocker.code} className="publication-blocker-item">
                    <Space orientation="vertical" size={4} style={{ width: '100%' }}>
                      <Typography.Text strong><CloseCircleOutlined style={{ color: '#cf1322' }} /> {blocker.title}</Typography.Text>
                      <Typography.Text type="secondary">{blocker.description}</Typography.Text>
                      {blocker.actionLabel && blocker.target && <Button size="small" type="link" onClick={() => document.getElementById(blocker.target!)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>{blocker.actionLabel}</Button>}
                    </Space>
                  </div>
                ))}
                {blockers.length > 3 && <Collapse ghost items={[{
                  key: 'remaining-blockers',
                  label: `展开其余 ${blockers.length - 3} 项`,
                  children: <Space orientation="vertical" style={{ width: '100%' }}>{blockers.slice(3).map((blocker) => (
                    <div key={blocker.code} className="publication-blocker-item">
                      <Space orientation="vertical" size={4} style={{ width: '100%' }}>
                        <Typography.Text strong><CloseCircleOutlined style={{ color: '#cf1322' }} /> {blocker.title}</Typography.Text>
                        <Typography.Text type="secondary">{blocker.description}</Typography.Text>
                        {blocker.actionLabel && blocker.target && <Button size="small" type="link" onClick={() => document.getElementById(blocker.target!)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>{blocker.actionLabel}</Button>}
                      </Space>
                    </div>
                  ))}</Space>,
                }]} />}
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
              <Form.Item name="is_always_open" label={<FieldLabel label="全天开放" hint="开放式景点或公共空间全年全天可访问时勾选。勾选后无需填写周一至周日 00:00–23:59；如有固定闭馆日或临时调整，仍需单独维护对应规则。" />} valuePropName="checked"><Switch /></Form.Item>
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
  canResolve,
  onResolve,
}: {
  conflicts: SourceConflict[]
  loading: boolean
  error: string | null
  canResolve: boolean
  onResolve: () => void
}) {
  return (
    <Card title="来源冲突与裁决（O06）">
      {loading ? <Card loading size="small" /> : error ? (
        <Alert showIcon type="warning" title="来源冲突暂不可用" description={error} />
      ) : conflicts.length === 0 ? (
        <Alert showIcon type="success" title="当前没有检测到来源内容冲突" description="系统已检查同一来源标识下的内容版本，无需额外确认。不同来源之间的地址、坐标和开放时间差异，仍在 O04/O05 的具体证据中核验。" />
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
          // O07 has two independent states: the editor's relation decision and
          // the reviewer's evidence verification. This summary is the former,
          // so an agreed/rejected relation is already a completed decision even
          // while its reviewer status remains pending in the table below.
          const verified = noRelationsConfirmed
            ? 1
            : group.target === 'o07-evidence'
              ? active.filter((item) => 'resolution_status' in item && item.resolution_status !== 'pending').length
              : active.filter((item) => item.review_status === 'human_verified').length
          const total = noRelationsConfirmed ? 1 : active.length
          return <Button key={group.target} size="small" onClick={() => document.getElementById(group.target)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>
            {group.label}：{verified}/{total} {group.target === 'o07-evidence' ? '已裁决' : '已核验'}
          </Button>
        })}
        <Tag color={revision.solver_eligible ? 'success' : 'warning'}>{revision.solver_eligible ? '已具备求解资格' : '尚未具备求解资格'}</Tag>
      </Space>
    </Card>
  )
}

function RelationEvidenceCard({ api, evidence, revision, sourceChannels, canEdit, canReview, onChanged, onSuccess, onError }: {
  api: ReturnType<typeof useAdminSession>['api']
  evidence: PlaceRevisionEvidence | null
  revision: PlaceRevision
  sourceChannels: SourceChannel[]
  canEdit: boolean
  canReview: boolean
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
  const reviewEvidence = async (item: PlaceRelationEvidence, reviewStatus: 'human_verified' | 'rejected') => {
    setWorking(true)
    try {
      await api.reviewEvidence(revision.place_revision_id, 'relation', item.relation_id, {
        review_status: reviewStatus,
        operation_intent_id: `relation-evidence-review-${crypto.randomUUID()}`,
        reason_code: reviewStatus === 'human_verified' ? 'EVIDENCE_APPROVED' : 'EVIDENCE_REJECTED',
      })
      await onChanged()
      onSuccess(reviewStatus === 'human_verified' ? '关系证据已通过审核' : '关系证据已驳回')
    } catch (reason) { onError(adminErrorMessage(reason)) } finally { setWorking(false) }
  }
  const save = async () => {
    if (!editing) return
    if (!note.trim()) {
      onError('请填写判断依据后再保存关系裁决')
      return
    }
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
    <InstructionHint text="关系记录由系统根据地点归一与去重线索自动发现，不在此处手工新增。请逐条判断关系是否成立：同意会保留该地点关系，驳回会将其标记为误识别并从有效关系中排除；暂时无法判断时选择待处理。没有关系记录时，数据编辑员需要确认“已检查，无关系”。" />
    <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
      <Alert showIcon type={revision.relation_review_status === 'no_relations' || relations.length > 0 ? 'success' : 'warning'} title={`关系检查：${relationReviewStatusLabel(revision.relation_review_status)}`} description={relations.length > 0 ? '系统已发现关系记录，请确认每条记录的关系类型和裁决状态。' : revision.relation_review_status === 'no_relations' ? '本次修订已记录当前地点没有需要裁决的关系。' : canEdit ? '当前没有关系记录。请确认本次检查完成，系统会保留操作人和时间。' : '当前账号只有查看权限，请由数据编辑员确认“无关系”。'} />
      {relations.length === 0 && canEdit && (revision.relation_review_status ?? 'pending') !== 'no_relations' && <Button type="primary" onClick={() => void confirmNone()} loading={confirmingNone}>确认无关系</Button>}
    <Table<PlaceRelationEvidence> rowKey="relation_id" dataSource={relations} pagination={false} locale={{ emptyText: '当前地点暂无关系证据' }} columns={[
      { title: '关系类型', dataIndex: 'relation_type', render: (value: string) => <Space size={6}><Tag color="blue">{relationTypeLabel(value)}</Tag><span className="relation-meaning">{relationMeaning(value)}</span></Space> },
      { title: '关系地点', render: (_: unknown, item: PlaceRelationEvidence) => {
        const fromName = item.from_place_name ?? '待补充地点名称'
        const toName = item.to_place_name ?? '待补充地点名称'
        return <Tooltip title={`内部端点：${item.from_place_id} → ${item.to_place_id}`}><span className="relation-endpoints"><strong>{fromName}</strong><span className="relation-arrow">→</span><strong>{toName}</strong></span></Tooltip>
      } },
      { title: '关系说明', render: (_: unknown, item: PlaceRelationEvidence) => <span>{relationExplanation(item)}</span> },
      { title: '审核', dataIndex: 'review_status', render: (_value: string, item: PlaceRelationEvidence) => <Space size={6}><span>{reviewStatusLabel(item.review_status)}</span>{canReview && <><Button size="small" type={item.review_status === 'human_verified' ? 'primary' : 'default'} disabled={working || item.review_status === 'human_verified'} onClick={() => void reviewEvidence(item, 'human_verified')}>通过</Button><Button size="small" danger disabled={working || item.review_status === 'rejected'} onClick={() => void reviewEvidence(item, 'rejected')}>驳回</Button></>}</Space> },
      { title: '裁决', dataIndex: 'resolution_status', render: relationResolutionLabel },
      { title: '识别依据', render: (_: unknown, item: PlaceRelationEvidence) => <span>{sourceLabelById(evidence, item.source_record_id, sourceChannels)}<br /><Typography.Text type="secondary">系统关系线索</Typography.Text></span> },
      ...(canEdit ? [{ title: '操作', key: 'actions', width: 110, render: (_: unknown, item: PlaceRelationEvidence) => <Button size="small" onClick={() => { setEditing(item); setStatus(item.resolution_status); setNote(item.decision_note ?? '') }}>裁决</Button> }] : []),
    ]} />
    <Modal title="关系裁决" open={editing !== null} onOk={() => void save()} onCancel={() => setEditing(null)} confirmLoading={working}>
      <Space orientation="vertical" style={{ width: '100%' }}>
        <Alert type="info" showIcon message="请选择关系判断结果" description="同意此地点关系：关系成立并保留；驳回此地点关系：关系不成立并排除；待处理：暂不作决定。" />
        <Select value={status} onChange={setStatus} options={[{ value: 'resolved', label: '同意此地点关系' }, { value: 'not_required', label: '驳回此地点关系' }, { value: 'pending', label: '待处理' }]} />
        <Input.TextArea value={note} onChange={(event) => setNote(event.target.value)} placeholder="请填写判断依据（同意或驳回均必填）" rows={4} status={editing && !note.trim() ? 'error' : undefined} />
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
  sourceChannels,
  holidayCalendars,
  holidayCalendarsLoading,
  holidayCalendarsError,
  onReloadHolidayCalendars,
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
  holidayCalendars: HolidayCalendar[]
  holidayCalendarsLoading: boolean
  holidayCalendarsError: string | null
  onReloadHolidayCalendars: () => Promise<void>
  canEdit: boolean
  canReview: boolean
  onSuccess: (text: string) => void
  onChanged: () => Promise<void>
  onError: (message: string) => void
}) {
  const reviewContext = new URLSearchParams(useLocation().search).get('from') === 'review'
  const editable = revision.lifecycle_status === 'candidate' && canEdit
  const reviewable = revision.lifecycle_status === 'candidate' && canReview
  const [modal, setModal] = useState<'time_rule' | 'closure' | 'date_exception' | 'holiday' | null>(null)
  const [editing, setEditing] = useState<PlaceTimeRuleEvidence | PlaceClosureEvidence | PlaceDateExceptionEvidence | null>(null)
  const [saving, setSaving] = useState(false)
  const [previewDate, setPreviewDate] = useState('')
  const [preview, setPreview] = useState<PlaceTimePreview | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [form] = Form.useForm()
  const exceptionKind = Form.useWatch('exception_kind', form)
  const selectedHolidayCalendarId = Form.useWatch('calendar_id', form)
  const selectedHolidayCalendar = holidayCalendars.find((calendar) => calendar.calendar_id === selectedHolidayCalendarId)

  const generateHoliday = async () => {
    try {
      const values = await form.validateFields()
      const minutes = timeFormMinutes(values)
      if (minutes.start_minute === null || minutes.end_minute === null) throw new Error('请填写节假日开放时间')
      setSaving(true)
      await api.generateHolidayExceptions(revision.place_revision_id, {
        expected_revision_version: revision.revision_version,
        calendar_id: values.calendar_id,
        source_record_id: values.source_record_id || selectedHolidayCalendar?.source_record_id || '',
        open_start_minute: minutes.start_minute,
        open_end_minute: minutes.end_minute,
        open_last_entry_minute: minutes.last_entry_minute,
        shift_closure: values.shift_closure !== false,
        operation_intent_id: `holiday-exceptions-${crypto.randomUUID()}`,
        reason_code: 'HOLIDAY_POLICY_MATERIALIZED',
      })
      setModal(null); await onChanged(); onSuccess('已按节假日历生成日期例外，请逐项核验后再送审')
    } catch (reason) {
      if (reason instanceof Error && !isFormValidationError(reason)) onError(reason.message)
      else if (!isFormValidationError(reason)) onError(adminErrorMessage(reason))
    } finally { setSaving(false) }
  }

  const openEditor = (
    kind: 'time_rule' | 'closure' | 'date_exception',
    item?: PlaceTimeRuleEvidence | PlaceClosureEvidence | PlaceDateExceptionEvidence,
  ) => {
    setEditing(item ?? null)
    form.resetFields()
    if (kind === 'time_rule') {
      const rule = item as PlaceTimeRuleEvidence | undefined
      form.setFieldsValue(rule ? timeRuleFormValues(rule) : { rule_kind: 'opening_hours', weekdays: [1, 2, 3, 4, 5] })
    } else if (kind === 'closure') {
      const closure = item as PlaceClosureEvidence | undefined
      form.setFieldsValue(closure ?? { weekday: 1 })
    } else {
      const exception = item as PlaceDateExceptionEvidence | undefined
      form.setFieldsValue(exception ? dateExceptionFormValues(exception) : { exception_kind: 'closed' })
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
        const minutes = timeFormMinutes(values)
        const input: PlaceTimeRuleInput = {
          ...base,
          rule_kind: values.rule_kind,
          weekdays: values.weekdays,
          start_minute: minutes.start_minute,
          end_minute: minutes.end_minute,
          last_entry_minute: minutes.last_entry_minute,
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
        const minutes = values.exception_kind === 'closed'
          ? { start_minute: null, end_minute: null, last_entry_minute: null }
          : timeFormMinutes(values)
        if (values.exception_kind !== 'closed' && (minutes.start_minute === null || minutes.end_minute === null)) {
          throw new Error('开放覆盖或场次覆盖必须填写开始时间和结束时间')
        }
        const input: PlaceDateExceptionInput = {
          ...base,
          service_date: values.service_date,
          exception_kind: values.exception_kind,
          start_minute: minutes.start_minute,
          end_minute: minutes.end_minute,
          last_entry_minute: minutes.last_entry_minute,
          source_record_id: values.source_record_id,
        }
        if (editing) await api.updateDateException(revision.place_revision_id, (editing as PlaceDateExceptionEvidence).date_exception_id, input)
        else await api.createDateException(revision.place_revision_id, input)
      }
      setModal(null)
      await onChanged()
      onSuccess('时间证据已保存，修订版本需重新送审')
    } catch (reason) {
      if (reason instanceof Error && reason.message.includes('时间')) onError(reason.message)
      else if (!isFormValidationError(reason)) onError(adminErrorMessage(reason))
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
  const deleteRule = async (id: string) => {
    setSaving(true)
    try {
      await api.deleteTimeRule(revision.place_revision_id, id, {
        expected_revision_version: revision.revision_version,
        operation_intent_id: `time-rule-delete-${crypto.randomUUID()}`,
        reason_code: 'TIME_RULE_DELETED',
      })
      await onChanged()
      onSuccess('开放规则已删除，修订版本需重新送审')
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
    <Card
      title={<Space size={8}>开放时间与固定场次（O05）<Tooltip title="时间证据随当前修订版本保存；修改后需要重新送审和核验。"><ExclamationCircleFilled className="section-help-icon" /></Tooltip></Space>}
      className="time-evidence-card"
    >
      <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
        {holidayCalendarsError && <Alert showIcon type="warning" title="节假日历加载失败" description={<Space orientation="vertical"><Typography.Text>{holidayCalendarsError}</Typography.Text><Button size="small" onClick={() => void onReloadHolidayCalendars()}>重新加载节假日历</Button></Space>} />}
        {revision.place_kind === 'show' && (
          <Alert
            showIcon
            type="warning"
            title="演出地点必须使用固定场次规则"
            description="开放时间只能说明可营业时段；演出、灯光秀等地点还需要明确的开始时间和结束时间，并将规则类型设置为“固定场次”。"
          />
        )}
        <div className="time-preview-toolbar">
          <div>
            <Typography.Text strong>指定日期结果预览</Typography.Text>
            <Typography.Text type="secondary"> 按已核验规则查看某一天最终是开放、闭馆还是固定场次。</Typography.Text>
          </div>
          <Space wrap>
            <Input type="date" value={previewDate} onChange={(event) => setPreviewDate(event.target.value)} />
            <Button onClick={() => void runPreview()} loading={previewLoading} disabled={!previewDate}>查看结果</Button>
          </Space>
        </div>
        {preview && <Card size="small" className="time-preview-result" title={`${preview.service_date}：${preview.open ? '开放' : '闭馆'}`}>
          <Space orientation="vertical">
            <Typography.Text>时间窗口：{preview.windows.length ? preview.windows.map((window) => `${minuteLabel(window.start_minute)}–${minuteLabel(window.end_minute)}（末入 ${minuteLabel(window.last_entry_minute)}）`).join('；') : '无'}</Typography.Text>
            <Typography.Text>固定场次：{preview.fixed_sessions.length ? preview.fixed_sessions.map((session) => `${minuteLabel(session.start_minute)}–${minuteLabel(session.end_minute)}`).join('；') : '无'}</Typography.Text>
            <Typography.Text>判定原因：{preview.reason_codes.length ? preview.reason_codes.map(reasonCodeLabel).join('；') : '正常周开放规则'}</Typography.Text>
          </Space>
        </Card>}
        <section className="time-evidence-section">
          <div className="time-evidence-section-heading">
            <div><Typography.Title level={5}>常规开放规则与固定场次</Typography.Title><Typography.Text type="secondary">维护每周重复的开放时段；演出、灯光秀等使用“固定场次”。</Typography.Text></div>
            {editable && <Button icon={<PlusOutlined />} onClick={() => openEditor('time_rule')}>新增开放规则</Button>}
          </div>
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
            { title: '来源', key: 'source', width: 220, render: (_: unknown, item) => <Space size={4}><Typography.Text>{sourceLabelById(evidence, item.source_record_id, sourceChannels)}</Typography.Text><Tag color={item.source_record_valid ? 'success' : 'error'}>{item.source_record_valid ? '有效' : '无效'}</Tag></Space> },
            ...((editable || reviewable) ? [{ title: '操作', key: 'actions', width: 280, fixed: 'right' as const, render: (_: unknown, item: PlaceTimeRuleEvidence) => <Space>{editable && <><Button size="small" icon={<EditOutlined />} onClick={() => openEditor('time_rule', item)}>编辑</Button>{reviewContext && item.active && <Button size="small" danger onClick={() => void retire('time_rule', item.time_rule_id)}>停用</Button>}{!reviewContext && <Popconfirm title="删除这条开放规则或固定场次？" description="删除后不再出现在本修订的规则列表中，操作审计仍保留。" okText="删除" cancelText="取消" onConfirm={() => deleteRule(item.time_rule_id)}><Button size="small" danger disabled={saving}>删除</Button></Popconfirm>}</>}{reviewable && item.active && <><Button size="small" type="primary" onClick={() => void review('time_rule', item.time_rule_id, 'human_verified')}>通过</Button><Button size="small" onClick={() => void review('time_rule', item.time_rule_id, 'rejected')}>驳回</Button></>}</Space> }] : []),
          ]}
          locale={{ emptyText: evidence.revision.is_always_open ? '全天开放，无需周时间窗' : '尚未采集周规则或固定场次' }}
          />
        </section>
        <section className="time-evidence-section">
          <div className="time-evidence-section-heading">
            <div><Typography.Title level={5}>固定闭馆日</Typography.Title><Typography.Text type="secondary">例如博物馆每周一闭馆；节假日冲突由下方日期例外覆盖。</Typography.Text></div>
            {editable && <Button icon={<PlusOutlined />} onClick={() => openEditor('closure')}>新增闭馆日</Button>}
          </div>
          <Table<PlaceClosureEvidence>
          rowKey="closure_id"
          size="small"
          pagination={false}
          dataSource={evidence.closures}
          columns={[
            { title: '闭馆星期', dataIndex: 'weekday', render: weekdayLabel },
            { title: '状态', dataIndex: 'review_status', render: (value: string, item) => <Space size={4}><Tag color={reviewStatusColor(value)}>{reviewStatusLabel(value)}</Tag>{!item.active && <Tag>已停用</Tag>}</Space> },
            { title: '来源', key: 'source', render: (_: unknown, item) => <Space size={4}>{sourceLabelById(evidence, item.source_record_id, sourceChannels)}<Tag color={item.source_record_valid ? 'success' : 'error'}>{item.source_record_valid ? '有效' : '无效'}</Tag></Space> },
            ...((editable || reviewable) ? [{ title: '操作', key: 'actions', width: 280, fixed: 'right' as const, render: (_: unknown, item: PlaceClosureEvidence) => <Space>{editable && <><Button size="small" icon={<EditOutlined />} onClick={() => openEditor('closure', item)}>编辑</Button>{reviewContext && item.active && <Button size="small" danger onClick={() => void retire('closure', item.closure_id)}>停用</Button>}</>}{reviewable && item.active && <><Button size="small" type="primary" onClick={() => void review('closure', item.closure_id, 'human_verified')}>通过</Button><Button size="small" onClick={() => void review('closure', item.closure_id, 'rejected')}>驳回</Button></>}</Space> }] : []),
          ]}
          locale={{ emptyText: '没有固定闭馆日记录' }}
          />
        </section>
        <section className="time-evidence-section time-evidence-section-emphasis">
          <div className="time-evidence-section-heading">
            <div><Typography.Title level={5}>日期例外</Typography.Title><Typography.Text type="secondary">可选项，仅用于法定节假日开放、顺延闭馆或临时调整；临时关闭优先级最高。没有例外不影响审核与发布。</Typography.Text></div>
            {editable && <Space wrap><Button loading={holidayCalendarsLoading} onClick={() => { if (!holidayCalendars.length) { void onReloadHolidayCalendars(); return } form.resetFields(); form.setFieldsValue({ calendar_id: holidayCalendars[0]?.calendar_id, shift_closure: true, start_time: '09:00', end_time: '17:00', last_entry_time: '16:30' }); setEditing(null); setModal('holiday') }}>{holidayCalendars.length ? '按节假日历生成' : '加载节假日历'}</Button><Button type="primary" icon={<PlusOutlined />} onClick={() => openEditor('date_exception')}>新增单日例外</Button></Space>}
          </div>
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
            { title: '来源', key: 'source', width: 220, render: (_: unknown, item) => <Space size={4}>{sourceLabelById(evidence, item.source_record_id, sourceChannels)}<Tag color={item.source_record_valid ? 'success' : 'error'}>{item.source_record_valid ? '有效' : '无效'}</Tag></Space> },
            ...((editable || reviewable) ? [{ title: '操作', key: 'actions', width: 280, fixed: 'right' as const, render: (_: unknown, item: PlaceDateExceptionEvidence) => <Space>{editable && <><Button size="small" icon={<EditOutlined />} onClick={() => openEditor('date_exception', item)}>编辑</Button>{reviewContext && item.active && <Button size="small" danger onClick={() => void retire('date_exception', item.date_exception_id)}>停用</Button>}</>}{reviewable && item.active && <><Button size="small" type="primary" onClick={() => void review('date_exception', item.date_exception_id, 'human_verified')}>通过</Button><Button size="small" onClick={() => void review('date_exception', item.date_exception_id, 'rejected')}>驳回</Button></>}</Space> }] : []),
          ]}
          locale={{ emptyText: '没有日期例外记录' }}
          />
        </section>
      </Space>
      <Modal title={timeEvidenceModalTitle(modal)} open={modal !== null} onOk={() => void (modal === 'holiday' ? generateHoliday() : save())} onCancel={() => setModal(null)} confirmLoading={saving} okText={editing ? '保存修改' : modal === 'holiday' ? '确认生成' : '确认新增'} cancelText="取消" width={760} className="time-evidence-modal" forceRender>
        <Form form={form} layout="vertical">
          {modal === 'holiday' && <>
            <Alert type="info" showIcon title="只生成真实冲突日期" description="系统只处理法定节假日恰好落在固定闭馆日的情况，并可生成节后顺延闭馆；生成后仍需逐项人工核验。" />
            <section className="time-modal-section">
              <Typography.Title level={5}>生成依据</Typography.Title>
              <div className="time-modal-grid">
                <Form.Item name="calendar_id" label="法定节假日历" rules={[{ required: true, message: '请选择法定节假日历' }]}><Select options={holidayCalendars.map((calendar) => ({ value: calendar.calendar_id, label: calendar.display_name }))} placeholder="选择已核验的年度节假日历" /></Form.Item>
                <SourceRecordField sources={evidence.sources} sourceChannels={sourceChannels} required={false} extraOption={selectedHolidayCalendar?.source_record_id ? { value: selectedHolidayCalendar.source_record_id, label: '该年度法定节假日历官方来源' } : undefined} />
              </div>
              {selectedHolidayCalendar && <Typography.Paragraph type="secondary" className="holiday-calendar-note">日历依据：{selectedHolidayCalendar.source_note}；包含 {selectedHolidayCalendar.periods.length} 段法定节假日。</Typography.Paragraph>}
            </section>
            <section className="time-modal-section">
              <Typography.Title level={5}>节假日开放时间</Typography.Title>
              <div className="time-form-grid">
                <TimeField required name="start_time" nextDayName="start_next_day" label="开始时间" hint="节假日开放开始时间，例如 09:00。" />
                <TimeField required name="end_time" nextDayName="end_next_day" label="结束时间" hint="节假日开放结束时间，例如 17:00。" />
                <TimeField name="last_entry_time" nextDayName="last_entry_next_day" label="最晚入馆" hint="没有最晚入馆限制时可留空。" />
              </div>
              <Form.Item name="shift_closure" valuePropName="checked" initialValue style={{ marginBottom: 0 }}><Checkbox>节假日结束后的第一天顺延闭馆</Checkbox></Form.Item>
            </section>
          </>}
          {modal === 'time_rule' && <>
            <section className="time-modal-section"><Typography.Title level={5}>规则范围</Typography.Title><div className="time-modal-grid"><Form.Item name="rule_kind" label="规则类型" rules={[{ required: true }]}><Select options={[{ value: 'opening_hours', label: '开放时间' }, { value: 'fixed_session', label: '固定场次' }, { value: 'last_entry', label: '最晚入园规则' }]} /></Form.Item><Form.Item name="weekdays" label="适用星期" rules={[{ required: true }]}><Select mode="multiple" options={weekdayOptions()} /></Form.Item></div></section>
            <section className="time-modal-section"><Typography.Title level={5}>时间与有效期</Typography.Title><MinuteFields required /><div className="time-modal-grid"><Form.Item name="valid_from" label="有效期开始"><Input type="date" /></Form.Item><Form.Item name="valid_to" label="有效期结束"><Input type="date" /></Form.Item></div></section>
            <section className="time-modal-section"><Typography.Title level={5}>证据来源</Typography.Title><SourceRecordField sources={evidence.sources} sourceChannels={sourceChannels} /></section>
          </>}
          {modal === 'closure' && <>
            <section className="time-modal-section"><Typography.Title level={5}>闭馆设置</Typography.Title><div className="time-modal-grid"><Form.Item name="weekday" label="闭馆星期" rules={[{ required: true }]}><Select options={weekdayOptions()} /></Form.Item><SourceRecordField sources={evidence.sources} sourceChannels={sourceChannels} /></div></section>
          </>}
          {modal === 'date_exception' && <>
            <section className="time-modal-section"><Typography.Title level={5}>例外设置</Typography.Title><div className="time-modal-grid"><Form.Item name="service_date" label="例外日期" rules={[{ required: true }]}><Input type="date" /></Form.Item><Form.Item name="exception_kind" label="例外类型" rules={[{ required: true }]}><Select options={[{ value: 'closed', label: '临时关闭' }, { value: 'open_override', label: '开放覆盖' }, { value: 'session_override', label: '场次覆盖' }]} /></Form.Item></div></section>
            {exceptionKind === 'closed'
              ? <Alert type="warning" showIcon title="该日期将全天关闭" description="临时关闭优先于周规则、固定闭馆日和其他开放覆盖，不需要填写时间。" />
              : <section className="time-modal-section"><Typography.Title level={5}>{exceptionKind === 'session_override' ? '覆盖场次' : '覆盖开放时间'}</Typography.Title><MinuteFields required /></section>}
            <section className="time-modal-section"><Typography.Title level={5}>证据来源</Typography.Title><SourceRecordField sources={evidence.sources} sourceChannels={sourceChannels} /></section>
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
  return dayOffset > 0 ? `次日 ${time}` : time
}

type TimeFormValues = {
  start_time?: string
  start_next_day?: boolean
  end_time?: string
  end_next_day?: boolean
  last_entry_time?: string
  last_entry_next_day?: boolean
}

function timeRuleFormValues(rule: PlaceTimeRuleEvidence): TimeFormValues & Partial<PlaceTimeRuleEvidence> {
  return {
    ...rule,
    start_time: minuteInputValue(rule.start_minute),
    start_next_day: isNextDay(rule.start_minute),
    end_time: minuteInputValue(rule.end_minute),
    end_next_day: isNextDay(rule.end_minute),
    last_entry_time: minuteInputValue(rule.last_entry_minute),
    last_entry_next_day: isNextDay(rule.last_entry_minute),
  }
}

function dateExceptionFormValues(exception: PlaceDateExceptionEvidence): TimeFormValues & Partial<PlaceDateExceptionEvidence> {
  return {
    ...exception,
    start_time: minuteInputValue(exception.start_minute),
    start_next_day: isNextDay(exception.start_minute),
    end_time: minuteInputValue(exception.end_minute),
    end_next_day: isNextDay(exception.end_minute),
    last_entry_time: minuteInputValue(exception.last_entry_minute),
    last_entry_next_day: isNextDay(exception.last_entry_minute),
  }
}

export function timeFormMinutes(values: TimeFormValues): Pick<PlaceTimeRuleInput, 'start_minute' | 'end_minute' | 'last_entry_minute'> {
  const start_minute = parseTimeInput(values.start_time, values.start_next_day)
  const end_minute = parseTimeInput(values.end_time, values.end_next_day)
  const last_entry_minute = parseTimeInput(values.last_entry_time, values.last_entry_next_day)
  if (start_minute !== null && end_minute !== null && end_minute <= start_minute) {
    throw new Error('结束时间必须晚于开始时间；如果跨午夜，请勾选结束时间旁的“次日”')
  }
  if (last_entry_minute !== null && start_minute !== null && last_entry_minute > start_minute && end_minute !== null && last_entry_minute > end_minute) {
    throw new Error('最晚入园时间不能晚于结束时间；请检查时间或“次日”标记')
  }
  return { start_minute, end_minute, last_entry_minute }
}

export function parseTimeInput(value: string | undefined, nextDay = false): number | null {
  if (!value) return null
  const match = /^(\d{2}):(\d{2})$/.exec(value)
  if (!match) throw new Error('时间必须填写为小时:分钟，例如 09:30')
  const hours = Number(match[1])
  const minutes = Number(match[2])
  if (hours > 23 || minutes > 59) throw new Error('时间格式无效，请填写 00:00 至 23:59')
  return hours * 60 + minutes + (nextDay ? 1440 : 0)
}

function minuteInputValue(value: number | null): string | undefined {
  if (value === null) return undefined
  const minute = value % 1440
  return `${String(Math.floor(minute / 60)).padStart(2, '0')}:${String(minute % 60).padStart(2, '0')}`
}

function isNextDay(value: number | null): boolean {
  return value !== null && value >= 1440
}

function MinuteFields({ required = false }: { required?: boolean }) {
  return <>
    <Typography.Text type="secondary" className="time-field-guidance">请按当地时间填写；跨午夜时在结束时间或最晚入园时间旁勾选“次日”，例如 23:00–次日 02:00。</Typography.Text>
    <div className="time-form-grid">
      <TimeField required={required} name="start_time" nextDayName="start_next_day" label="开始时间" hint="直接填写当地时间，例如 09:30。只有开始时间本身属于次日时才勾选“次日”。" />
      <TimeField required={required} name="end_time" nextDayName="end_next_day" label="结束时间" hint="如果结束时间落在开始后的第二天，例如 23:00–次日 02:00，请勾选“次日”。" />
      <TimeField name="last_entry_time" nextDayName="last_entry_next_day" label="最晚入园" hint="游客最晚允许进入的当地时间；没有限制时留空。若发生在次日，请勾选“次日”。" />
    </div>
  </>
}


function weekdayOptions() {
  return [1, 2, 3, 4, 5, 6, 7].map((value) => ({ value, label: weekdayLabel(value) }))
}

function timeEvidenceModalTitle(kind: 'time_rule' | 'closure' | 'date_exception' | 'holiday' | null): string {
  if (kind === 'time_rule') return '周规则或固定场次'
  if (kind === 'closure') return '固定闭馆日'
  if (kind === 'date_exception') return '日期例外'
  if (kind === 'holiday') return '法定节假日规则'
  return '时间证据'
}

function weekdayLabel(value: number): string {
  return ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][value - 1] ?? `星期${value}`
}



type PublicationBlocker = {
  code: string
  title: string
  description: string
  actionLabel?: string
  target?: 'review-actions' | 'o04-evidence' | 'o05-evidence' | 'o06-source-conflicts' | 'o07-evidence' | 'revision-basic-facts'
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
  if (sourceConflicts.some((item) => !item.resolved)) codes.push('SOURCE_CONFLICT_UNRESOLVED')

  // 基础事实阻断项（与后端 evaluate_review_readiness 的 basic 检查同口径）：
  // 阻断 flag 只能通过编辑并保存名称/分类/时长清除，证据核验不会碰它们。
  const BASIC_FACT_BLOCKING_FLAGS = ['NAME_REQUIRES_HUMAN_VERIFICATION', 'CATEGORY_REQUIRES_HUMAN_VERIFICATION', 'DURATION_NOT_COLLECTED'] as const
  if (revision.lifecycle_status === 'candidate' && revision.review_flags.some((flag) => BASIC_FACT_BLOCKING_FLAGS.includes(flag as typeof BASIC_FACT_BLOCKING_FLAGS[number]))) {
    codes.push('BASIC_FACTS_NOT_CONFIRMED')
  }

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
    if (evidence.relations?.some((item) => item.active && item.review_status !== 'human_verified')) codes.push('RELATION_EVIDENCE_UNVERIFIED')
    if ((evidence.relations ?? []).filter((item) => item.active).length === 0 && revision.relation_review_status === 'pending') codes.push('RELATION_REVIEW_REQUIRED')
  }
  if (!revision.solver_eligible) codes.push('PLACE_NOT_SOLVER_ELIGIBLE')
  if (publicationCheck && !publicationCheck.publishable) codes.push(...publicationCheck.reason_codes)

  const priority = [
    'BASIC_FACTS_NOT_CONFIRMED',
    'FIXED_SESSION_REQUIRED',
    'FIXED_SESSION_AMBIGUOUS',
    'SOURCE_CONFLICT_UNRESOLVED',
    'TIME_RULE_UNRESOLVED',
    'MISSING_VERIFIED_TIME_RULE',
    'MISSING_VERIFIED_GEOMETRY',
    'MISSING_VERIFIED_ACCESS_POINT',
    'RELATION_REVIEW_REQUIRED',
    'RELATION_EVIDENCE_UNVERIFIED',
    'OVERLAPPING_SELECTION_UNRESOLVED',
    'REVISION_NOT_HUMAN_VERIFIED',
    'PLACE_NOT_SOLVER_ELIGIBLE',
  ]
  const uniqueCodes = [...new Set(codes)].sort((left, right) => {
    const leftIndex = priority.indexOf(left)
    const rightIndex = priority.indexOf(right)
    return (leftIndex < 0 ? priority.length : leftIndex) - (rightIndex < 0 ? priority.length : rightIndex)
  })
  return uniqueCodes.map((code): PublicationBlocker => {
    if (code === 'BASIC_FACTS_NOT_CONFIRMED') return {
      code, title: '基础事实尚未经编辑确认',
      description: `名称、分类或游览时长还没有人工确认过（系统标记：${revision.review_flags.filter((flag) => BASIC_FACT_BLOCKING_FLAGS.includes(flag as typeof BASIC_FACT_BLOCKING_FLAGS[number])).map((flag) => reviewFlagLabel(flag)).join('、') || '待核验'}）。请在页面上方的“基础信息”中重新保存一次名称与分类，并把时长改为真实游览时长（当前导入值 ${revision.duration_recommended} 分钟通常是占位值）。仅核验证据区不会清除这些标记。`,
      actionLabel: '编辑基础事实', target: 'revision-basic-facts',
    }
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
      description: `检测到 ${sourceConflicts.filter((item) => !item.resolved).length} 组来源内容不一致。请打开 O06 查看每条来源记录，核对后由数据编辑员标记处理完成。`,
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
        : `当前读取到 ${evidence?.time_rules.filter((item) => item.active).length ?? 0} 条有效开放时间规则，其中 ${evidence?.time_rules.filter((item) => item.active && item.review_status === 'human_verified').length ?? 0} 条已人工核验。需要至少一条当前有效来源支持、并已人工核验的“开放时间规则”；日期例外仅用于节假日/临时调整，不是必需项。`,
      actionLabel: '查看开放时间（O05）', target: 'o05-evidence',
    }
    if (code === 'OVERLAPPING_SELECTION_UNRESOLVED') return {
      code, title: reasonCodeLabel(code),
      description: '存在“重叠”或“同一体验”关系尚未裁决。请在 O07 选择已裁决或无需裁决，并填写裁决说明。',
      actionLabel: '查看关系裁决（O07）', target: 'o07-evidence',
    }
    if (code === 'RELATION_EVIDENCE_UNVERIFIED') return {
      code, title: '地点关系证据尚未审核',
      description: '关系裁决表示数据编辑员是否同意该关系；当前 O07 关系证据仍是“候选”，请由 reviewer 在关系表的“审核”列点击“通过”或“驳回”，再执行修订版本审核。',
      actionLabel: '审核关系证据（O07）', target: 'o07-evidence',
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


import { formatDateTime, localDateTimeValue, relationExplanation, relationMeaning, sourceLabelById, sourceRecordBusinessLabel, sourceRecordReferences } from './revisionDetailDisplay'
export { formatDateTime, localDateTimeValue, relationExplanation, relationMeaning, sourceLabelById, sourceRecordBusinessLabel, sourceRecordReferences } from './revisionDetailDisplay'

