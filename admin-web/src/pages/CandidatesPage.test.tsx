import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'

import type { PlaceRevision } from '../api/types'
import { CandidatesPage } from './CandidatesPage'

const mocks = vi.hoisted(() => ({
  api: { listCandidates: vi.fn() },
  navigate: vi.fn(),
}))

vi.mock('../auth/AdminSessionProvider', () => ({
  useAdminSession: () => ({ api: mocks.api }),
}))

vi.mock('react-router-dom', () => ({
  useNavigate: () => mocks.navigate,
}))

const revision: PlaceRevision = {
  place_revision_id: 'revision-1', place_id: 'place-1', revision_number: 1, revision_version: 1,
  lifecycle_status: 'candidate', canonical_name: '西湖', aliases: [], place_kind: 'scenic_area',
  category: '自然景观', admin_area: '西湖区', address: '杭州市西湖区', geometry_kind: 'area',
  duration_min: 1, duration_recommended: 1, duration_max: 1, internal_travel_min: 0,
  energy_level: 3, indoor_outdoor: 'outdoor', suitable_periods: ['morning'], audience_tags: [],
  rain_suitability: 'conditional', is_always_open: false, solver_eligible: false,
  conflicts_resolved: false, source_record_ids: ['source-1'], created_at: '2026-09-01T00:00:00Z',
  reviewed_at: null, published_at: null,
  review_flags: [
    'DURATION_NOT_COLLECTED',
    'ACCESS_POINT_UNVERIFIED',
    'TIME_RULES_NOT_COLLECTED',
    'FIXED_TIME_OR_OPERATING_RULE_REQUIRED',
  ],
  relation_review_status: 'pending',
  review_readiness: {
    status: 'needs_evidence', completed_checks: 3, verified_checks: 1, total_checks: 6,
    missing_checks: ['basic', 'access_point', 'time'], pending_review_checks: ['geometry', 'relation'],
    task_status: null,
    checks: [
      { key: 'basic', collected: false, verified: false, total: 1, verified_count: 0 },
      { key: 'source', collected: true, verified: true, total: 1, verified_count: 1 },
      { key: 'geometry', collected: true, verified: false, total: 1, verified_count: 0 },
      { key: 'access_point', collected: false, verified: false, total: 0, verified_count: 0 },
      { key: 'time', collected: false, verified: false, total: 0, verified_count: 0 },
      { key: 'relation', collected: true, verified: false, total: 1, verified_count: 0 },
    ],
  },
}

describe('CandidatesPage review readiness', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.api.listCandidates.mockResolvedValue({ items: [revision], total: 1, limit: 20, offset: 0 })
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false, media: query, onchange: null,
        addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(),
        removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
      })),
    })
  })

  it('shows batch readiness and the six business checks without exposing technical codes', async () => {
    render(<CandidatesPage />)

    await waitFor(() => expect(screen.getByText('西湖')).toBeTruthy())
    expect(screen.getByText(/待补录 1 条，可送审 0 条/)).toBeTruthy()
    expect(screen.getByText('待补录')).toBeTruthy()
    expect(screen.getByText('3/6 项已准备')).toBeTruthy()
    expect(screen.getByText('未采集')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Expand row' }))
    expect(screen.getByText('基础事实：待补录')).toBeTruthy()
    expect(screen.getByText('来源与冲突：已核验')).toBeTruthy()
    expect(screen.getByText('来源与冲突', { exact: true })).toBeTruthy()
    expect(screen.queryByText('冲突已裁决')).toBeNull()
    expect(screen.getByText('地点几何：待审核')).toBeTruthy()
    expect(screen.getByText('访问点：待补录')).toBeTruthy()
    expect(screen.getByText('开放时间：待补录')).toBeTruthy()
    expect(screen.getByText('关系检查：待审核')).toBeTruthy()
    expect(screen.getByText('需要补充固定场次或营业时间')).toBeTruthy()
    expect(screen.queryByText('DURATION_NOT_COLLECTED')).toBeNull()
    expect(screen.queryByText('FIXED_TIME_OR_OPERATING_RULE_REQUIRED')).toBeNull()
  })
})
