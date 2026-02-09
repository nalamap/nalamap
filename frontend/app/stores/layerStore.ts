// stores/layerStore.ts
import { create } from "zustand";
import { GeoDataObject, LayerStyle } from "../models/geodatamodel";
import { getApiBase } from "../utils/apiBase";
import Logger from "../utils/logger";

type LayerApiRecord = {
  id: string;
  data_link: string;
  data_type: string;
  name: string;
  description?: string | null;
  derived: boolean;
  style?: LayerStyle | null;
  payload?: Record<string, any> | null;
};

type MapLayerApiRecord = LayerApiRecord & {
  z_index: number;
  visible: boolean;
};

type LayerApiPayload = {
  data_link: string;
  data_type: string;
  name: string;
  description?: string | null;
  derived: boolean;
  style?: LayerStyle | null;
  payload?: Record<string, any> | null;
};

const inferLayerType = (dataType?: string, dataLink?: string): string | undefined => {
  const link = (dataLink || "").toLowerCase();
  if (link.includes("service=wms") || link.includes("/wms")) {
    return "WMS";
  }
  if (link.includes("service=wfs") || link.includes("/wfs")) {
    return "WFS";
  }
  if (link.includes("service=wmts") || link.includes("/wmts")) {
    return "WMTS";
  }
  if (link.includes("service=wcs") || link.includes("/wcs")) {
    return "WCS";
  }
  if (link.endsWith(".geojson") || link.includes("application/json")) {
    return "UPLOADED";
  }
  if (dataType) {
    return dataType.toUpperCase();
  }
  return undefined;
};

const buildPayload = (layer: GeoDataObject, order?: number) => ({
  external_id: layer.id,
  data_source_id: layer.data_source_id,
  data_origin: layer.data_origin,
  data_source: layer.data_source,
  title: layer.title,
  llm_description: layer.llm_description,
  score: layer.score,
  bounding_box: layer.bounding_box,
  layer_type: layer.layer_type,
  properties: layer.properties,
  visible: layer.visible,
  selected: layer.selected,
  sha256: layer.sha256,
  size: layer.size,
  order,
});

const toApiPayload = (layer: GeoDataObject, order?: number): LayerApiPayload => ({
  data_link: layer.data_link,
  data_type: layer.data_type || "Layer",
  name: layer.name,
  description: layer.description ?? null,
  derived: false,
  style: layer.style ?? null,
  payload: buildPayload(layer, order),
});

const fromApiRecord = (record: LayerApiRecord): GeoDataObject => {
  const payload = record.payload || {};
  return {
    id: payload.external_id || record.id,
    db_id: record.id,
    data_source_id: payload.data_source_id || record.id,
    data_type: record.data_type,
    data_origin: payload.data_origin || "uploaded",
    data_source: payload.data_source || "user",
    data_link: record.data_link,
    name: record.name,
    title: payload.title || record.name,
    description: record.description ?? payload.description ?? undefined,
    llm_description: payload.llm_description,
    score: payload.score,
    bounding_box: payload.bounding_box,
    layer_type: payload.layer_type || inferLayerType(record.data_type, record.data_link),
    properties: payload.properties || {},
    visible: payload.visible ?? true,
    selected: payload.selected ?? false,
    style: record.style ?? undefined,
    sha256: payload.sha256,
    size: payload.size,
  };
};

const fromMapLayerRecord = (record: MapLayerApiRecord): GeoDataObject => {
  const layer = fromApiRecord(record);
  return {
    ...layer,
    visible: record.visible ?? layer.visible,
  };
};

const extractOrder = (record: LayerApiRecord, fallback: number): number => {
  const raw = record.payload?.order;
  if (typeof raw === "number" && Number.isFinite(raw)) {
    return raw;
  }
  const parsed = raw ? Number(raw) : NaN;
  return Number.isFinite(parsed) ? parsed : fallback;
};

