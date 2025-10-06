"use client";

// This file exposes Zustand stores to the window object for E2E testing
import { useEffect } from "react";
import { useLayerStore } from "./stores/layerStore";
import { useMapStore } from "./stores/mapStore";
import { useSettingsStore } from "./stores/settingsStore";

export default function ExposeStoresForTesting() {
  useEffect(() => {
    if (typeof window !== "undefined") {
      // Expose stores when component mounts
      (window as any).useLayerStore = useLayerStore;
      (window as any).useMapStore = useMapStore;
      (window as any).useSettingsStore = useSettingsStore;

      console.log("[Test Infrastructure] Stores exposed to window");
    }
  }, []);

  return null;
}
