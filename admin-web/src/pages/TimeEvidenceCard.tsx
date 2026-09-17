import { EditOutlined, PlusOutlined, ExclamationCircleFilled } from '@ant-design/icons'
import { Alert, Button, Card, Checkbox, Collapse, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Table, Tag, Tooltip, Typography } from 'antd'
import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { adminErrorMessage } from '../api/errorMessages'
import { createOperationIntent } from '../api/adminApi'
import type { HolidayCalendar, PlaceClosureEvidence, PlaceClosureInput, PlaceDateExceptionEvidence, PlaceDateExceptionInput, PlaceRevision, PlaceRevisionEvidence, PlaceTimePreview, PlaceTimeRuleEvidence, PlaceTimeRuleInput, SourceChannel } from '../api/types'
import { useAdminSession } from '../auth/AdminSessionProvider'
import { dateExceptionKindLabel, reasonCodeLabel, reviewStatusLabel, sourceDecisionLabel, timeRuleKindLabel } from '../ui/displayLabels'
import { SourceRecordField, TimeField, FieldLabel } from './revisionDetailFields'
import { isFormValidationError, sourceLabelById, formatDateTime, reviewStatusColor } from './revisionDetailDisplay'

export function TimeEvidenceCard({
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
        operation_intent_id: createOperationIntent('holiday-exceptions'),
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
        operation_intent_id: createOperationIntent('time-evidence'),
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
        operation_intent_id: createOperationIntent('time-evidence-review'),
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
        operation_intent_id: createOperationIntent('time-evidence-retire'),
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
        operation_intent_id: createOperationIntent('time-rule-delete'),
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
            title={evidence?.time_rules.some((item) => item.active) ? '演出地点需核验固定场次' : '演出地点必须使用固定场次规则'}
            description={evidence?.time_rules.some((item) => item.active)
              ? '当前已有固定场次记录；请逐条核对其来源和时间，确认最晚入场早于结束时间后再送审。'
              : '开放时间只能说明可营业时段；演出、灯光秀等地点需要新增明确开始和结束时间的“固定场次”规则。'}
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



