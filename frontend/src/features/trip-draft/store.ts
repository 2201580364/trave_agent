import Taro from '@tarojs/taro'
import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'

export interface PendingGeneration {
  kind: 'initial' | 'replacement'
  intentId: string
  path: string
  data: Record<string, string | number>
  selectedAttractionIds: string[]
}

interface PlanningState {
  token: string
  principalId: string
  draftId: string
  draftVersion: number
  selectedAttractionIds: string[]
  tripId: string
  revisionId: string
  currentRevisionId: string
  currentRevisionNumber: number
  pendingGeneration: PendingGeneration | null
  setPendingGeneration: (pending: PendingGeneration | null) => void
  setSession: (token: string, principalId: string) => void
  setDraft: (draftId: string, draftVersion: number) => void
  setDraftVersion: (version: number) => void
  setSelectedAttractions: (ids: string[]) => void
  setTrip: (tripId: string, revisionId: string, revisionNumber?: number) => void
  setCurrentRevision: (revisionId: string, revisionNumber: number) => void
  viewRevision: (revisionId: string) => void
  replacePlan: (draftId: string, draftVersion: number) => void
  reset: () => void
}

const storage = {
  getItem: (name: string) => Taro.getStorageSync(name) || null,
  setItem: (name: string, value: string) => Taro.setStorageSync(name, value),
  removeItem: (name: string) => Taro.removeStorageSync(name)
}

const empty = {
  token: '',
  principalId: '',
  draftId: '',
  draftVersion: 0,
  selectedAttractionIds: [] as string[],
  tripId: '',
  revisionId: '',
  currentRevisionId: '',
  currentRevisionNumber: 0,
  pendingGeneration: null as PendingGeneration | null
}

export const usePlanningStore = create<PlanningState>()(
  persist(
    (set) => ({
      ...empty,
      setPendingGeneration: (pendingGeneration) => set({ pendingGeneration }),
      setSession: (token, principalId) => set({ token, principalId }),
      setDraft: (draftId, draftVersion) => set({ draftId, draftVersion }),
      setDraftVersion: (draftVersion) => set({ draftVersion, pendingGeneration: null }),
      setSelectedAttractions: (selectedAttractionIds) => set({ selectedAttractionIds }),
      setTrip: (tripId, revisionId, currentRevisionNumber = 0) => set({
        tripId,
        revisionId,
        currentRevisionId: revisionId,
        currentRevisionNumber,
        pendingGeneration: null
      }),
      setCurrentRevision: (currentRevisionId, currentRevisionNumber) => set({
        currentRevisionId,
        currentRevisionNumber
      }),
      viewRevision: (revisionId) => set({ revisionId }),
      replacePlan: (draftId, draftVersion) => set({
        draftId,
        draftVersion,
        selectedAttractionIds: [],
        tripId: '',
        revisionId: '',
        currentRevisionId: '',
        currentRevisionNumber: 0,
        pendingGeneration: null
      }),
      reset: () => set(empty)
    }),
    { name: 'travel-agent-planning-v1', storage: createJSONStorage(() => storage) }
  )
)
