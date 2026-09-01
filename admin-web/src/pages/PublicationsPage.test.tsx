import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'

import type { PlaceRevision } from '../api/types'
import { PublicationsPage } from './PublicationsPage'

const mocks = vi.hoisted(() => ({
  api: {
    listCandidates: vi.fn(),
    checkPlaceRevisionPublication: vi.fn(),
    listResearchSnapshots: vi.fn(),
    previewPublicationBatch: vi.fn(),
    executePublicationBatch: vi.fn(),
    publishPlaceRevision: vi.fn(),
  },
}))

vi.mock('../auth/AdminSessionProvider', () => ({
  useAdminSession: () => ({
    api: mocks.api,
    hasPermission: () => true,
  }),
}))

const baseRevision: PlaceRevision = {
  place_revision_id: 'place_revision_internal_1',
  place_id: 'place-1',
  revision_number: 3,
  revision_version: 1,
  lifecycle_status: 'human_verified',
  canonical_name: '西湖音乐喷泉表演',
  aliases: [],
  place_kind: 'show',
  category: 'performing_arts',
  admin_area: '上城区',
  address: '湖滨三公园',
  geometry_kind: 'point',
  duration_min: 20,
  duration_recommended: 30,
  duration_max: 40,
  internal_travel_min: 0,
  energy_level: 1,
  indoor_outdoor: 'outdoor',
  suitable_periods: ['evening'],
  audience_tags: [],
  rain_suitability: 'unsuitable',
  is_always_open: false,
  solver_eligible: true,
  conflicts_resolved: true,
  source_record_ids: ['source-1'],
  created_at: '2026-09-01T00:00:00Z',
  reviewed_at: '2026-09-01T01:00:00Z',
  published_at: null,
  review_flags: [],
}

describe('PublicationsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.api.listCandidates.mockImplementation(async (status: string) => {
      const item = status === 'published'
        ? { ...baseRevision, lifecycle_status: 'published', published_at: '2026-09-01T02:00:00Z' }
        : baseRevision
      return { items: [item], limit: 20, offset: 0, total: 1 }
    })
    mocks.api.checkPlaceRevisionPublication.mockResolvedValue({
      revision_id: baseRevision.place_revision_id,
      publishable: true,
      reason_codes: [],
    })
    mocks.api.listResearchSnapshots.mockResolvedValue({ items: [], limit: 10, offset: 0, total: 0 })
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

  it('keeps published places visible in a searchable business-facing view', async () => {
    render(
      <MemoryRouter initialEntries={['/publications']}>
        <PublicationsPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(mocks.api.listCandidates).toHaveBeenCalledWith(
      'human_verified',
      20,
      0,
      {},
    ))

    fireEvent.click(screen.getByText('已发布地点'))

    await waitFor(() => expect(mocks.api.listCandidates).toHaveBeenCalledWith(
      'published',
      20,
      0,
      {},
    ))
    expect(screen.getByText('已发布地点目录')).toBeTruthy()
    expect(screen.getByText('西湖音乐喷泉表演')).toBeTruthy()
    expect(screen.getByText('上城区')).toBeTruthy()
    expect(screen.getByText('演出/固定场次')).toBeTruthy()
    expect(screen.getByText('演出演艺')).toBeTruthy()
    expect(screen.queryByText(baseRevision.place_revision_id)).toBeNull()
  })
})
