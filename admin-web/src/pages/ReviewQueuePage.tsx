import { ReloadOutlined } from '@ant-design/icons'
import { Button, Card, Descriptions, Select, Space, Table, Tag, Typography, message } from 'antd'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { adminErrorMessage } from '../api/errorMessages'
import type { ReviewDecision, ReviewTask, ReviewTaskStatus } from '../api/types'
import { useAdminSession } from '../auth/AdminSessionProvider'
import { ErrorNotice } from '../components/ErrorNotice'

const PAGE_SIZE = 50
const statusLabels: Record<ReviewTaskStatus, string> = {
  draft: '草稿',
  ready_for_review: '待审核',
  in_review: '审核中',
  changes_requested: '待修改',
  approved: '已通过',
  closed: '已关闭',
}

export function ReviewQueuePage() {
  const { api } = useAdminSession()
  const [status, setStatus] = useState<ReviewTaskStatus | undefined>('ready_for_review')
  const [tasks, setTasks] = useState<ReviewTask[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.listReviewTasks(status, PAGE_SIZE)
      setTasks(result.items)
    } catch (reason) {
      setError(adminErrorMessage(reason))
    } finally {
      setLoading(false)
    }
  }, [api, status])

  useEffect(() => {
    void load()
  }, [load])

  const columns = useMemo(
    () => [
      {
        title: '状态',
        dataIndex: 'status',
        width: 120,
        render: (value: ReviewTaskStatus) => (
          <Tag color={value === 'approved' ? 'success' : value === 'changes_requested' ? 'warning' : 'processing'}>
            {statusLabels[value]}
          </Tag>
        ),
      },
      { title: '审核任务', dataIndex: 'review_task_id', width: 230, ellipsis: true },
      { title: 'Revision', dataIndex: 'place_revision_id', width: 230, ellipsis: true },
      { title: '版本', dataIndex: 'version', width: 80 },
      { title: '更新时间', dataIndex: 'updated_at', width: 210, render: formatDateTime },
    ],
    [],
  )

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div className="page-heading-row">
        <div>
          <Typography.Title level={2}>地点审核工作台</Typography.Title>
          <Typography.Paragraph type="secondary">
            O01 / O08：查看审核任务和追加式决定历史。审核操作由服务端权限和版本校验决定。
          </Typography.Paragraph>
        </div>
        <Space>
          <Select<ReviewTaskStatus | undefined>
            value={status}
            allowClear
            placeholder="全部状态"
            style={{ width: 150 }}
            options={Object.entries(statusLabels).map(([value, label]) => ({ value, label }))}
            onChange={setStatus}
          />
          <Button icon={<ReloadOutlined />} onClick={() => void load()} loading={loading}>
            刷新
          </Button>
        </Space>
      </div>
      {error !== null && <ErrorNotice message={error} onClose={() => setError(null)} />}
      <Card>
        <Table<ReviewTask>
          rowKey="review_task_id"
          columns={columns}
          dataSource={tasks}
          loading={loading}
          pagination={false}
          scroll={{ x: 900 }}
          expandable={{
            expandedRowRender: (task) => (
              <ReviewTaskDetails task={task} api={api} onChanged={load} />
            ),
          }}
          locale={{ emptyText: '当前状态下没有审核任务' }}
        />
      </Card>
    </Space>
  )
}

function ReviewTaskDetails({
  task,
  api,
  onChanged,
}: {
  task: ReviewTask
  api: ReturnType<typeof useAdminSession>['api']
  onChanged: () => Promise<void>
}) {
  const [decisions, setDecisions] = useState<ReviewDecision[]>([])
  const [working, setWorking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const canDecide = ['ready_for_review', 'in_review', 'changes_requested'].includes(task.status)

  useEffect(() => {
    void api
      .listReviewDecisions(task.review_task_id)
      .then((result) => setDecisions(result.items))
      .catch((reason) => setError(adminErrorMessage(reason)))
  }, [api, task.review_task_id])

  const decide = async (decisionKind: ReviewDecision['decision_kind']) => {
    setWorking(true)
    setError(null)
    try {
      await api.decidePlaceReview(task.review_task_id, {
        expected_version: task.version,
        decision_kind: decisionKind,
        reason_code:
          decisionKind === 'approve'
            ? 'OM1_FACTS_VERIFIED'
            : decisionKind === 'request_changes'
              ? 'OM1_REVIEW_CHANGES'
              : 'OM1_REVIEW_CANCELLED',
      })
      message.success('审核操作已提交')
      await onChanged()
    } catch (reason) {
      setError(adminErrorMessage(reason))
    } finally {
      setWorking(false)
    }
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Descriptions bordered size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
        <Descriptions.Item label="创建人">{task.created_by}</Descriptions.Item>
        <Descriptions.Item label="Revision">{task.place_revision_id}</Descriptions.Item>
        <Descriptions.Item label="版本">{task.version}</Descriptions.Item>
      </Descriptions>
      {error !== null && <ErrorNotice message={error} onClose={() => setError(null)} />}
      {canDecide && (
        <Space wrap>
          <Button type="primary" loading={working} onClick={() => void decide('approve')}>
            通过
          </Button>
          <Button loading={working} onClick={() => void decide('request_changes')}>
            退回修改
          </Button>
          <Button danger loading={working} onClick={() => void decide('cancel')}>
            关闭任务
          </Button>
        </Space>
      )}
      <Typography.Text strong>决定历史</Typography.Text>
      <Table<ReviewDecision>
        rowKey="review_decision_id"
        size="small"
        pagination={false}
        dataSource={decisions}
        columns={[
          { title: '决定', dataIndex: 'decision_kind' },
          { title: '角色', dataIndex: 'actor_role' },
          { title: '理由', dataIndex: 'reason_code' },
          { title: '时间', dataIndex: 'created_at', render: formatDateTime },
        ]}
      />
    </Space>
  )
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'medium',
    hour12: false,
  }).format(new Date(value))
}
