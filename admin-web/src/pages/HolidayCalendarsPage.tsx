import { CalendarOutlined, DeleteOutlined, PlusOutlined, ReloadOutlined, SyncOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Col, Descriptions, Form, Input, InputNumber, List, Modal, Radio, Row, Space, Statistic, Steps, Table, Tag, Tooltip, Typography, message, type TableColumnsType } from 'antd'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { adminErrorMessage } from '../api/errorMessages'
import type { HolidayCalendar, HolidayCalendarImpact, HolidayCalendarSyncJob, HolidayCalendarVersion } from '../api/types'
import { useAdminSession } from '../auth/AdminSessionProvider'
import { ErrorNotice } from '../components/ErrorNotice'

const statusLabels: Record<string, { label: string; color: string }> = {
  queued: { label: '等待同步', color: 'default' },
  running: { label: '正在同步', color: 'processing' },
  not_announced: { label: '年度安排尚未发布', color: 'gold' },
  temporarily_unavailable: { label: '官方来源暂不可用', color: 'orange' },
  needs_attention: { label: '需要人工处理', color: 'red' },
  validated_preview: { label: '预览校验通过', color: 'cyan' },
  published: { label: '已发布新版本', color: 'green' },
  up_to_date: { label: '已是最新版本', color: 'blue' },
  cancelled: { label: '已取消', color: 'default' },
}

const executionStages = [
  { key: 'discovering', title: '查找官方公告' },
  { key: 'fetching', title: '读取官方正文' },
  { key: 'extracting', title: 'AI 提取安排' },
  { key: 'validating', title: '确定性校验' },
  { key: 'preview_ready', title: '生成预览' },
  { key: 'publishing', title: '提交新版本' },
]

