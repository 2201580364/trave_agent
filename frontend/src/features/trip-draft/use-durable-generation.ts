// H3/S8: persist the request before submission; refresh replays the same intent.
import Taro, { useDidShow } from '@tarojs/taro'
import { useRef, useState } from 'react'
import type { GenerationIntent } from '@/entities/planning/types'
import { apiRequest, ApiError, errorMessageForCode } from '@/shared/api/client'
import { waitForGeneration } from './generation-polling'
import { type PendingGeneration, usePlanningStore } from './store'

export function useDurableGeneration(kind: PendingGeneration['kind']) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const inFlight = useRef(false)

  const run = async (newRequest?: PendingGeneration) => {
    const state = usePlanningStore.getState()
    const pending = state.pendingGeneration ?? newRequest
    if (!pending || pending.kind !== kind || !state.token || inFlight.current) return
    inFlight.current = true
    state.setPendingGeneration(pending)
    setLoading(true)
    setError('')
    const stillCurrent = () => {
      const current = usePlanningStore.getState()
      return current.token === state.token && current.pendingGeneration?.intentId === pending.intentId
    }
    try {
      const intent = await apiRequest<GenerationIntent>(pending.path, {
        method: 'POST', token: state.token, data: pending.data
      })
      const completed = await waitForGeneration(intent, {
        fetchStatus: (id) => apiRequest<GenerationIntent>(`/api/v1/generation-intents/${id}`, { token: state.token })
      })
      if (!stillCurrent()) return
      if (completed.status !== 'completed' || !completed.trip_id || !completed.trip_revision_id) {
        state.setPendingGeneration(null)
        throw new Error(errorMessageForCode(completed.failure_code ?? 'generation_temporarily_failed', errorMessageForCode('generation_temporarily_failed')))
      }
      if (intent.replacement_draft_id && intent.replacement_draft_version) {
        state.setDraft(intent.replacement_draft_id, intent.replacement_draft_version)
      }
      state.setSelectedAttractions(pending.selectedAttractionIds)
      state.setTrip(completed.trip_id, completed.trip_revision_id)
      await Taro.redirectTo({ url: '/pages/trip-detail/index' })
    } catch (cause) {
      // A rejected input can be corrected; an uncertain network outcome retains
      // the idempotency key so retry cannot silently create a second task.
      if (stillCurrent() && cause instanceof ApiError && [400, 403, 404, 409, 422].includes(cause.status)) {
        state.setPendingGeneration(null)
      }
      setError(cause instanceof Error ? cause.message : errorMessageForCode('generation_temporarily_failed'))
    } finally {
      inFlight.current = false
      setLoading(false)
    }
  }

  useDidShow(() => {
    if (usePlanningStore.getState().pendingGeneration?.kind === kind) void run()
  })
  return { run, loading, error }
}
