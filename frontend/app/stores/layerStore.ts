// stores/layerStore.ts
import { create } from "zustand";
import { GeoDataObject } from "../models/geodatamodel";

type LayerStore = {
  layers: GeoDataObject[];
  globalGeodata: GeoDataObject[];
  zoomTo: string | number | null;
  setZoomTo: (id: string | number | null) => void;
  addLayer: (layer: GeoDataObject) => void;
  removeLayer: (resource_id: string | number) => void;
  toggleLayerVisibility: (resource_id: string | number) => void;
  toggleLayerSelection: (resource_id: string | number) => void;
  resetLayers: () => void;
  selectLayerForSearch: (resource_id: string | number) => void;
  reorderLayers: (from: number, to: number) => void;
  // Backend State Sync method
  synchronizeLayersFromBackend: (backend_layers: GeoDataObject[]) => void;
  synchronizeGlobalGeodataFromBackend: (backend_global_geodata: GeoDataObject[]) => void;
};

export const useLayerStore = create<LayerStore>((set) => ({
  layers: [],
  globalGeodata: [],
  zoomTo: null,
  setZoomTo: (id) => set({ zoomTo: id }), // now id can be null
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
  selectLayerForSearch: (resource_id) =>
    set((state) => ({
      layers: state.layers.map((l) => ({
        ...l,
        selected: l.id === resource_id,
      })),
    })),
  // --- Modified Function ---
  toggleLayerSelection: (resource_id) =>
    set((state) => ({
      layers: state.layers.map((l) =>
        l.id === resource_id
          ? { ...l, selected: !l.selected } // Toggle the selected status
          : l // Keep others as they are
      ),
    })),
  // --- End Modified Function ---
  reorderLayers: (from, to) =>
    set((state) => {
      const layers = [...state.layers];
      const [removed] = layers.splice(from, 1);
      layers.splice(to, 0, removed);
      return { layers };
    }),
  // Backend State Sync
  synchronizeLayersFromBackend: (backend_layers) =>
    set((state) => {
      const layers = backend_layers;
      //TODO: Maybe merge/improve later on?
      return { layers };
    }),
  synchronizeGlobalGeodataFromBackend: (backend_global_geodata) =>
    set((state) => {
      const globalGeodata = backend_global_geodata;
      //TODO: Maybe merge/improve later on?
      return { globalGeodata };
    }),
}));
