import Taro from '@tarojs/taro'
import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'

interface PlanningState {
  token: string
  principalId: string
  draftId: string
  draftVersion: number
  selectedAttractionIds: string[]
  tripId: string
  revisionId: string
  setSession: (token: string, principalId: string) => void
  setDraft: (draftId: string, draftVersion: number) => void
  setDraftVersion: (version: number) => void
  setSelectedAttractions: (ids: string[]) => void
  setTrip: (tripId: string, revisionId: string) => void
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
  revisionId: ''
}

export const usePlanningStore = create<PlanningState>()(
  persist(
    (set) => ({
      ...empty,
      setSession: (token, principalId) => set({ token, principalId }),
      setDraft: (draftId, draftVersion) => set({ draftId, draftVersion }),
      setDraftVersion: (draftVersion) => set({ draftVersion }),
      setSelectedAttractions: (selectedAttractionIds) => set({ selectedAttractionIds }),
      setTrip: (tripId, revisionId) => set({ tripId, revisionId }),
      replacePlan: (draftId, draftVersion) => set({
        draftId,
        draftVersion,
        selectedAttractionIds: [],
        tripId: '',
        revisionId: ''
      }),
      reset: () => set(empty)
    }),
    { name: 'travel-agent-planning-v1', storage: createJSONStorage(() => storage) }
  )
)
