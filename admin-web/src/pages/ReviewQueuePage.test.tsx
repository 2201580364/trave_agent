import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'

import type { ReviewTask } from '../api/types'
import { ReviewQueuePage } from './ReviewQueuePage'

const mocks = vi.hoisted(() => ({
  api: {
    listReviewTasks: vi.fn(),
    listReviewDecisions: vi.fn(),
  },
  navigate: vi.fn(),
}))

vi.mock('../auth/AdminSessionProvider', () => ({
  useAdminSession: () => ({ api: mocks.api }),
}))

vi.mock('react-router-dom', () => ({
  useNavigate: () => mocks.navigate,
}))

const task: ReviewTask = {
  review_task_id: 'task-1',
  place_revision_id: 'revision-west-lake',
  status: 'ready_for_review',
  assigned_reviewer_id: null,
  version: 1,
  created_by: 'editor-1',
  created_at: '2026-08-31T00:00:00Z',
  updated_at: '2026-08-31T00:00:00Z',
}

describe('ReviewQueuePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.api.listReviewTasks.mockResolvedValue({ items: [task], limit: 50, offset: 0 })
    mocks.api.listReviewDecisions.mockResolvedValue({ items: [] })
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

  it('provides a direct entry to the reviewed place details', async () => {
    render(<ReviewQueuePage />)

    await waitFor(() => expect(screen.getByText(task.place_revision_id)).toBeTruthy())
    const detailsButton = screen.getByText('查看地点详情')
    fireEvent.click(detailsButton)

    expect(mocks.navigate).toHaveBeenCalledWith('/candidates/revision-west-lake?from=review&task=task-1')
  })
})
