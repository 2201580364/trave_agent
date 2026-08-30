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
import { Alert, Button, Card, Descriptions, Form, Input, InputNumber, Modal, Space, Tag, Typography, message } from 'antd'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { adminErrorMessage } from '../api/errorMessages'
import type { PlaceRevision } from '../api/types'
import { useAdminSession } from '../auth/AdminSessionProvider'
import { ErrorNotice } from '../components/ErrorNotice'

const lifecycleLabels: Record<PlaceRevision['lifecycle_status'], string> = {
  candidate: '候选',
  human_verified: '人工已核验',
  published: '已发布',
  retired: '已退役',
}

const placeKindLabels: Record<string, string> = {
  attraction: '景点',
  scenic_area: '景区',
  neighborhood: '街区',
  walking_route: '步行路线',
  market: '市集',
  show: '演出/固定场次',
  experience: '体验',
}

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
  const { api } = useAdminSession()
  const navigate = useNavigate()
  const { revisionId } = useParams<{ revisionId: string }>()
  const [revision, setRevision] = useState<PlaceRevision | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editOpen, setEditOpen] = useState(false)
  const [working, setWorking] = useState(false)
  const [form] = Form.useForm()

  const load = useCallback(async () => {
    if (!revisionId) {
      setError('缺少 Revision ID')
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      setRevision(await api.getPlaceRevision(revisionId))
    } catch (reason) {
      setRevision(null)
      setError(adminErrorMessage(reason))
    } finally {
      setLoading(false)
    }
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
      message.success(`已创建 Revision ${created.revision_number}`)
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
      message.success('Revision 已保存，需重新送审')
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
      message.success('已送入审核队列')
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
      message.success('新快照已发布')
      await load()
    } catch (reason) {
      setError(adminErrorMessage(reason))
    } finally {
      setWorking(false)
    }
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div className="page-heading-row">
        <div>
          <Typography.Title level={2}>Revision 详情</Typography.Title>
          <Typography.Paragraph type="secondary">
            O03：核对候选地点的业务事实、生命周期和当前发布阻断摘要。
          </Typography.Paragraph>
        </div>
        <Space wrap>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/candidates')}>
            返回候选地点
          </Button>
          {revision && revision.lifecycle_status === 'candidate' && (
            <Space.Compact>
              <Button icon={<EditOutlined />} onClick={() => { form.setFieldsValue({ canonical_name: revision.canonical_name, address: revision.address, duration_recommended: revision.duration_recommended }); setEditOpen(true) }}>
                编辑候选
              </Button>
              <Button icon={<SendOutlined />} onClick={() => void submitReview()} loading={working}>
                送审
              </Button>
            </Space.Compact>
          )}
          {revision && revision.lifecycle_status === 'human_verified' && (
            <Button type="primary" icon={<CloudUploadOutlined />} onClick={() => void publish()} loading={working}>
              发布新快照
            </Button>
          )}
          {revision && revision.lifecycle_status !== 'candidate' && (
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
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Space wrap>
                <Typography.Title level={3} style={{ margin: 0 }}>
                  {revision.canonical_name}
                </Typography.Title>
                <Tag color={revision.lifecycle_status === 'human_verified' ? 'success' : 'processing'}>
                  {lifecycleLabels[revision.lifecycle_status]}
                </Tag>
                <Tag>Revision {revision.revision_number}</Tag>
              </Space>
              <Typography.Text type="secondary">
                {revision.place_revision_id} · Place {revision.place_id}
              </Typography.Text>
            </Space>
          </Card>

          <Card title="基础事实">
            <Descriptions bordered size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
              <Descriptions.Item label="规范名称">{revision.canonical_name}</Descriptions.Item>
              <Descriptions.Item label="别名">{revision.aliases.join('、') || '未提供'}</Descriptions.Item>
              <Descriptions.Item label="区域">{revision.admin_area}</Descriptions.Item>
              <Descriptions.Item label="类型">{placeKindLabels[revision.place_kind] ?? revision.place_kind}</Descriptions.Item>
              <Descriptions.Item label="分类">{revision.category}</Descriptions.Item>
              <Descriptions.Item label="地址">{revision.address ?? '未提供'}</Descriptions.Item>
              <Descriptions.Item label="几何类型">{revision.geometry_kind}</Descriptions.Item>
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
              <Descriptions.Item label="室内/室外">{revision.indoor_outdoor}</Descriptions.Item>
              <Descriptions.Item label="适用时段">{revision.suitable_periods.join('、') || '未提供'}</Descriptions.Item>
              <Descriptions.Item label="适合人群">{revision.audience_tags.join('、') || '未提供'}</Descriptions.Item>
              <Descriptions.Item label="雨天适配">{revision.rain_suitability}</Descriptions.Item>
              <Descriptions.Item label="全天开放">{revision.is_always_open ? '是' : '否'}</Descriptions.Item>
              <Descriptions.Item label="求解器可用">
                {revision.solver_eligible ? <Tag color="success">可用</Tag> : <Tag color="error">不可用</Tag>}
              </Descriptions.Item>
              <Descriptions.Item label="待核验项" span={3}>
                {revision.review_flags.length > 0
                  ? revision.review_flags.map((flag) => (
                      <Tag key={flag} color="warning">
                        {reviewFlagLabels[flag] ?? flag}
                      </Tag>
                    ))
                  : '无'}
              </Descriptions.Item>
            </Descriptions>
          </Card>

          <Card title="治理状态">
            <Descriptions bordered size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
              <Descriptions.Item label="当前生命周期">{lifecycleLabels[revision.lifecycle_status]}</Descriptions.Item>
              <Descriptions.Item label="冲突裁决">{revision.conflicts_resolved ? '已完成' : '待处理'}</Descriptions.Item>
              <Descriptions.Item label="人工核验时间">{formatOptionalDateTime(revision.reviewed_at)}</Descriptions.Item>
              <Descriptions.Item label="发布时间">{formatOptionalDateTime(revision.published_at)}</Descriptions.Item>
              <Descriptions.Item label="Revision ID">{revision.place_revision_id}</Descriptions.Item>
              <Descriptions.Item label="Place ID">{revision.place_id}</Descriptions.Item>
            </Descriptions>
          </Card>

          <Card title="发布阻断摘要">
            {blockers.length === 0 ? (
              <Alert showIcon type="success" icon={<CheckCircleOutlined />} message="当前 Revision 没有从详情字段识别出的阻断项" />
            ) : (
              <Space direction="vertical" style={{ width: '100%' }}>
                <Alert showIcon type="warning" message={`当前有 ${blockers.length} 项需要处理`} />
                {blockers.map((blocker) => (
                  <Typography.Text key={blocker} type="secondary">
                    <CloseCircleOutlined /> {blocker}
                  </Typography.Text>
                ))}
              </Space>
            )}
            <Typography.Paragraph type="secondary" style={{ marginTop: 16, marginBottom: 0 }}>
              本摘要只基于当前 Revision API 返回字段；几何、访问点、开放时间、来源冲突和关系裁决的逐项证据将在 O04–O07 页面接入后显示。
            </Typography.Paragraph>
          </Card>
        </>
      )}
      {revision === null && loading && <Card loading />}
      <Modal title="编辑 candidate Revision" open={editOpen} onOk={() => void saveEdit()} onCancel={() => setEditOpen(false)} confirmLoading={working}>
        <Form form={form} layout="vertical">
          <Form.Item name="canonical_name" label="规范名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="address" label="地址"><Input /></Form.Item>
          <Form.Item name="duration_recommended" label="建议时长（分钟）" rules={[{ required: true, type: 'number', min: 0 }]}><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
        </Form>
      </Modal>
    </Space>
  )
}

function publicationBlockers(revision: PlaceRevision): string[] {
  const blockers: string[] = []
  if (revision.lifecycle_status === 'candidate') blockers.push('尚未完成人工核验，生命周期仍为 candidate')
  if (revision.source_record_ids.length === 0) blockers.push('缺少来源记录')
  if (!revision.conflicts_resolved) blockers.push('存在未完成裁决的冲突')
  if (!revision.solver_eligible) blockers.push('当前 Revision 尚不满足求解器使用条件')
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
