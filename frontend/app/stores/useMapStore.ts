// stores/useMapStore.ts
import { create } from 'zustand'

export const useMapStore = create((set) => ({
  layers: [],
  conversation: [],
  addLayer: (layer: any) => set((state: { layers: any }) => ({ layers: [...state.layers, layer] })),
  addMessage: (msg: any) => set((state: { conversation: any }) => ({ conversation: [...state.conversation, msg] })),
}))
