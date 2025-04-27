// stores/layerStore.ts
import { create } from "zustand";
import { GeoDataObject } from "../models/geodatamodel";

type LayerStore = {
  layers: GeoDataObject[];
  addLayer: (layer: GeoDataObject) => void;
  removeLayer: (resource_id: string | number) => void;
  toggleLayerVisibility: (resource_id: string | number) => void;
  resetLayers: () => void;
  selectLayerForSearch: (resource_id: string | number) => void;
};

export const useLayerStore = create<LayerStore>((set) => ({
  layers: [],
  addLayer: (layer) =>
    set((state) => {
      // remove any existing layer with this resource_id
      const withoutOld = state.layers.filter(
        (l) => l.id !== layer.id
      );
      // add the new layer (always visible by default)
      return {
        layers: [
          ...withoutOld,
          {
            ...layer,
            visible: true,
          },
        ],
      };
    }),
  removeLayer: (resource_id) =>
    set((state) => ({
      layers: state.layers.filter((layer) => layer.id !== resource_id),
    })),
  toggleLayerVisibility: (resource_id) =>
    set((state) => ({
      layers: state.layers.map((layer) =>
        layer.id === resource_id
          ? { ...layer, visible: !layer.visible }
          : layer
      ),
    })),
  resetLayers: () => set({ layers: [] }),
  // new implementation:
  selectLayerForSearch: (resource_id) =>
    set((state) => ({
      layers: state.layers.map((l) => ({
        ...l,
        selected: l.id === resource_id,
      })),
    })),
}));
