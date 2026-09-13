import { Alert, Button, Card, Modal, Space, Table, Tag, Typography } from 'antd'
import type { PlaceRevision, PlaceRevisionEvidence, SourceConflict } from '../api/types'
import { sourceDecisionLabel, reviewStatusLabel } from '../ui/displayLabels'
import { formatDateTime } from './revisionDetailDisplay'

export function SourceConflictCard({
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

export function VerificationSummaryCard({ evidence, revision }: { evidence: PlaceRevisionEvidence | null; revision: PlaceRevision }) {
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


