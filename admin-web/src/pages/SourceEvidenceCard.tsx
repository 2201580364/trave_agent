// H3 / S7-4: source evidence editing retains the revision and audit boundary.
import { PlusOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Collapse, Form, Input, Modal, Select, Space, Table, Tag, Tooltip, Typography } from 'antd'
import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { adminErrorMessage } from '../api/errorMessages'
import type { CreatePlaceSourceRecordInput, PlaceEvidenceSource, PlaceRevision, PlaceRevisionEvidence, SourceChannel } from '../api/types'
import type { useAdminSession } from '../auth/AdminSessionProvider'
import { collectionModeLabel, sourceDecisionLabel, sourceKindLabel } from '../ui/displayLabels'
import { formatDateTime, localDateTimeValue, sourceRecordBusinessLabel, sourceRecordReferences, isFormValidationError } from './revisionDetailDisplay'
import { FieldLabel } from './revisionDetailFields'

type SourceRecordFormValues = {
  source_id: string
  source_url: string
  collection_mode: string
  observed_at: string
  content_sha256?: string
  reason_text?: string
}

export function SourceEvidenceCard({ api, evidence, revision, sourceChannels, canEdit, onChanged, onSuccess, onError }: {
  api: ReturnType<typeof useAdminSession>['api']
  evidence: PlaceRevisionEvidence | null
  revision: PlaceRevision
  sourceChannels: SourceChannel[]
  canEdit: boolean
  onChanged: () => Promise<void>
  onSuccess: (text: string) => void
  onError: (message: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm<SourceRecordFormValues>()
  const selectedSourceId = Form.useWatch('source_id', form)
  const selectedChannel = sourceChannels.find((item) => item.source_id === selectedSourceId)
  const reviewContext = new URLSearchParams(useLocation().search).get('from') === 'review'
  const editable = revision.lifecycle_status === 'candidate' && canEdit

  const openCreate = () => {
    const first = sourceChannels[0]
    form.setFieldsValue({
      source_id: first?.source_id,
      collection_mode: first?.collection_modes[0],
      observed_at: localDateTimeValue(new Date()),
      source_url: '',
      content_sha256: undefined,
      reason_text: undefined,
    })
    setOpen(true)
  }

  const save = async () => {
    setSaving(true)
    try {
      const values = await form.validateFields()
      const input: CreatePlaceSourceRecordInput = {
        expected_revision_version: revision.revision_version,
        source_id: values.source_id,
        source_url: values.source_url.trim(),
        collection_mode: values.collection_mode,
        observed_at: new Date(values.observed_at).toISOString(),
        content_sha256: values.content_sha256?.trim() || undefined,
        operation_intent_id: `source-record-create-${crypto.randomUUID()}`,
        reason_code: 'PLACE_SOURCE_RECORD_ADDED',
        reason_text: values.reason_text?.trim() || undefined,
      }
      await api.createSourceRecord(revision.place_revision_id, input)
      setOpen(false)
      await onChanged()
      onSuccess('来源记录已新增并关联当前修订版本，需要重新确认冲突并送审')
    } catch (reason) {
      if (!isFormValidationError(reason)) onError(adminErrorMessage(reason))
    } finally {
      setSaving(false)
    }
  }

  const detach = (source: PlaceEvidenceSource) => {
    const references = sourceRecordReferences(evidence, source.source_record_id)
    if (references.length > 0) return
    Modal.confirm({
      title: '从当前修订移除来源记录？',
      content: '来源记录本身会保留用于历史追溯，只解除与当前修订版本的关联。移除后需要重新确认冲突并送审。',
      okText: '确认移除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        setSaving(true)
        try {
          await api.detachSourceRecord(revision.place_revision_id, source.source_record_id, {
            expected_revision_version: revision.revision_version,
            operation_intent_id: `source-record-detach-${crypto.randomUUID()}`,
            reason_code: 'PLACE_SOURCE_RECORD_REMOVED',
          })
          await onChanged()
          onSuccess('来源记录已从当前修订移除，历史记录仍保留')
        } catch (reason) {
          onError(adminErrorMessage(reason))
        } finally {
          setSaving(false)
        }
      },
    })
  }

  return <Card title="来源证据">
    <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between' }} align="start">
        <Typography.Paragraph type="secondary" style={{ margin: 0, maxWidth: 900 }}>
          来源记录用于证明名称、坐标、开放时间等事实来自哪里。请选择系统已审核的来源渠道，并填写实际查看的具体页面；不要填写搜索结果页、网站首页或带密钥的接口请求地址。
        </Typography.Paragraph>
        {editable && <Button type="primary" icon={<PlusOutlined />} onClick={openCreate} disabled={sourceChannels.length === 0}>新增来源记录</Button>}
      </Space>
      {sourceChannels.length === 0 && editable && <Alert type="warning" showIcon title="来源渠道暂不可用，请刷新页面后重试" />}
      <Table<PlaceEvidenceSource>
        rowKey="source_record_id"
        size="small"
        pagination={false}
        dataSource={evidence?.sources ?? []}
        scroll={{ x: 1050 }}
        columns={[
          { title: '来源渠道', key: 'channel', width: 220, render: (_: unknown, item) => sourceRecordBusinessLabel(item, sourceChannels) },
          { title: '渠道类型', key: 'kind', width: 140, render: (_: unknown, item) => sourceKindLabel(sourceChannels.find((channel) => channel.source_id === item.source_id)?.source_kind) },
          { title: '来源决策', dataIndex: 'source_decision', width: 120, render: (value: string) => <Tag color={value === 'approved' ? 'success' : 'warning'}>{sourceDecisionLabel(value)}</Tag> },
          { title: '采集方式', dataIndex: 'collection_mode', width: 130, render: collectionModeLabel },
          { title: '具体来源地址', dataIndex: 'source_url', width: 300, ellipsis: true, render: (value: string) => <Tooltip title={value}><Typography.Link href={value} target="_blank" rel="noreferrer" ellipsis>{value}</Typography.Link></Tooltip> },
          { title: '观察时间', dataIndex: 'observed_at', width: 190, render: formatDateTime },
          { title: '使用情况', key: 'usage', width: 180, render: (_: unknown, item) => {
            const references = sourceRecordReferences(evidence, item.source_record_id)
            return references.length > 0 ? <Tooltip title={`正在支持：${references.join('、')}`}><Tag color="processing">被 {references.length} 类证据使用</Tag></Tooltip> : <Tag>尚未被子证据使用</Tag>
          } },
          ...(editable ? [{ title: '操作', key: 'actions', fixed: 'right' as const, width: 150, render: (_: unknown, item: PlaceEvidenceSource) => {
            const references = sourceRecordReferences(evidence, item.source_record_id)
            const attached = item.attached_to_revision ?? revision.source_record_ids.includes(item.source_record_id)
            return attached ? <Tooltip title={references.length > 0 ? `请先把这些证据改用其他来源：${references.join('、')}` : '只解除当前修订关联，历史来源记录不会删除'}><span><Button size="small" danger disabled={references.length > 0 || saving} onClick={() => detach(item)}>从当前修订移除</Button></span></Tooltip> : <Tag>仅历史追溯</Tag>
          } }] : []),
        ]}
        locale={{ emptyText: '当前修订版本尚未关联来源记录' }}
      />
    </Space>
    <Modal title="新增来源记录" open={open} onOk={() => void save()} onCancel={() => setOpen(false)} confirmLoading={saving} okText="确认新增" cancelText="取消" forceRender>
      <Form form={form} layout="vertical">
        <Form.Item name="source_id" label={<FieldLabel label="来源渠道" hint="这里只能选择已通过系统治理审核、且允许支持地点事实的渠道。" />} rules={[{ required: true, message: '请选择来源渠道' }]}>
          <Select showSearch optionFilterProp="label" options={sourceChannels.map((channel) => ({ value: channel.source_id, label: `${channel.display_name}（${sourceDecisionLabel(channel.decision)}）` }))} onChange={(value) => {
            const channel = sourceChannels.find((item) => item.source_id === value)
            form.setFieldValue('collection_mode', channel?.collection_modes[0])
          }} />
        </Form.Item>
        {selectedChannel && <Alert type={selectedChannel.decision === 'approved' ? 'success' : 'warning'} showIcon title={`${selectedChannel.display_name}：${sourceDecisionLabel(selectedChannel.decision)}`} description={<Space orientation="vertical" size={2}>{selectedChannel.base_urls.map((url) => <Typography.Text key={url} type="secondary">允许地址：{url}</Typography.Text>)}{selectedChannel.conditions.slice(0, 2).map((condition) => <Typography.Text key={condition} type="secondary">• {condition}</Typography.Text>)}</Space>} style={{ marginBottom: 16 }} />}
        <Form.Item name="source_url" label={<FieldLabel label="具体来源地址" hint="填写能直接看到该地点事实的 HTTPS 页面或已审核 API 文档地址；不能填写带 Key、token 或签名参数的请求地址。" />} rules={[{ required: true, message: '请输入具体来源地址' }, { type: 'url', message: '请输入完整网址' }, { pattern: /^https:\/\//i, message: '来源地址必须使用 HTTPS' }]}><Input placeholder="https://官方域名/具体页面" /></Form.Item>
        <Form.Item name="observed_at" label={<FieldLabel label="观察时间" hint="填写你实际查看页面或获得接口结果的时间，不是页面文章的发布时间。" />} rules={[{ required: true, message: '请选择观察时间' }]}><Input type="datetime-local" /></Form.Item>
        <Form.Item name="collection_mode" label={<FieldLabel label="采集方式" hint="人工在浏览器中核对页面选“人工查阅”；程序读取公开网页选“公开页面采集”；接口返回选“接口采集”。" />} rules={[{ required: true, message: '请选择采集方式' }]}><Select options={(selectedChannel?.collection_modes ?? []).map((value) => ({ value, label: collectionModeLabel(value) }))} /></Form.Item>
        <Collapse ghost items={[{ key: 'advanced', label: '高级追溯信息（通常无需填写）', children: <><Form.Item name="content_sha256" label={<FieldLabel label="内容哈希" hint="仅在系统或采集工具已生成 64 位 SHA-256 时填写；人工审核员通常留空。" />} rules={[{ pattern: /^[0-9a-fA-F]{64}$/, message: '内容哈希必须是 64 位十六进制字符' }]}><Input placeholder="可留空" /></Form.Item><Form.Item name="reason_text" label="补充说明"><Input.TextArea rows={3} maxLength={500} placeholder="可填写该来源支持了哪些事实，避免复制网页全文" showCount /></Form.Item></> }]} />
      </Form>
    </Modal>
  </Card>
}

