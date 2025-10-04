// stores/mapStore.ts
import { create } from "zustand";

type BasemapInfo = {
  url: string;
  attribution: string;
};

type MapState = {
  basemap: BasemapInfo;
  setBasemap: (basemap: BasemapInfo) => void;
};

export const useMapStore = create<MapState>((set) => ({
  basemap: {
    url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="https://carto.com/attribution">CARTO</a>'
  },
  setBasemap: (basemap) => set({ basemap }),
}));

// Expose store to window for E2E testing
if (typeof window !== 'undefined') {
  (window as any).useMapStore = useMapStore;
  console.log('[MapStore] Exposed to window for testing');
}
