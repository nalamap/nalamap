// stores/mapStore.ts
import { create } from "zustand";
import Logger from "../utils/logger";
import { getApiBase } from "../utils/apiBase";

type BasemapInfo = {
  url: string;
  attribution: string;
};

type MapRecord = {
  id: string;
  name: string;
  description?: string | null;
};

type MapState = {
  basemap: BasemapInfo;
  maps: MapRecord[];
  currentMapId: string | null;
  setBasemap: (basemap: BasemapInfo) => void;
  setMaps: (maps: MapRecord[]) => void;
  setCurrentMapId: (mapId: string | null) => void;
  loadMaps: () => Promise<void>;
  ensureDefaultMap: () => Promise<void>;
  createMap: (name: string, description?: string | null) => Promise<MapRecord | null>;
  clearMaps: () => void;
};

type MapApiRecord = {
  id: string;
  name: string;
  description?: string | null;
};

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

export const useMapStore = create<MapState>((set) => ({
  basemap: {
    url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="https://carto.com/attribution">CARTO</a>',
  },
  maps: [],
  currentMapId: null,
  setBasemap: (basemap) => set({ basemap }),
  setMaps: (maps) =>
    set((state) => ({
      maps,
      currentMapId:
        state.currentMapId && maps.some((m) => m.id === state.currentMapId)
          ? state.currentMapId
          : maps[0]?.id ?? null,
    })),
  setCurrentMapId: (mapId) => set({ currentMapId: mapId }),
  loadMaps: async () => {
    try {
      const apiBase = getApiBase();
      const records = await fetchJson<MapApiRecord[]>(`${apiBase}/maps/`);
      const maps = records.map((record) => ({
        id: record.id,
        name: record.name,
        description: record.description ?? null,
      }));
      set((state) => ({
        maps,
        currentMapId:
          state.currentMapId && maps.some((m) => m.id === state.currentMapId)
            ? state.currentMapId
            : maps[0]?.id ?? null,
      }));
    } catch (err) {
      Logger.warn("Failed to load maps:", err);
    }
  },
  ensureDefaultMap: async () => {
    try {
      const apiBase = getApiBase();
      const records = await fetchJson<MapApiRecord[]>(`${apiBase}/maps/`);
      if (records.length > 0) {
        set(() => ({
          maps: records,
          currentMapId: records[0]?.id ?? null,
        }));
        return;
      }

      const created = await fetchJson<MapApiRecord>(`${apiBase}/maps/`, {
        method: "POST",
        body: JSON.stringify({
          name: "My Map",
          description: "Default map",
        }),
      });
      set(() => ({
        maps: [created],
        currentMapId: created.id,
      }));
    } catch (err) {
      Logger.warn("Failed to ensure default map:", err);
    }
  },
  createMap: async (name: string, description?: string | null) => {
    try {
      const apiBase = getApiBase();
      const created = await fetchJson<MapApiRecord>(`${apiBase}/maps/`, {
        method: "POST",
        body: JSON.stringify({ name, description }),
      });
      const record: MapRecord = {
        id: created.id,
        name: created.name,
        description: created.description ?? null,
      };
      set((state) => ({
        maps: [...state.maps, record],
        currentMapId: record.id,
      }));
      return record;
    } catch (err) {
      Logger.warn("Failed to create map:", err);
    }
    return null;
  },
  clearMaps: () => set({ maps: [], currentMapId: null }),
}));

// Expose store to window for E2E testing
if (typeof window !== "undefined") {
  (window as any).useMapStore = useMapStore;
  console.log("[MapStore] Exposed to window for testing");
}
