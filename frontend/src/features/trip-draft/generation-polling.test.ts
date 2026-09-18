import { describe, expect, it, vi } from 'vitest'

vi.mock('@tarojs/taro', () => ({ default: { request: vi.fn() } }))

import type { GenerationIntent } from '@/entities/planning/types'

import { waitForGeneration } from './generation-polling'

function intent(status: GenerationIntent['status']): GenerationIntent {
  return {
    generation_intent_id: 'intent_poll_1',
    status,
    trip_id: null,
    trip_revision_id: null,
    failure_code: null
  }
}

describe('waitForGeneration', () => {
  it('continues through queued and running states until the completed result is available', async () => {
    const statuses = [intent('running'), { ...intent('completed'), trip_id: 'trip_1', trip_revision_id: 'revision_1' }]
    const requestedIds: string[] = []

    const result = await waitForGeneration(intent('queued'), {
      fetchStatus: async (intentId) => {
        requestedIds.push(intentId)
        return statuses.shift()!
      },
      sleep: async () => {},
      now: () => 100
    })

    expect(requestedIds).toEqual(['intent_poll_1', 'intent_poll_1'])
    expect(result.status).toBe('completed')
    expect(result.trip_id).toBe('trip_1')
  })

  it('fails after the configured polling deadline without requesting another status', async () => {
    let now = 0
    await expect(
      waitForGeneration(intent('queued'), {
        fetchStatus: async () => intent('running'),
        sleep: async () => {
          now = 100
        },
        now: () => now,
        timeoutMilliseconds: 100
      })
    ).rejects.toThrow('后台任务仍会继续')
  })
})
