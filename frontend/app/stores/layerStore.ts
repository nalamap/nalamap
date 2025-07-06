// stores/layerStore.ts
import { create, StateCreator } from "zustand";
import { GeoDataObject, LayerStyle } from "../models/geodatamodel";

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
  // Layer styling
  updateLayerStyle: (resource_id: string | number, style: LayerStyle) => void;
  // Backend State Sync method
  synchronizeLayersFromBackend: (backend_layers: GeoDataObject[]) => void;
  updateLayersFromBackend: (updated_layers: GeoDataObject[]) => void;
  synchronizeGlobalGeodataFromBackend: (backend_global_geodata: GeoDataObject[]) => void;
};

export const useLayerStore = create<LayerStore>()(
  (set: (partial: LayerStore | Partial<LayerStore> | ((state: LayerStore) => LayerStore | Partial<LayerStore>)) => void) => ({
  layers: [],
  globalGeodata: [],
  zoomTo: null,
  setZoomTo: (id: string | number | null) => set({ zoomTo: id }),
  addLayer: (layer: GeoDataObject) =>
    set((state: LayerStore) => {
      // remove any existing layer with this resource_id
      const withoutOld = state.layers.filter(
        (l: GeoDataObject) => l.id !== layer.id
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
  removeLayer: (resource_id: string | number) =>
    set((state: LayerStore) => ({
      layers: state.layers.filter((layer: GeoDataObject) => layer.id !== resource_id),
    })),
  toggleLayerVisibility: (resource_id: string | number) =>
    set((state: LayerStore) => ({
      layers: state.layers.map((layer: GeoDataObject) =>
        layer.id === resource_id
          ? { ...layer, visible: !layer.visible }
          : layer
      ),
    })),
  resetLayers: () => set({ layers: [] }),
  selectLayerForSearch: (resource_id: string | number) =>
    set((state: LayerStore) => ({
      layers: state.layers.map((l: GeoDataObject) => ({
        ...l,
        selected: l.id === resource_id,
      })),
    })),
  // --- Modified Function ---
  toggleLayerSelection: (resource_id: string | number) =>
    set((state: LayerStore) => ({
      layers: state.layers.map((l: GeoDataObject) =>
        l.id === resource_id
          ? { ...l, selected: !l.selected } // Toggle the selected status
          : l // Keep others as they are
      ),
    })),
  // --- End Modified Function ---
  reorderLayers: (from: number, to: number) =>
    set((state: LayerStore) => {
      const layers = [...state.layers];
      const [removed] = layers.splice(from, 1);
      layers.splice(to, 0, removed);
      return { layers };
    }),
  // Layer styling
  updateLayerStyle: (resource_id: string | number, style: LayerStyle) =>
    set((state: LayerStore) => ({
      layers: state.layers.map((layer: GeoDataObject) =>
        layer.id === resource_id
          ? { ...layer, style: { ...layer.style, ...style } }
          : layer
      ),
    })),
  // Backend State Sync
  synchronizeLayersFromBackend: (backend_layers: GeoDataObject[]) =>
    set((state: LayerStore) => {
      // Create a map of existing layers by ID for easy lookup
      const existingLayersMap = new Map(state.layers.map(layer => [layer.id, layer]));
      
      // Merge backend layers with existing layers, preserving visibility and selection state
      const layers = backend_layers.map(backendLayer => {
        const existingLayer = existingLayersMap.get(backendLayer.id);
        if (existingLayer) {
          // Preserve visibility and selection state from existing layer
          return {
            ...backendLayer,
            visible: existingLayer.visible,
            selected: existingLayer.selected
          };
        }
        return backendLayer;
      });
      
      return { layers };
    }),
  // Update specific layers (for chat styling)
  updateLayersFromBackend: (updated_layers: GeoDataObject[]) =>
    set((state: LayerStore) => {
      console.log("updateLayersFromBackend called with:", updated_layers);
      console.log("Current state layers:", state.layers);
      
      const layers = state.layers.map(existingLayer => {
        const updatedLayer = updated_layers.find(layer => layer.id === existingLayer.id);
        if (updatedLayer) {
          console.log(`Updating layer ${existingLayer.id}:`, {
            old: existingLayer,
            new: updatedLayer
          });
          // Update the layer but preserve visibility and selection state
          return {
            ...updatedLayer,
            visible: existingLayer.visible,
            selected: existingLayer.selected
          };
        }
        return existingLayer;
      });
      
      console.log("Updated layers result:", layers);
      return { layers };
    }),
  synchronizeGlobalGeodataFromBackend: (backend_global_geodata: GeoDataObject[]) =>
    set((state: LayerStore) => {
      const globalGeodata = backend_global_geodata;
      //TODO: Maybe merge/improve later on?
      return { globalGeodata };
    }),
}));
