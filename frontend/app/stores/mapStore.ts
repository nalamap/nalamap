// stores/mapStore.ts
import { create } from "zustand";

type MapState = {
  basemap: string;
  setBasemap: (url: string) => void;
};

export const useMapStore = create<MapState>((set) => ({
  basemap: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
  setBasemap: (url) => set({ basemap: url }),
}));