export function HolidayCalendarsPage() {
  const { api, hasPermission } = useAdminSession()
  const [calendars, setCalendars] = useState<HolidayCalendar[]>([])
  const [jobs, setJobs] = useState<HolidayCalendarSyncJob[]>([])
  const [executionAvailable, setExecutionAvailable] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [syncOpen, setSyncOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [selectedJob, setSelectedJob] = useState<HolidayCalendarSyncJob | null>(null)
  const [selectedCalendar, setSelectedCalendar] = useState<HolidayCalendarVersion | null>(null)
  const [selectedImpact, setSelectedImpact] = useState<HolidayCalendarImpact | null>(null)
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [previewJob, setPreviewJob] = useState<HolidayCalendarSyncJob | null>(null)
  const [form] = Form.useForm<{ year: number; mode: 'preview' | 'sync' }>()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [calendarResponse, jobResponse, capability] = await Promise.all([
        api.listHolidayCalendars(),
        api.listHolidayCalendarSyncJobs(),
        api.getHolidayCalendarSyncCapability(),
      ])
      setCalendars(calendarResponse.items)
      setJobs(jobResponse.items)
      if (selectedJobId) {
        const refreshed = jobResponse.items.find((item) => item.sync_job_id === selectedJobId)
        if (refreshed) setSelectedJob(refreshed)
      }
      setExecutionAvailable(capability.execution_available)
    } catch (reason) {
      setError(adminErrorMessage(reason))
    } finally {
      setLoading(false)
    }
  }, [api, selectedJobId])

  useEffect(() => { void load() }, [load])

  useEffect(() => {
    if (!jobs.some((item) => item.status === 'queued' || item.status === 'running')) return
    const timer = window.setInterval(() => void load(), 3000)
    return () => window.clearInterval(timer)
  }, [jobs, load])

  const submitSync = async () => {
    try {
      const values = await form.validateFields()
      setSubmitting(true)
      const job = await api.createHolidayCalendarSyncJob({
        ...values,
        operation_intent_id: `holiday-sync-${crypto.randomUUID()}`,
      })
      message.success(values.mode === 'preview' ? '预览任务已创建' : '同步发布任务已创建')
      setSyncOpen(false)
      setSelectedJob(job)
      setSelectedJobId(job.sync_job_id)
      await load()
    } catch (reason) {
      if (!(reason && typeof reason === 'object' && 'errorFields' in reason)) setError(adminErrorMessage(reason))
    } finally {
      setSubmitting(false)
    }
  }

  const years = useMemo(
    () => calendars.map((item) => Number(item.periods[0]?.start.slice(0, 4))).filter(Number.isFinite),
    [calendars],
  )
  const calendarColumns: TableColumnsType<HolidayCalendar> = [
    { title: '年度', width: 100, render: (_, item) => item.periods[0]?.start.slice(0, 4) ?? '未知' },
    { title: '日历名称', dataIndex: 'display_name' },
    { title: '状态', width: 110, render: () => <Tag color="green">已发布</Tag> },
    { title: '节假日范围', width: 120, render: (_, item) => `${item.periods.length} 段` },
    { title: '数据依据', dataIndex: 'source_note' },
    { title: '操作', fixed: 'right', width: 100, render: (_, item) => <Button type="link" onClick={async () => { try { const [calendar, impact] = await Promise.all([api.getHolidayCalendarVersion(item.calendar_id), api.getHolidayCalendarImpact(item.calendar_id)]); setSelectedCalendar(calendar); setSelectedImpact(impact) } catch (reason) { setError(adminErrorMessage(reason)) } }}>查看详情</Button> },
  ]
  const jobColumns: TableColumnsType<HolidayCalendarSyncJob> = [
    { title: '年度', dataIndex: 'year', width: 90 },
    { title: '同步方式', dataIndex: 'mode', width: 100, render: (value) => value === 'preview' ? '仅预览' : '同步并发布' },
    { title: '状态', dataIndex: 'status', width: 160, render: (value) => { const item = statusLabels[value] ?? { label: '未知状态', color: 'default' }; return <Tag color={item.color}>{item.label}</Tag> } },
    { title: '尝试次数', dataIndex: 'attempt_count', width: 100 },
    { title: '创建时间', dataIndex: 'created_at', width: 190, render: (value) => new Date(value).toLocaleString('zh-CN') },
    { title: '结果说明', render: (_, item) => jobResultText(item) },
    { title: '操作', fixed: 'right', width: 160, render: (_, item) => <Space size="small"><Button type="link" onClick={() => { setSelectedJob(item); setSelectedJobId(item.sync_job_id) }}>查看详情</Button>{(item.status === 'queued' || item.status === 'temporarily_unavailable') && <Button type="link" danger onClick={async () => { try { const cancelled = await api.cancelHolidayCalendarSyncJob(item.sync_job_id); setSelectedJob(cancelled); setSelectedJobId(cancelled.sync_job_id); message.success('同步任务已取消'); await load() } catch (reason) { setError(adminErrorMessage(reason)) } }}>取消</Button>}</Space> },
  ]

  return (
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      <div className="page-heading">
        <div>
          <Typography.Title level={2}><CalendarOutlined /> 中国法定节假日历</Typography.Title>
          <Typography.Paragraph type="secondary">统一维护中国大陆年度法定节假日安排，供地点开放时间和日期例外生成使用。</Typography.Paragraph>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void load()}>刷新</Button>
          <Button type="primary" icon={<SyncOutlined />} disabled={!executionAvailable || !hasPermission('holiday:calendar:write')} onClick={() => { form.setFieldsValue({ year: new Date().getFullYear() + 1, mode: 'preview' }); setSyncOpen(true) }}>同步节假日历</Button>
        </Space>
      </div>
      {error && <ErrorNotice message={error} onClose={() => setError(null)} />}
      {!executionAvailable && <Alert showIcon type="warning" title="自动同步执行服务尚未启用" description="当前可以查看已发布日历和历史任务；官方公告发现与 AI 抽取执行器完成配置后，系统才会开放同步按钮，避免任务永久停留在等待状态。" />}
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}><Card><Statistic title="已发布年度" value={calendars.length} suffix="个" /></Card></Col>
        <Col xs={24} md={8}><Card><Statistic title="最晚覆盖年度" value={years.length ? Math.max(...years) : '暂无'} /></Card></Col>
        <Col xs={24} md={8}><Card><Statistic title="最近同步任务" value={jobs.length} suffix="条" /></Card></Col>
      </Row>
      <Card title="已发布年度日历"><Table rowKey="calendar_id" loading={loading} columns={calendarColumns} dataSource={calendars} pagination={false} scroll={{ x: 900 }} /></Card>
      <Card title="最近同步任务"><Table rowKey="sync_job_id" loading={loading} columns={jobColumns} dataSource={jobs} pagination={false} scroll={{ x: 900 }} locale={{ emptyText: '暂无同步任务' }} /></Card>
      <Modal title="同步中国法定节假日历" open={syncOpen} confirmLoading={submitting} okText="创建任务" cancelText="取消" onOk={() => void submitSync()} onCancel={() => setSyncOpen(false)}>
        <Alert showIcon type="info" title="建议先执行预览" description="预览会抓取并校验官方公告，但不会改变当前已发布日历。确认结果无误后，再选择同步并发布。" style={{ marginBottom: 20 }} />
        <Form form={form} layout="vertical">
          <Form.Item name="year" label="日历年度" rules={[{ required: true, message: '请选择需要同步的年度' }]}><InputNumber min={2000} max={2200} precision={0} style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="mode" label="执行方式" rules={[{ required: true }]}><Radio.Group><Space orientation="vertical"><Radio value="preview">仅预览并校验（推荐）</Radio><Radio value="sync">校验通过后发布新版本</Radio></Space></Radio.Group></Form.Item>
        </Form>
      </Modal>
      <Modal title="同步任务详情" open={selectedJob !== null} footer={null} onCancel={() => { setSelectedJob(null); setSelectedJobId(null) }} width={720}>
        {selectedJob && <Space orientation="vertical" size="middle" style={{ width: '100%' }}><Alert type={selectedJob.status === 'running' ? 'info' : selectedJob.status === 'queued' ? 'warning' : selectedJob.status === 'needs_attention' ? 'error' : 'success'} showIcon title={jobProgressText(selectedJob)} description="任务会自动刷新；下方记录展示 AI 和系统按时间发生的实际执行过程。" />{selectedJob.status === 'running' && <ExecutionProgress job={selectedJob} />}<ExecutionTimeline job={selectedJob} />{selectedJob.status === 'validated_preview' && <Button type="primary" onClick={() => setPreviewJob(selectedJob)}>查看并确认本轮预览数据</Button>}<Descriptions bordered column={1} size="small" items={jobDetailItems(selectedJob)} />{(selectedJob.status === 'queued' || selectedJob.status === 'temporarily_unavailable') && <Button danger onClick={async () => { try { const cancelled = await api.cancelHolidayCalendarSyncJob(selectedJob.sync_job_id); setSelectedJob(cancelled); message.success('同步任务已取消'); await load() } catch (reason) { setError(adminErrorMessage(reason)) } }}>取消此任务</Button>}</Space>}
      </Modal>
      <Modal title="本轮预览数据确认" open={previewJob !== null} onCancel={() => setPreviewJob(null)} footer={null} width={1100}>{previewJob && <PreviewResult key={previewJob.sync_job_id} job={previewJob} onPublish={async (periods, workdays) => { try { const job = await api.confirmHolidayCalendarPreview(previewJob.sync_job_id, { periods, adjusted_workdays: workdays, operation_intent_id: `holiday-confirm-${crypto.randomUUID()}` }); setPreviewJob(null); setSelectedJob(job); setSelectedJobId(job.sync_job_id); message.success('预览内容已确认并完成入库发布'); await load() } catch (reason) { setError(adminErrorMessage(reason)) } }} />}</Modal>
      <Modal title="年度日历版本详情" open={selectedCalendar !== null} footer={null} onCancel={() => { setSelectedCalendar(null); setSelectedImpact(null) }} width={860}>
        {selectedCalendar && <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
          <Descriptions bordered column={2} size="small" items={[
            { key: 'year', label: '年度', children: selectedCalendar.year },
            { key: 'version', label: '版本', children: `第 ${selectedCalendar.version} 版` },
            { key: 'status', label: '状态', children: selectedCalendar.status === 'published' ? '当前已发布' : '历史版本' },
            { key: 'published', label: '发布时间', children: new Date(selectedCalendar.published_at).toLocaleString('zh-CN') },
          ]} />
          {selectedImpact && <Alert showIcon type={selectedImpact.changed_date_count > 0 ? 'warning' : 'success'} title={selectedImpact.compared_calendar_id ? `与上一版本相比，共有 ${selectedImpact.changed_date_count} 个日期发生变化` : '这是该年度的首个版本，没有上一版本可比较'} description={`已有 ${selectedImpact.affected_places.length} 个地点使用相关日历物化过日期例外；系统不会自动改写这些历史记录。`} />}
          <Table rowKey={(item) => `${item.holiday_name}-${item.start_date}`} size="small" pagination={false} dataSource={selectedCalendar.periods} columns={[
            { title: '节日', dataIndex: 'holiday_name' }, { title: '开始日期', dataIndex: 'start_date' }, { title: '结束日期', dataIndex: 'end_date' }, { title: '官方原文依据', dataIndex: 'evidence_quote' },
          ]} />
          <Table rowKey="service_date" size="small" pagination={false} dataSource={selectedCalendar.adjusted_workdays} columns={[
            { title: '调休上班日期', dataIndex: 'service_date' }, { title: '对应节日', dataIndex: 'holiday_name' }, { title: '官方原文依据', dataIndex: 'evidence_quote' },
          ]} locale={{ emptyText: '无调休上班日' }} />
          {selectedImpact && <Table rowKey="place_revision_id" size="small" pagination={false} dataSource={selectedImpact.affected_places} columns={[
            { title: '受影响地点', dataIndex: 'place_name' }, { title: '区域', dataIndex: 'admin_area' }, { title: '已物化日期例外', dataIndex: 'materialized_exception_count', render: (value) => `${value} 条` },
          ]} locale={{ emptyText: '暂无可追溯的受影响地点' }} />}
        </Space>}
      </Modal>
    </Space>
  )
}

