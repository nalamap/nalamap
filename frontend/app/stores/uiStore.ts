// stores/uiStore.ts
import { create } from "zustand";
import { persist } from "zustand/middleware";

type UIState = {
  sidebarWidth: number; // percentage
  layerPanelWidth: number; // percentage
  mapWidth: number; // percentage
  chatPanelWidth: number; // percentage
  layerPanelCollapsed: boolean; // track if layer panel is collapsed
  setSidebarWidth: (width: number) => void;
  setLayoutWidths: (widths: [number, number, number, number]) => void;
  getLayoutWidths: () => [number, number, number, number];
  setLayerPanelCollapsed: (collapsed: boolean) => void;
};

export const useUIStore = create<UIState>()(
  persist(
    (set, get) => ({
      sidebarWidth: 4,
      layerPanelWidth: 18,
      mapWidth: 56,
      chatPanelWidth: 22,
      layerPanelCollapsed: false,
      setSidebarWidth: (width) => set({ sidebarWidth: width }),
      setLayoutWidths: ([sidebar, layer, map, chat]) =>
        set({
          sidebarWidth: sidebar,
          layerPanelWidth: layer,
          mapWidth: map,
          chatPanelWidth: chat,
        }),
      getLayoutWidths: () => {
        const state = get();
        return [
          state.sidebarWidth,
          state.layerPanelWidth,
          state.mapWidth,
          state.chatPanelWidth,
        ];
      },
      setLayerPanelCollapsed: (collapsed) => set({ layerPanelCollapsed: collapsed }),
    }),
    {
      name: "nalamap-ui-storage", // localStorage key
    }
  )
);

// Expose store to window for E2E testing
if (typeof window !== "undefined") {
  (window as any).useUIStore = useUIStore;
  console.log("[UIStore] Exposed to window for testing");
}
