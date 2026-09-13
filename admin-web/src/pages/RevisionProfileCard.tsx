import { Card, Collapse, Descriptions } from 'antd'
import type { PlaceRevision } from '../api/types'
import { formatDateTime, formatOptionalDateTime } from './revisionDetailDisplay'
import { geometryKindLabel, indoorOutdoorLabel, rainSuitabilityLabel, reviewFlagLabel } from '../ui/displayLabels'

export function RevisionProfileCard({ revision }: { revision: PlaceRevision }) {
  return (
    <Card title="地点资料" className="revision-profile-card">
      <div id="revision-basic-facts" />
      <Descriptions size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
        <Descriptions.Item label="别名">{revision.aliases.join('、') || '未提供'}</Descriptions.Item>
        <Descriptions.Item label="地址">{revision.address ?? '未提供'}</Descriptions.Item>
        <Descriptions.Item label="地图表达">{geometryKindLabel(revision.geometry_kind)}</Descriptions.Item>
        <Descriptions.Item label="建议游览时长">{revision.review_flags.includes('DURATION_NOT_COLLECTED') ? '未采集' : `${revision.duration_min}–${revision.duration_max} 分钟，建议 ${revision.duration_recommended} 分钟`}</Descriptions.Item>
        <Descriptions.Item label="室内/室外">{indoorOutdoorLabel(revision.indoor_outdoor)}</Descriptions.Item>
        <Descriptions.Item label="全天开放">{revision.is_always_open ? '是' : '否'}</Descriptions.Item>
      </Descriptions>
      <Collapse ghost className="revision-technical-collapse" items={[{ key: 'more', label: '查看更多体验与技术信息', children: <Descriptions size="small" column={{ xs: 1, sm: 2, lg: 3 }}>
        <Descriptions.Item label="内部移动">{revision.internal_travel_min} 分钟</Descriptions.Item>
        <Descriptions.Item label="体力等级">{revision.energy_level} / 5</Descriptions.Item>
        <Descriptions.Item label="适用时段">{revision.suitable_periods.map((value) => ({ morning: '上午', afternoon: '下午', evening: '晚上' }[value] ?? '其他')).join('、') || '未提供'}</Descriptions.Item>
        <Descriptions.Item label="适合人群">{revision.audience_tags.join('、') || '未提供'}</Descriptions.Item>
        <Descriptions.Item label="雨天适配">{rainSuitabilityLabel(revision.rain_suitability)}</Descriptions.Item>
        <Descriptions.Item label="来源记录">{revision.source_record_ids.length} 条</Descriptions.Item>
        <Descriptions.Item label="创建时间">{formatDateTime(revision.created_at)}</Descriptions.Item>
        <Descriptions.Item label="人工核验时间">{formatOptionalDateTime(revision.reviewed_at)}</Descriptions.Item>
        <Descriptions.Item label="发布时间">{formatOptionalDateTime(revision.published_at)}</Descriptions.Item>
        <Descriptions.Item label="修订版本编号">{revision.place_revision_id}</Descriptions.Item>
        <Descriptions.Item label="地点编号">{revision.place_id}</Descriptions.Item>
        <Descriptions.Item label="待核验提示">{revision.review_flags.length ? revision.review_flags.map(reviewFlagLabel).join('、') : '无'}</Descriptions.Item>
      </Descriptions> }]} />
    </Card>
  )
}