function jobResultText(job: HolidayCalendarSyncJob) {
  const reason = typeof job.validation_result.reason === 'string' ? job.validation_result.reason : ''
  const labels: Record<string, string> = {
    official_announcement_not_found: '官方尚未发布该年度安排',
    official_source_unavailable: '中国政府网暂时无法访问，系统稍后重试',
    historical_announcement_not_found: '历史年度公告未检索到，请检查官方来源或稍后重试',
    extraction_service_unavailable: '智能结构化服务暂时不可用，系统稍后重试',
    announcement_extraction_failed: '公告结构化或确定性校验未通过，需要人工查看',
  }
  const detail = typeof job.validation_result.detail === 'string' ? job.validation_result.detail : ''
  return (labels[reason] ? `${labels[reason]}${detail ? `：${detail}` : ''}` : detail) || job.source_title || (job.status === 'queued' ? '等待后台同步服务处理' : '暂无补充说明')
}

function jobProgressText(job: HolidayCalendarSyncJob) {
  if (job.status === 'queued') return '任务已创建，等待后台同步服务领取'
  if (job.status === 'running') return `正在处理：第 ${job.attempt_count} 次尝试`
  if (job.status === 'temporarily_unavailable') return '官方来源或智能结构化服务暂时不可用，等待重试'
  if (job.status === 'cancelled') return '任务已取消，不会继续执行'
  return `任务处理完成：${statusLabels[job.status]?.label ?? '已结束'}`
}

