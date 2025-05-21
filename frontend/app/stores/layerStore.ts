// stores/layerStore.ts
import { create } from "zustand";
import { GeoDataObject } from "../models/geodatamodel";
import { suggestColor } from "../hooks/useLllmConfig";

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
  updateLayerStyle: (resource_id: string | number, styleOptions: Partial<import("../models/geodatamodel").StyleOptions>) => void;
  // Backend State Sync method
  synchronizeLayersFromBackend: (backend_layers: GeoDataObject[]) => void;
  synchronizeGlobalGeodataFromBackend: (backend_global_geodata: GeoDataObject[]) => void;
};

// Utility to pick a suggested color based on layer name
function getSuggestedColor(name: string): string {
  const key = name.toLowerCase();
  if (key.includes('river')) return '#3388ff';
  if (key.includes('lake') || key.includes('water')) return '#4192c4';
  if (key.includes('forest') || key.includes('wood')) return '#228B22';
  if (key.includes('road') || key.includes('highway')) return '#ff8c00';
  if (key.includes('city') || key.includes('town')) return '#e6194b';
  // fallback: random pastel
  const letters = '89ABCDEF';
  let color = '#';
  for (let i = 0; i < 6; i++) {
    color += letters[Math.floor(Math.random() * letters.length)];
  }
  return color;
}

export const useLayerStore = create<LayerStore>((set, get) => ({
  layers: [],
  globalGeodata: [],
  zoomTo: null,
  setZoomTo: (id) => set({ zoomTo: id }), // now id can be null
  addLayer: (layer) => {
    const id = layer.id;
    // initial random pastel until LLM suggestion returns
    const letters = '89ABCDEF';
    let fallback = '#';
    for (let i = 0; i < 6; i++) {
      fallback += letters[Math.floor(Math.random() * letters.length)];
    }
    set((state) => {
      const withoutOld = state.layers.filter((l) => l.id !== layer.id);
      return {
        layers: [
          ...withoutOld,
          {
            ...layer,
            visible: true,
            style: {
              strokeColor: fallback,
              fillColor: fallback,
              fillOpacity: 0.5,
            },
          },
        ],
      };
    });
    // async LLM-based color suggestion
    suggestColor(layer.name || layer.id.toString(), layer.properties || {})
      .then((color) => {
        get().updateLayerStyle(id, { strokeColor: color, fillColor: color });
      })
      .catch((err) => console.error('Color suggestion error:', err));
  },
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
  // Update styling options for a given layer
  updateLayerStyle: (resource_id, styleOptions) =>
    set((state) => ({
      layers: state.layers.map((layer) =>
        layer.id === resource_id
          ? { ...layer, style: { ...layer.style, ...styleOptions } }
          : layer
      ),
    })),
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
