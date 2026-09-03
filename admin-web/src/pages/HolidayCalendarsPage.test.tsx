import { render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'

import { HolidayCalendarsPage } from './HolidayCalendarsPage'

const mocks = vi.hoisted(() => ({
  api: {
    listHolidayCalendars: vi.fn(),
    listHolidayCalendarSyncJobs: vi.fn(),
    getHolidayCalendarSyncCapability: vi.fn(),
    createHolidayCalendarSyncJob: vi.fn(),
    confirmHolidayCalendarPreview: vi.fn(),
    getHolidayCalendarVersion: vi.fn(),
    getHolidayCalendarImpact: vi.fn(),
  },
}))

vi.mock('../auth/AdminSessionProvider', () => ({
  useAdminSession: () => ({
    api: mocks.api,
    hasPermission: (permission: string) => permission === 'holiday:calendar:write',
  }),
}))

describe('HolidayCalendarsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      value: vi.fn().mockReturnValue({ matches: false, addListener: vi.fn(), removeListener: vi.fn() }),
    })
    mocks.api.listHolidayCalendars.mockResolvedValue({
      items: [{
        calendar_id: 'cn-mainland-2026',
        display_name: '中国大陆法定节假日历（2026）',
        source_note: '数据库已发布第 1 版',
        periods: [{ name: '元旦', start: '2026-01-01', end: '2026-01-03' }],
      }],
    })
    mocks.api.listHolidayCalendarSyncJobs.mockResolvedValue({ items: [], limit: 50, offset: 0 })
    mocks.api.getHolidayCalendarSyncCapability.mockResolvedValue({ execution_available: false, region_code: 'CN' })
  })

  it('shows published coverage and keeps sync disabled until execution is configured', async () => {
    render(<HolidayCalendarsPage />)

    await waitFor(() => expect(screen.getByText('中国大陆法定节假日历（2026）')).toBeTruthy())
    expect(screen.getByText('自动同步执行服务尚未启用')).toBeTruthy()
    expect(screen.getByRole('button', { name: /同步节假日历/ }).getAttribute('disabled')).not.toBeNull()
  })

  it('shows the AI execution stream for a running synchronization job', async () => {
    mocks.api.getHolidayCalendarSyncCapability.mockResolvedValue({ execution_available: true, region_code: 'CN' })
    mocks.api.listHolidayCalendarSyncJobs.mockResolvedValue({
      items: [{
        sync_job_id: 'job-1', region_code: 'CN', year: 2027, mode: 'preview', status: 'running',
        validation_result: {
          stage: 'extracting', stage_detail: '正文已获取，AI 正在提取节假日和调休信息',
          execution_events: [
            { stage: 'discovering', detail: '正在中国政府网查找正式公告', at: '2026-09-03T10:00:00Z' },
            { stage: 'fetching', detail: '已找到公告，正在获取官方正文', at: '2026-09-03T10:00:01Z' },
            { stage: 'extracting', detail: '正文已获取，AI 正在提取节假日和调休信息', at: '2026-09-03T10:00:02Z' },
          ],
        }, attempt_count: 1, created_by: 'admin', created_at: '2026-09-03T10:00:00Z',
      }], limit: 50, offset: 0,
    })

    render(<HolidayCalendarsPage />)
    const detailButtons = await screen.findAllByRole('button', { name: '查看详情' })
    const detailButton = detailButtons[detailButtons.length - 1]
    detailButton.click()
    expect(await screen.findByText('AI 执行进度')).toBeTruthy()
    expect(screen.getByText('正文已获取，AI 正在提取节假日和调休信息')).toBeTruthy()
    expect(screen.getByText('AI 执行过程')).toBeTruthy()
  })

})
