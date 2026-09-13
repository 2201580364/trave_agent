import { ExclamationCircleFilled } from '@ant-design/icons'
import { Tooltip } from 'antd'

export function FieldLabel({ label, hint }: { label: string; hint: string }) {
  return <span>{label} <Tooltip title={hint}><ExclamationCircleFilled style={{ color: '#d89614', cursor: 'help' }} aria-label={`${label}填写提示`} /></Tooltip></span>
}


import { Checkbox, Form, Input, Select, Space, Typography } from 'antd'
import type { PlaceRevisionEvidence, SourceChannel } from '../api/types'
import { sourceRecordBusinessLabel } from './revisionDetailDisplay'

export function TimeField({ name, nextDayName, label, hint, required = false }: { name: string; nextDayName: string; label: string; hint: string; required?: boolean }) {
  return <Form.Item label={<FieldLabel label={label} hint={hint} />}><Space.Compact block><Form.Item name={name} noStyle rules={[{ required, message: `请填写${label}` }, { pattern: /^$|^\d{2}:\d{2}$/, message: '请填写 HH:mm 格式，例如 09:30' }]}><Input type="time" step={60} style={{ width: '100%' }} aria-label={label} /></Form.Item><Form.Item name={nextDayName} valuePropName="checked" noStyle><Checkbox style={{ padding: '0 10px', whiteSpace: 'nowrap' }}>次日</Checkbox></Form.Item></Space.Compact></Form.Item>
}
export function SourceRecordField({ sources = [], sourceChannels, required = true, extraOption }: { sources?: PlaceRevisionEvidence['sources']; sourceChannels: SourceChannel[]; required?: boolean; extraOption?: { value: string; label: string } }) {
  const options = [...sources.map((source) => ({ value: source.source_record_id, label: sourceRecordBusinessLabel(source, sourceChannels) })), ...(extraOption ? [extraOption] : [])]
  return <Form.Item name="source_record_id" label={<FieldLabel label="来源记录" hint="普通证据选择当前地点的有效来源；按法定节假日历生成时，可直接使用该年度日历的官方来源。" />} rules={required ? [{ required: true }] : []}><Select showSearch optionFilterProp="label" options={options} placeholder={extraOption ? '可选择地点来源，也可使用法定节假日历官方来源' : '选择当前地点的有效来源'} /></Form.Item>
}
