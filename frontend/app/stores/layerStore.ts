// stores/layerStore.ts
import { create } from "zustand";

export type LayerData = {
    resource_id: string | number;
    name: string;
    title?: string;
    description?: string;
    access_url: string;
    source_type: string;
    format?: string;
    llm_description?: string;
    bounding_box?: any;
    score?: number;
    visible?: boolean;
  };
  
  type LayerStore = {
    layers: LayerData[];
    addLayer: (layer: LayerData) => void;
    removeLayer: (resource_id: string | number) => void;
    toggleLayerVisibility: (resource_id: string | number) => void;
    resetLayers: () => void;
  };

export const useLayerStore = create<LayerStore>((set) => ({
    layers: [],
    addLayer: (layer) =>
      set((state) => ({
        layers: [...state.layers, { ...layer, visible: true }],
      })),
    removeLayer: (resource_id) =>
      set((state) => ({
        layers: state.layers.filter((layer) => layer.resource_id !== resource_id),
      })),
    toggleLayerVisibility: (resource_id) =>
      set((state) => ({
        layers: state.layers.map((layer) =>
          layer.resource_id === resource_id
            ? { ...layer, visible: !layer.visible }
            : layer
        ),
      })),
    resetLayers: () => set({ layers: [] }),
  }));