function executionEvents(job: HolidayCalendarSyncJob): Array<{ stage: string; detail: string; at: string }> {
  const value = job.validation_result.execution_events
  if (!Array.isArray(value)) return []
  return value.filter((item): item is { stage: string; detail: string; at: string } => {
    if (!item || typeof item !== 'object') return false
    const event = item as Record<string, unknown>
    return typeof event.stage === 'string' && typeof event.detail === 'string' && typeof event.at === 'string'
  })
}

function ExecutionProgress({ job }: { job: HolidayCalendarSyncJob }) {
  const stage = typeof job.validation_result.stage === 'string' ? job.validation_result.stage : undefined
  const current = Math.max(0, executionStages.findIndex((item) => item.key === stage))
  return <Card size="small" title="AI 执行进度"><Steps size="small" current={current} items={executionStages.map((item) => ({ title: item.title }))} /></Card>
}

function ExecutionTimeline({ job }: { job: HolidayCalendarSyncJob }) {
  const events = executionEvents(job)
  return <Card size="small" title="AI 执行过程"><List size="small" dataSource={events} locale={{ emptyText: '该任务创建于过程记录启用前，暂无可回放的执行记录' }} renderItem={(event, index) => <List.Item><List.Item.Meta avatar={<Tag color={index === events.length - 1 && job.status === 'running' ? 'processing' : 'default'}>{index + 1}</Tag>} title={event.detail} description={new Date(event.at).toLocaleString('zh-CN')} /></List.Item>} /></Card>
}

