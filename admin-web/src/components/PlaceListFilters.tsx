import { SearchOutlined } from '@ant-design/icons'
import { Button, Form, Input, Select, Space } from 'antd'
import { useEffect } from 'react'

import type { PlaceListFilters as PlaceListFilterValues } from '../api/types'
import { placeKindLabel } from '../ui/displayLabels'

const PLACE_KIND_OPTIONS = [
  'attraction',
  'scenic_area',
  'neighborhood',
  'walking_route',
  'market',
  'show',
  'experience',
].map((value) => ({ value, label: placeKindLabel(value) }))

export function PlaceListFilters({
  value,
  loading,
  onSearch,
  onReset,
}: {
  value: PlaceListFilterValues
  loading?: boolean
  onSearch: (value: PlaceListFilterValues) => void
  onReset: () => void
}) {
  const [form] = Form.useForm<PlaceListFilterValues>()

  useEffect(() => {
    form.setFieldsValue(value)
  }, [form, value])

  return (
    <Form<PlaceListFilterValues>
      form={form}
      layout="inline"
      onFinish={(fields) =>
        onSearch({
          keyword: fields.keyword?.trim() || undefined,
          admin_area: fields.admin_area?.trim() || undefined,
          place_kind: fields.place_kind || undefined,
        })
      }
    >
      <Form.Item name="keyword" label="关键字">
        <Input allowClear placeholder="地点名称、地址、分类" style={{ width: 230 }} />
      </Form.Item>
      <Form.Item name="admin_area" label="区域">
        <Input allowClear placeholder="例如：西湖区" style={{ width: 150 }} />
      </Form.Item>
      <Form.Item name="place_kind" label="地点类型">
        <Select allowClear placeholder="全部类型" options={PLACE_KIND_OPTIONS} style={{ width: 160 }} />
      </Form.Item>
      <Form.Item>
        <Space>
          <Button type="primary" htmlType="submit" icon={<SearchOutlined />} loading={loading}>
            查询
          </Button>
          <Button
            onClick={() => {
              form.resetFields()
              onReset()
            }}
          >
            清空
          </Button>
        </Space>
      </Form.Item>
    </Form>
  )
}
