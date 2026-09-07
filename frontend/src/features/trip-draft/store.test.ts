/**
 * S8-1 contract tests for the planning store (features/trip-draft/store.ts).
 *
 * The store is the single source of truth for the anonymous session, draft
 * lifecycle, and trip/revision navigation across every page. Taro storage is
 * mocked so the zustand persist middleware serializes to an in-memory map,
 * which lets us assert both state transitions and persistence semantics
 * without a Taro runtime.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

const taroStorage = new Map<string, string>()

vi.mock('@tarojs/taro', () => ({
  default: {
    getStorageSync: (key: string) => taroStorage.get(key) ?? null,
    setStorageSync: (key: string, value: string) => {
      taroStorage.set(key, value)
    },
    removeStorageSync: (key: string) => {
      taroStorage.delete(key)
    }
  }
}))

import { usePlanningStore } from './store'

function snapshot() {
  return usePlanningStore.getState()
}

describe('planning store session', () => {
  beforeEach(() => {
    taroStorage.clear()
    usePlanningStore.getState().reset()
  })

  it('starts empty', () => {
    const state = snapshot()
    expect(state.token).toBe('')
    expect(state.principalId).toBe('')
    expect(state.draftId).toBe('')
    expect(state.draftVersion).toBe(0)
    expect(state.selectedAttractionIds).toEqual([])
    expect(state.tripId).toBe('')
    expect(state.revisionId).toBe('')
    expect(state.currentRevisionId).toBe('')
    expect(state.currentRevisionNumber).toBe(0)
  })

  it('setSession stores token and principal id', () => {
    usePlanningStore.getState().setSession('tok-1', 'principal-1')
    const state = snapshot()
    expect(state.token).toBe('tok-1')
    expect(state.principalId).toBe('principal-1')
  })
})

describe('planning store draft lifecycle', () => {
  beforeEach(() => {
    taroStorage.clear()
    usePlanningStore.getState().reset()
  })

  it('setDraft stores id and version', () => {
    usePlanningStore.getState().setDraft('draft-1', 3)
    const state = snapshot()
    expect(state.draftId).toBe('draft-1')
    expect(state.draftVersion).toBe(3)
  })

  it('setDraftVersion bumps the version only', () => {
    usePlanningStore.getState().setDraft('draft-1', 3)
    usePlanningStore.getState().setDraftVersion(4)
    const state = snapshot()
    expect(state.draftId).toBe('draft-1')
    expect(state.draftVersion).toBe(4)
  })

  it('setSelectedAttractions replaces the selection', () => {
    usePlanningStore.getState().setSelectedAttractions(['a', 'b'])
    expect(snapshot().selectedAttractionIds).toEqual(['a', 'b'])
    usePlanningStore.getState().setSelectedAttractions(['c'])
    expect(snapshot().selectedAttractionIds).toEqual(['c'])
  })
})

describe('planning store trip and revision navigation', () => {
  beforeEach(() => {
    taroStorage.clear()
    usePlanningStore.getState().reset()
  })

  it('setTrip pins trip, revision, and current revision together', () => {
    usePlanningStore.getState().setSession('tok-1', 'principal-1')
    usePlanningStore.getState().setDraft('draft-1', 5)
    usePlanningStore.getState().setSelectedAttractions(['a', 'b', 'c'])
    usePlanningStore.getState().setTrip('trip-1', 'rev-1', 2)

    const state = snapshot()
    expect(state.tripId).toBe('trip-1')
    expect(state.revisionId).toBe('rev-1')
    expect(state.currentRevisionId).toBe('rev-1')
    expect(state.currentRevisionNumber).toBe(2)
    // setTrip must not disturb draft/session state.
    expect(state.draftId).toBe('draft-1')
    expect(state.token).toBe('tok-1')
  })

  it('setTrip defaults current revision number to 0', () => {
    usePlanningStore.getState().setTrip('trip-1', 'rev-1')
    const state = snapshot()
    expect(state.currentRevisionNumber).toBe(0)
    expect(state.currentRevisionId).toBe('rev-1')
  })

  it('viewRevision switches the viewed revision without touching current', () => {
    usePlanningStore.getState().setTrip('trip-1', 'rev-1', 2)
    usePlanningStore.getState().viewRevision('rev-0')

    const state = snapshot()
    expect(state.revisionId).toBe('rev-0')
    expect(state.currentRevisionId).toBe('rev-1')
    expect(state.currentRevisionNumber).toBe(2)
  })

  it('setCurrentRevision updates the current pointer only', () => {
    usePlanningStore.getState().setTrip('trip-1', 'rev-1', 2)
    usePlanningStore.getState().setCurrentRevision('rev-2', 3)

    const state = snapshot()
    expect(state.currentRevisionId).toBe('rev-2')
    expect(state.currentRevisionNumber).toBe(3)
    expect(state.revisionId).toBe('rev-1')
  })
})

describe('planning store replacePlan and reset', () => {
  beforeEach(() => {
    taroStorage.clear()
    usePlanningStore.getState().reset()
  })

  it('replacePlan starts a new draft round and clears trip state', () => {
    usePlanningStore.getState().setSession('tok-1', 'principal-1')
    usePlanningStore.getState().setDraft('draft-1', 5)
    usePlanningStore.getState().setSelectedAttractions(['a', 'b'])
    usePlanningStore.getState().setTrip('trip-1', 'rev-1', 2)
    usePlanningStore.getState().replacePlan('draft-2', 1)

    const state = snapshot()
    expect(state.draftId).toBe('draft-2')
    expect(state.draftVersion).toBe(1)
    expect(state.selectedAttractionIds).toEqual([])
    expect(state.tripId).toBe('')
    expect(state.revisionId).toBe('')
    expect(state.currentRevisionId).toBe('')
    expect(state.currentRevisionNumber).toBe(0)
    // A replacement round keeps the anonymous session.
    expect(state.token).toBe('tok-1')
  })

  it('reset returns everything to the initial shape', () => {
    usePlanningStore.getState().setSession('tok-1', 'principal-1')
    usePlanningStore.getState().setTrip('trip-1', 'rev-1', 2)
    usePlanningStore.getState().reset()

    const state = snapshot()
    expect(state.token).toBe('')
    expect(state.tripId).toBe('')
    expect(state.selectedAttractionIds).toEqual([])
  })
})

describe('planning store persistence (zustand persist via Taro storage)', () => {
  beforeEach(() => {
    taroStorage.clear()
    usePlanningStore.getState().reset()
  })

  it('persists state changes to storage under the store name', async () => {
    usePlanningStore.getState().setSession('tok-1', 'principal-1')
    usePlanningStore.getState().setTrip('trip-9', 'rev-9', 1)

    // zustand persist writes asynchronously (microtask).
    await Promise.resolve()

    const raw = taroStorage.get('travel-agent-planning-v1')
    expect(raw).toBeTruthy()
    const parsed = JSON.parse(raw as string)
    expect(parsed.state.token).toBe('tok-1')
    expect(parsed.state.tripId).toBe('trip-9')
    expect(parsed.version).toBe(0)
  })

  it('reset also clears the persisted payload', async () => {
    usePlanningStore.getState().setSession('tok-1', 'principal-1')
    await Promise.resolve()
    expect(taroStorage.get('travel-agent-planning-v1')).toBeTruthy()

    usePlanningStore.getState().reset()
    await Promise.resolve()

    const raw = taroStorage.get('travel-agent-planning-v1')
    expect(raw).toBeTruthy()
    const parsed = JSON.parse(raw as string)
    expect(parsed.state.token).toBe('')
  })
})