function PreviewResult({ job, onPublish }: { job: HolidayCalendarSyncJob; onPublish: (periods: Array<Record<string, unknown>>, workdays: Array<Record<string, unknown>>) => Promise<void> }) {
  const [periods, setPeriods] = useState<Array<Record<string, unknown>>>(() => Array.isArray(job.validation_result.preview_periods) ? job.validation_result.preview_periods.map((item) => ({ ...(item as Record<string, unknown>), _row_key: crypto.randomUUID() })) : [])
  const [workdays, setWorkdays] = useState<Array<Record<string, unknown>>>(() => Array.isArray(job.validation_result.preview_adjusted_workdays) ? job.validation_result.preview_adjusted_workdays.map((item) => ({ ...(item as Record<string, unknown>), _row_key: crypto.randomUUID() })) : [])
  const [publishing, setPublishing] = useState(false)
  const hasData = periods.length > 0
  const update = (setter: typeof setPeriods, rows: Array<Record<string, unknown>>, index: number, field: string, value: string) => setter(rows.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: value } : item))
  const periodColumns: TableColumnsType<Record<string, unknown>> = [
    { title: '节假日', dataIndex: 'name', width: 120, render: (_, item, index) => <Input value={String(item.name ?? '')} onChange={(event) => update(setPeriods, periods, index, 'name', event.target.value)} /> },
    { title: '开始日期', dataIndex: 'start', width: 150, render: (_, item, index) => <Input type="date" value={String(item.start ?? '')} onChange={(event) => update(setPeriods, periods, index, 'start', event.target.value)} /> },
    { title: '结束日期', dataIndex: 'end', width: 150, render: (_, item, index) => <Input type="date" value={String(item.end ?? '')} onChange={(event) => update(setPeriods, periods, index, 'end', event.target.value)} /> },
    { title: '官方原文依据', dataIndex: 'evidence_quote', render: (_, item, index) => <Input.TextArea rows={2} value={String(item.evidence_quote ?? '')} onChange={(event) => update(setPeriods, periods, index, 'evidence_quote', event.target.value)} /> },
    { title: '操作', width: 64, align: 'center', render: (_, __, index) => <Tooltip title="删除这一条"><Button type="text" danger icon={<DeleteOutlined />} aria-label="删除节假日段" onClick={() => setPeriods(periods.filter((_, itemIndex) => itemIndex !== index))} /></Tooltip> },
  ]
  const workdayColumns: TableColumnsType<Record<string, unknown>> = [
    { title: '调休上班日期', dataIndex: 'date', width: 170, render: (_, item, index) => <Input type="date" value={String(item.date ?? '')} onChange={(event) => update(setWorkdays, workdays, index, 'date', event.target.value)} /> },
    { title: '对应节日', dataIndex: 'holiday_name', width: 140, render: (_, item, index) => <Input value={String(item.holiday_name ?? '')} onChange={(event) => update(setWorkdays, workdays, index, 'holiday_name', event.target.value)} /> },
    { title: '官方原文依据', dataIndex: 'evidence_quote', render: (_, item, index) => <Input.TextArea rows={2} value={String(item.evidence_quote ?? '')} onChange={(event) => update(setWorkdays, workdays, index, 'evidence_quote', event.target.value)} /> },
    { title: '操作', width: 64, align: 'center', render: (_, __, index) => <Tooltip title="删除这一条"><Button type="text" danger icon={<DeleteOutlined />} aria-label="删除调休上班日" onClick={() => setWorkdays(workdays.filter((_, itemIndex) => itemIndex !== index))} /></Tooltip> },
  ]
  const publish = async () => {
    setPublishing(true)
    const withoutRowKeys = (rows: Array<Record<string, unknown>>) => rows.map(({ _row_key: _, ...item }) => item)
    try { await onPublish(withoutRowKeys(periods), withoutRowKeys(workdays)) } finally { setPublishing(false) }
  }
  return <Space orientation="vertical" size="large" style={{ width: '100%' }}>
    <Alert showIcon type={hasData ? 'info' : 'warning'} title={hasData ? '请核对 AI 提取结果，必要时可直接调整' : '该任务没有保存预览明细'} description={hasData ? '确认后，系统会重新校验年份、日期范围、重复冲突、七类法定节日和官方依据；全部通过才会直接生成新的已发布版本。' : '这条任务可能由旧版本 Worker 执行，无法回放本轮数据。请重新创建预览任务。'} />
    <div><Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 12 }}><Typography.Title level={5} style={{ margin: 0 }}>法定节假日</Typography.Title><Button icon={<PlusOutlined />} onClick={() => setPeriods([...periods, { _row_key: crypto.randomUUID(), name: '', start: `${job.year}-01-01`, end: `${job.year}-01-01`, evidence_quote: '' }])}>新增节假日</Button></Space><Table size="small" pagination={false} rowKey={(item) => String(item._row_key)} dataSource={periods} columns={periodColumns} locale={{ emptyText: '暂无节假日段' }} scroll={{ x: 900 }} /></div>
    <div><Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 12 }}><Typography.Title level={5} style={{ margin: 0 }}>调休上班日期</Typography.Title><Button icon={<PlusOutlined />} onClick={() => setWorkdays([...workdays, { _row_key: crypto.randomUUID(), date: `${job.year}-01-01`, holiday_name: '', evidence_quote: '' }])}>新增调休日期</Button></Space><Table size="small" pagination={false} rowKey={(item) => String(item._row_key)} dataSource={workdays} columns={workdayColumns} locale={{ emptyText: '无调休上班日' }} scroll={{ x: 760 }} /></div>
    <Space style={{ width: '100%', justifyContent: 'flex-end' }}><Button type="primary" icon={<SyncOutlined />} loading={publishing} disabled={!hasData} onClick={() => void publish()}>确认内容并入库发布</Button></Space>
  </Space>
}

function jobDetailItems(job: HolidayCalendarSyncJob) {
  const status = statusLabels[job.status] ?? { label: '未知状态', color: 'default' }
  return [
    { key: 'year', label: '年度', children: job.year },
    { key: 'mode', label: '执行方式', children: job.mode === 'preview' ? '仅预览' : '同步并发布' },
    { key: 'status', label: '当前状态', children: <Tag color={status.color}>{status.label}</Tag> },
    { key: 'result', label: '结果说明', children: jobResultText(job) },
    { key: 'source', label: '官方公告', children: job.source_url ? <a href={job.source_url} target="_blank" rel="noreferrer">{job.source_title || '查看中国政府网公告'}</a> : '尚未发现公告' },
    { key: 'attempt', label: '执行次数', children: job.attempt_count },
    { key: 'created', label: '创建时间', children: new Date(job.created_at).toLocaleString('zh-CN') },
    ...(job.next_retry_at ? [{ key: 'retry', label: '预计重试时间', children: new Date(job.next_retry_at).toLocaleString('zh-CN') }] : []),
  ]
}