const apiUrl = (path: string) => `${getApiBase()}${path}`;

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`);
  }
  return (await res.json()) as T;
}

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
  updateLayer: (
    resource_id: string | number,
    updates: Partial<GeoDataObject>,
  ) => void;
  updateLayerStyle: (resource_id: string | number, style: LayerStyle) => void;
  loadLayersFromBackend: () => Promise<void>;
  loadLayersForMap: (mapId: string) => Promise<void>;
  saveLayersToMap: (mapId: string) => Promise<void>;
  // Backend State Sync method
  synchronizeLayersFromBackend: (backend_layers: GeoDataObject[]) => void;
  updateLayersFromBackend: (updated_layers: GeoDataObject[]) => void;
  synchronizeGlobalGeodataFromBackend: (
    backend_global_geodata: GeoDataObject[],
  ) => void;
};

export const useLayerStore = create<LayerStore>()((set, get) => {
  const pendingCreates = new Map<string, Promise<string>>();

  const persistLayer = async (
    layerId: string | number,
    orderOverride?: number,
  ): Promise<string | null> => {
    const state = get();
    const layerIndex = state.layers.findIndex((layer) => layer.id === layerId);
    if (layerIndex === -1) return null;

    const layer = state.layers[layerIndex];
    const order = orderOverride ?? layerIndex;
    const payload = toApiPayload(layer, order);

    if (!layer.db_id) {
      const pendingKey = String(layer.id);
      let createPromise = pendingCreates.get(pendingKey);
      if (!createPromise) {
        createPromise = (async () => {
          const created = await fetchJson<LayerApiRecord>(apiUrl("/layers/"), {
            method: "POST",
            body: JSON.stringify(payload),
          });
          return created.id;
        })();
        pendingCreates.set(pendingKey, createPromise);
      }

      try {
        const createdId = await createPromise;
        set((state: LayerStore) => ({
          layers: state.layers.map((item) =>
            item.id === layerId ? { ...item, db_id: createdId } : item,
          ),
        }));
        return createdId;
      } catch (err) {
        Logger.warn("Failed to persist new layer:", err);
      } finally {
        pendingCreates.delete(pendingKey);
      }
      return null;
    }

    try {
      await fetchJson<LayerApiRecord>(apiUrl(`/layers/${layer.db_id}`), {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      return layer.db_id;
    } catch (err) {
      Logger.warn("Failed to update layer:", err);
    }
    return null;
  };

  const persistLayerDelete = async (dbId: string) => {
    try {
      const res = await fetch(apiUrl(`/layers/${dbId}`), {
        method: "DELETE",
        credentials: "include",
      });
      if (!res.ok && res.status !== 404) {
        throw new Error(`Delete failed: ${res.status}`);
      }
    } catch (err) {
      Logger.warn("Failed to delete layer:", err);
    }
  };

  const persistLayerOrdering = async () => {
    const state = get();
    await Promise.all(
      state.layers.map((layer, index) => persistLayer(layer.id, index)),
    );
  };

  const loadLayersFromBackend = async () => {
    try {
      const records = await fetchJson<LayerApiRecord[]>(apiUrl("/layers/"));
      const withOrder = records.map((record, index) => ({
        order: extractOrder(record, index),
        layer: fromApiRecord(record),
      }));
      const hasOrdering = records.some(
        (record) => record.payload?.order !== undefined,
      );
      const sorted = hasOrdering
        ? [...withOrder].sort((a, b) => a.order - b.order)
        : withOrder;
      set({ layers: sorted.map((item) => item.layer) });
    } catch (err) {
      Logger.warn("Failed to load layers:", err);
    }
  };

  const loadLayersForMap = async (mapId: string) => {
    try {
      const records = await fetchJson<MapLayerApiRecord[]>(
        apiUrl(`/maps/${mapId}/layers`),
      );
      const sorted = [...records].sort((a, b) => a.z_index - b.z_index);
      set({ layers: sorted.map((record) => fromMapLayerRecord(record)) });
    } catch (err) {
      Logger.warn("Failed to load map layers:", err);
      set({ layers: [] });
    }
  };

  const saveLayersToMap = async (mapId: string) => {
    const state = get();
    const resolved = await Promise.all(
      state.layers.map((layer, index) => persistLayer(layer.id, index)),
    );

    const payload = state.layers.map((layer, index) => ({
      layer_id: layer.db_id || resolved[index],
      z_index: index,
      visible: layer.visible ?? true,
    }));

    const filtered = payload.filter((item) => item.layer_id);
    try {
      await fetchJson(apiUrl(`/maps/${mapId}/layers`), {
        method: "PUT",
        body: JSON.stringify(filtered),
      });
    } catch (err) {
      Logger.warn("Failed to save map layers:", err);
    }
  };

  return {
    layers: [],
    globalGeodata: [],
    zoomTo: null,
    setZoomTo: (id: string | number | null) => set({ zoomTo: id }),
    addLayer: (layer: GeoDataObject) => {
      set((state: LayerStore) => {
        const withoutOld = state.layers.filter(
          (l: GeoDataObject) => l.id !== layer.id,
        );
        return {
          layers: [
            ...withoutOld,
            {
              ...layer,
              visible: layer.visible ?? true,
            },
          ],
        };
      });
      void persistLayer(layer.id);
    },
    removeLayer: (resource_id: string | number) => {
      const target = get().layers.find((layer) => layer.id === resource_id);
      set((state: LayerStore) => ({
        layers: state.layers.filter(
          (layer: GeoDataObject) => layer.id !== resource_id,
        ),
      }));
      if (target?.db_id) {
        void persistLayerDelete(target.db_id);
      }
    },
    toggleLayerVisibility: (resource_id: string | number) => {
      set((state: LayerStore) => ({
        layers: state.layers.map((layer: GeoDataObject) =>
          layer.id === resource_id
            ? { ...layer, visible: !layer.visible }
            : layer,
        ),
      }));
      void persistLayer(resource_id);
    },
    resetLayers: () => set({ layers: [] }),
    selectLayerForSearch: (resource_id: string | number) =>
      set((state: LayerStore) => ({
        layers: state.layers.map((l: GeoDataObject) => ({
          ...l,
          selected: l.id === resource_id,
        })),
      })),
    toggleLayerSelection: (resource_id: string | number) =>
      set((state: LayerStore) => ({
        layers: state.layers.map((l: GeoDataObject) =>
          l.id === resource_id ? { ...l, selected: !l.selected } : l,
        ),
      })),
    reorderLayers: (from: number, to: number) => {
      set((state: LayerStore) => {
        const layers = [...state.layers];
        const [removed] = layers.splice(from, 1);
        layers.splice(to, 0, removed);
        return { layers };
      });
      void persistLayerOrdering();
    },
    updateLayer: (
      resource_id: string | number,
      updates: Partial<GeoDataObject>,
    ) => {
      set((state: LayerStore) => ({
        layers: state.layers.map((layer: GeoDataObject) =>
          layer.id === resource_id ? { ...layer, ...updates } : layer,
        ),
      }));
      void persistLayer(resource_id);
    },
    updateLayerStyle: (resource_id: string | number, style: LayerStyle) => {
      set((state: LayerStore) => ({
        layers: state.layers.map((layer: GeoDataObject) =>
          layer.id === resource_id
            ? { ...layer, style: { ...layer.style, ...style } }
            : layer,
        ),
      }));
      void persistLayer(resource_id);
    },
    loadLayersFromBackend,
    loadLayersForMap,
    saveLayersToMap,
    synchronizeLayersFromBackend: (backend_layers: GeoDataObject[]) => {
      let persistIds: Array<string | number> = [];
      set((state: LayerStore) => {
        const existingLayersMap = new Map(
          state.layers.map((layer) => [layer.id, layer]),
        );

        const layers = backend_layers.map((backendLayer) => {
          const existingLayer = existingLayersMap.get(backendLayer.id);
          if (existingLayer) {
            return {
              ...backendLayer,
              db_id: existingLayer.db_id,
              visible: existingLayer.visible,
              selected: existingLayer.selected,
            };
          }
          // New layer: ensure visible defaults to true
          return {
            ...backendLayer,
            visible: backendLayer.visible ?? true,
          };
        });

        persistIds = layers
          .filter((layer) => !layer.db_id)
          .map((layer) => layer.id);

        return { layers };
      });
      persistIds.forEach((id) => void persistLayer(id));
    },
    updateLayersFromBackend: (updated_layers: GeoDataObject[]) => {
      let persistIds: Array<string | number> = [];
      set((state: LayerStore) => {
        Logger.log("updateLayersFromBackend called with:", updated_layers);
        Logger.log("Current state layers:", state.layers);

        const layers = state.layers.map((existingLayer) => {
          const updatedLayer = updated_layers.find(
            (layer) => layer.id === existingLayer.id,
          );
          if (updatedLayer) {
            Logger.log(`Updating layer ${existingLayer.id}:`, {
              old: existingLayer,
              new: updatedLayer,
            });
            return {
              ...updatedLayer,
              db_id: existingLayer.db_id,
              visible: existingLayer.visible,
              selected: existingLayer.selected,
            };
          }
          return existingLayer;
        });

        persistIds = layers
          .filter((layer) => updated_layers.some((u) => u.id === layer.id))
          .map((layer) => layer.id);

        Logger.log("Updated layers result:", layers);
        return { layers };
      });
      persistIds.forEach((id) => void persistLayer(id));
    },
    synchronizeGlobalGeodataFromBackend: (
      backend_global_geodata: GeoDataObject[],
    ) =>
      set(() => ({
        globalGeodata: backend_global_geodata,
      })),
  };
});

// Expose store to window for E2E testing
if (typeof window !== "undefined") {
  (window as any).useLayerStore = useLayerStore;
  console.log("[LayerStore] Exposed to window for testing");
}
