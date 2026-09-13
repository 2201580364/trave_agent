import { CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Collapse, Space, Tag, Typography } from 'antd'
import type { PublicationCheck } from '../api/types'
import { reasonCodeLabel } from '../ui/displayLabels'
import type { PublicationBlocker } from './publicationBlockers'

export function RevisionPublicationReadiness({ blockers, publicationCheck, publicationCheckError }: { blockers: PublicationBlocker[]; publicationCheck: PublicationCheck | null; publicationCheckError: string | null }) {
  return (
  <Card title="发布准备" className="publication-readiness-card">
    {blockers.length === 0 ? (
      <Alert showIcon type="success" icon={<CheckCircleOutlined />} title={publicationCheck?.publishable === false ? '当前仍有发布门禁原因，请查看下方明细' : '当前修订版本没有识别出的阻断项'} />
    ) : (
      <Space orientation="vertical" style={{ width: '100%' }}>
        <Alert showIcon type="warning" title={`当前有 ${blockers.length} 项需要处理`} />
        {blockers.slice(0, 3).map((blocker) => (
          <div key={blocker.code} className="publication-blocker-item">
    <Space orientation="vertical" size={4} style={{ width: '100%' }}>
      <Typography.Text strong><CloseCircleOutlined style={{ color: '#cf1322' }} /> {blocker.title}</Typography.Text>
      <Typography.Text type="secondary">{blocker.description}</Typography.Text>
      {blocker.actionLabel && blocker.target && <Button size="small" type="link" onClick={() => document.getElementById(blocker.target!)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>{blocker.actionLabel}</Button>}
    </Space>
          </div>
        ))}
        {blockers.length > 3 && <Collapse ghost items={[{
          key: 'remaining-blockers',
          label: `展开其余 ${blockers.length - 3} 项`,
          children: <Space orientation="vertical" style={{ width: '100%' }}>{blockers.slice(3).map((blocker) => (
    <div key={blocker.code} className="publication-blocker-item">
      <Space orientation="vertical" size={4} style={{ width: '100%' }}>
        <Typography.Text strong><CloseCircleOutlined style={{ color: '#cf1322' }} /> {blocker.title}</Typography.Text>
        <Typography.Text type="secondary">{blocker.description}</Typography.Text>
        {blocker.actionLabel && blocker.target && <Button size="small" type="link" onClick={() => document.getElementById(blocker.target!)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>{blocker.actionLabel}</Button>}
      </Space>
    </div>
          ))}</Space>,
        }]} />}
    </Space>
    )}
    {publicationCheckError && <Alert showIcon type="info" title="发布门禁暂时无法读取" description={publicationCheckError} />}
    {publicationCheck && publicationCheck.reason_codes.length > 0 && (
      <Alert
        showIcon
        type="warning"
        title="发布门禁检查结果"
        description={<Space wrap>{publicationCheck.reason_codes.map((code) => <Tag key={code} color="warning">{reasonCodeLabel(code)}</Tag>)}</Space>}
        style={{ marginTop: 12 }}
      />
    )}
    <Typography.Paragraph type="secondary" style={{ marginTop: 16, marginBottom: 0 }}>
      每个阻断项都对应一个证据区域。数据编辑员处理证据或来源冲突后需要重新送审；审核员完成逐项核验并通过修订版本审核；发布员再准备求解投影、通过发布门禁并发布新快照。
    </Typography.Paragraph>
  </Card>
  )
}
