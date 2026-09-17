import { Alert, Button, Card, Tooltip } from 'antd'
import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { Form, Modal, Input, Select, Space, Table, Tag, Typography } from 'antd'
import type { PlaceRelationEvidence, PlaceRevision, PlaceRevisionEvidence, SourceChannel } from '../api/types'
import { useAdminSession } from '../auth/AdminSessionProvider'
import { adminErrorMessage } from '../api/errorMessages'
import { createOperationIntent } from '../api/adminApi'
import { relationExplanation, relationMeaning, sourceLabelById, isFormValidationError, reviewStatusColor } from './revisionDetailDisplay'
import { InstructionHint } from './revisionDetailFields'
import { relationReviewStatusLabel, relationTypeLabel, relationResolutionLabel, reviewStatusLabel } from '../ui/displayLabels'
export function RelationEvidenceCard({ api, evidence, revision, sourceChannels, canEdit, canReview, onChanged, onSuccess, onError }: {
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
        operation_intent_id: createOperationIntent('relation-evidence-review'),
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
        operation_intent_id: createOperationIntent('relation-resolution'),
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
        operation_intent_id: createOperationIntent('relation-review-none'),
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


