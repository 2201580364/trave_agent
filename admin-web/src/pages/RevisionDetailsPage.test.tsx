import { render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'

import type { PlaceRevision } from '../api/types'
import { RevisionDetailsPage } from './RevisionDetailsPage'

const mocks = vi.hoisted(() => ({
  api: {
    getPlaceRevision: vi.fn(),
    getPlaceRevisionEvidence: vi.fn(),
  },
  navigate: vi.fn(),
}))

vi.mock('../auth/AdminSessionProvider', () => ({
  useAdminSession: () => ({ api: mocks.api }),
}))

vi.mock('react-router-dom', () => ({
  useNavigate: () => mocks.navigate,
  useParams: () => ({ revisionId: 'revision-1' }),
}))

const revision: PlaceRevision = {
  place_revision_id: 'revision-1',
  place_id: 'place-1',
  revision_number: 1,
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

describe('RevisionDetailsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
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
    expect(screen.getByText('管理服务暂时不可用，请稍后重试。')).toBeTruthy()
  })
})
