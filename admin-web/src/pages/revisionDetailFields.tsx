import { ExclamationCircleFilled } from '@ant-design/icons'
import { Tooltip } from 'antd'

export function FieldLabel({ label, hint }: { label: string; hint: string }) {
  return <span>{label} <Tooltip title={hint}><ExclamationCircleFilled style={{ color: '#d89614', cursor: 'help' }} aria-label={`${label}填写提示`} /></Tooltip></span>
}

