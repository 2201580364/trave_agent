import { RevisionActionBar } from './RevisionActionBar'
import { formatDateTime } from './revisionDetailDisplay'
import { SourceConflictCard, VerificationSummaryCard } from './SourceConflictAndSummary'
import { RelationEvidenceCard } from './RelationEvidenceCard'
export { parseTimeInput, timeFormMinutes } from './TimeEvidenceCard'
import { TimeEvidenceCard } from './TimeEvidenceCard'
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
        <RevisionActionBar>
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
        </RevisionActionBar>
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

import { buildPublicationBlockers } from './publicationBlockers'

