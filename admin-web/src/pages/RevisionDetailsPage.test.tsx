import { render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'

import type { PlaceRevision, PlaceRevisionEvidence, ReviewTask } from '../api/types'
import { RevisionDetailsPage } from './RevisionDetailsPage'

const mocks = vi.hoisted(() => ({
  api: {
    getPlaceRevision: vi.fn(),
    getPlaceRevisionEvidence: vi.fn(),
    getReviewTask: vi.fn(),
    listSourceConflicts: vi.fn(),
    checkPlaceRevisionPublication: vi.fn(),
  },
  permissions: new Set<string>(),
  navigate: vi.fn(),
  location: { search: '' },
}))

vi.mock('../auth/AdminSessionProvider', () => ({
  useAdminSession: () => ({
    api: mocks.api,
    hasPermission: (permission: string) => mocks.permissions.has(permission),
  }),
}))

vi.mock('react-router-dom', () => ({
  useNavigate: () => mocks.navigate,
  useParams: () => ({ revisionId: 'revision-1' }),
  useLocation: () => mocks.location,
}))

const revision: PlaceRevision = {
  place_revision_id: 'revision-1',
  place_id: 'place-1',
  revision_number: 1,
  revision_version: 1,
  lifecycle_status: 'candidate',
  canonical_name: '西湖',
  aliases: [],
  place_kind: 'attraction',
  category: '自然景观',
  admin_area: '杭州',
  address: null,
  geometry_kind: 'point',
  duration_min: 60,
  duration_recommended: 90,
  duration_max: 180,
  internal_travel_min: 10,
  energy_level: 2,
  indoor_outdoor: 'outdoor',
  suitable_periods: ['morning'],
  audience_tags: [],
  rain_suitability: 'poor',
  is_always_open: false,
  solver_eligible: true,
  conflicts_resolved: true,
  source_record_ids: ['source-1'],
  created_at: '2026-08-30T00:00:00Z',
  reviewed_at: null,
  published_at: null,
  review_flags: [],
}

const timeEvidence: PlaceRevisionEvidence = {
  revision,
  sources: [{
    source_record_id: 'source-1',
    source_id: 'official-site',
    source_url: 'https://example.test/opening-hours',
    source_url_redacted: false,
    collection_mode: 'manual',
    target_stage: 'candidate',
    source_decision: 'approved',
    observed_at: '2026-08-30T00:00:00Z',
    status: 'active',
  }],
  geometries: [],
  access_points: [],
  time_rules: [{
    time_rule_id: 'time-rule-1',
    rule_kind: 'fixed_session',
    weekdays: [5, 6],
    start_minute: 1410,
    end_minute: 1470,
    last_entry_minute: 1400,
    valid_from: null,
    valid_to: null,
    source_record_id: 'source-1',
    source_record_valid: true,
    review_status: 'human_verified',
    active: true,
    created_at: '2026-08-30T00:00:00Z',
    reviewed_at: '2026-08-30T01:00:00Z',
  }],
  closures: [{
    closure_id: 'closure-1',
    weekday: 1,
    source_record_id: 'source-1',
    source_record_valid: true,
    review_status: 'candidate',
    active: true,
    created_at: '2026-08-30T00:00:00Z',
    reviewed_at: null,
  }],
  date_exceptions: [{
    date_exception_id: 'date-exception-1',
    service_date: '2026-10-01',
    exception_kind: 'session_override',
    start_minute: 1500,
    end_minute: 1560,
    last_entry_minute: null,
    source_record_id: 'source-1',
    source_record_valid: false,
    review_status: 'rejected',
    active: false,
    created_at: '2026-08-30T00:00:00Z',
    reviewed_at: null,
  }],
  projection: null,
  missing_source_record_ids: [],
}

describe('RevisionDetailsPage', () => {
  const openReviewTask: ReviewTask = {
    review_task_id: 'task-1',
    place_revision_id: 'revision-1',
    status: 'ready_for_review',
    assigned_reviewer_id: null,
    version: 1,
    created_by: 'editor-1',
    created_at: '2026-08-30T00:00:00Z',
    updated_at: '2026-08-30T00:00:00Z',
  }

  beforeEach(() => {
    vi.clearAllMocks()
    mocks.api.listSourceConflicts.mockResolvedValue({ revision_id: 'revision-1', items: [] })
    mocks.api.checkPlaceRevisionPublication.mockResolvedValue({ revision_id: 'revision-1', publishable: true, reason_codes: [] })
    mocks.permissions.clear()
    mocks.location.search = ''
    vi.stubGlobal('ResizeObserver', class {
      observe() {}
      unobserve() {}
      disconnect() {}
    })
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
  })

  it('keeps the O03 revision details visible when the O04 evidence request fails', async () => {
    mocks.api.getPlaceRevision.mockResolvedValueOnce(revision)
    mocks.api.getPlaceRevisionEvidence.mockRejectedValueOnce(new Error('evidence endpoint unavailable'))

    render(<RevisionDetailsPage />)

    await waitFor(() => expect(screen.getAllByText('西湖').length).toBeGreaterThan(0))

    expect(screen.getByText('基础事实')).toBeTruthy()
    expect(screen.getByText('O04 证据暂不可用')).toBeTruthy()
    expect(screen.getByText('O05 时间证据暂不可用')).toBeTruthy()
    expect(screen.getAllByText('管理服务暂时不可用，请稍后重试。')).toHaveLength(2)
  })

  it('renders revision-scoped O05 time evidence and keeps cross-midnight offsets visible', async () => {
    mocks.api.getPlaceRevision.mockResolvedValueOnce(revision)
    mocks.api.getPlaceRevisionEvidence.mockResolvedValueOnce(timeEvidence)

    render(<RevisionDetailsPage />)

    await waitFor(() => expect(screen.getByText('开放时间与固定场次（O05）')).toBeTruthy())

    expect(screen.getByText('固定场次')).toBeTruthy()
    expect(screen.getByText('23:30 – 次日 00:30 (+1440)')).toBeTruthy()
    expect(screen.getByText('周一')).toBeTruthy()
    expect(screen.getByText('场次覆盖')).toBeTruthy()
    expect(screen.getByText('次日 01:00 (+1440) – 次日 02:00 (+1440)')).toBeTruthy()
    expect(screen.getAllByText('无效').length).toBeGreaterThan(0)
    expect(screen.getAllByText('已停用').length).toBeGreaterThan(0)
  })

  it('shows O05 edit and reviewer actions only when the administrator has permissions', async () => {
    mocks.permissions.add('place:candidate:write')
    mocks.permissions.add('place:review:decide')
    mocks.location.search = '?from=review&task=task-1'
    mocks.api.getPlaceRevision.mockResolvedValueOnce(revision)
    mocks.api.getPlaceRevisionEvidence.mockResolvedValueOnce(timeEvidence)
    mocks.api.getReviewTask.mockResolvedValueOnce(openReviewTask)

    render(<RevisionDetailsPage />)

    await waitFor(() => expect(screen.getByText('开放时间与固定场次（O05）')).toBeTruthy())

    expect(screen.getAllByText('新增')).toHaveLength(5)
    const buttonLabels = [...document.querySelectorAll('button')]
      .map((button) => button.textContent?.replace(/\s/g, ''))
    expect(buttonLabels.filter((label) => label === '通过')).toHaveLength(2)
    expect(buttonLabels.filter((label) => label === '驳回')).toHaveLength(2)
    expect(screen.getByText('审核通过')).toBeTruthy()
    expect(screen.getByText('退回修改')).toBeTruthy()
    expect(screen.getByText('返回地点审核')).toBeTruthy()
    expect(screen.queryByText('编辑候选')).toBeNull()
    expect(screen.queryByText('送审')).toBeNull()
  })

  it('hides reviewer actions and keeps the candidate return path outside review context', async () => {
    mocks.permissions.add('place:candidate:write')
    mocks.permissions.add('place:review:decide')
    mocks.api.getPlaceRevision.mockResolvedValueOnce(revision)
    mocks.api.getPlaceRevisionEvidence.mockResolvedValueOnce(timeEvidence)

    render(<RevisionDetailsPage />)

    await waitFor(() => expect(screen.getByText('开放时间与固定场次（O05）')).toBeTruthy())

    expect(screen.getByText('返回候选地点')).toBeTruthy()
    expect(screen.getByText('编辑候选')).toBeTruthy()
    expect(screen.queryByText('审核通过')).toBeNull()
    expect(screen.queryByText('退回修改')).toBeNull()
    expect(screen.queryByText('关闭任务')).toBeNull()
    expect(screen.queryAllByText('通过')).toHaveLength(0)
    expect(mocks.api.getReviewTask).not.toHaveBeenCalled()
  })

  it('explains source conflicts and solver prerequisites with actionable locations', async () => {
    const blockedRevision = { ...revision, solver_eligible: false, conflicts_resolved: false }
    mocks.api.getPlaceRevision.mockResolvedValueOnce(blockedRevision)
    mocks.api.getPlaceRevisionEvidence.mockResolvedValueOnce({ ...timeEvidence, geometries: [], access_points: [], time_rules: [] })
    mocks.api.listSourceConflicts.mockResolvedValueOnce({
      revision_id: 'revision-1',
      items: [{ source_id: 'official-site', resolved: false, records: [{ source_record_id: 'source-1', source_url: 'https://example.test', source_decision: 'pending', status: 'active', observed_at: '2026-08-30T00:00:00Z' }, { source_record_id: 'source-2', source_url: 'https://example.test/old', source_decision: 'rejected', status: 'active', observed_at: '2026-08-29T00:00:00Z' }] }],
    })
    mocks.api.checkPlaceRevisionPublication.mockResolvedValueOnce({ revision_id: 'revision-1', publishable: false, reason_codes: ['MISSING_VERIFIED_GEOMETRY', 'SOURCE_CONFLICT_UNRESOLVED'] })

    render(<RevisionDetailsPage />)

    await waitFor(() => expect(screen.getByText('来源冲突与裁决（O06）')).toBeTruthy())
    expect(screen.getByText('检测到 1 组来源冲突')).toBeTruthy()
    expect(screen.getByText('存在未完成裁决的来源冲突')).toBeTruthy()
    expect(screen.getByText('缺少已核验的地点几何')).toBeTruthy()
    expect(screen.getByText('查看来源冲突（O06）')).toBeTruthy()
    expect(screen.getAllByText('查看地图与访问点（O04）').length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: '开放时间（O05）：0/1 已核验' })).toBeTruthy()
  })

  it('does not claim ordinary opening hours exist when a show has no time rules', async () => {
    const showRevision = { ...revision, place_kind: 'show' }
    mocks.api.getPlaceRevision.mockResolvedValueOnce(showRevision)
    mocks.api.getPlaceRevisionEvidence.mockResolvedValueOnce({
      ...timeEvidence,
      revision: showRevision,
      time_rules: [],
    })
    mocks.api.checkPlaceRevisionPublication.mockResolvedValueOnce({
      revision_id: 'revision-1',
      publishable: false,
      reason_codes: ['FIXED_SESSION_REQUIRED'],
    })

    render(<RevisionDetailsPage />)

    await waitFor(() => expect(screen.getByText('演出地点需要固定场次规则')).toBeTruthy())
    expect(screen.getByText(/无论当前是否已有普通开放时间/)).toBeTruthy()
    expect(screen.queryByText(/当前已有开放时间记录/)).toBeNull()
  })
})
