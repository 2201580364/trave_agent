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

