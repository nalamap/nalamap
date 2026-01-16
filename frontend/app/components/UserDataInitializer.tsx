"use client";

import { useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { useLayerStore } from "../stores/layerStore";
import { useMapStore } from "../stores/mapStore";

export default function UserDataInitializer() {
  const { user } = useAuth();
  const loadLayersForMap = useLayerStore((s) => s.loadLayersForMap);
  const resetLayers = useLayerStore((s) => s.resetLayers);
  const ensureDefaultMap = useMapStore((s) => s.ensureDefaultMap);
  const clearMaps = useMapStore((s) => s.clearMaps);
  const currentMapId = useMapStore((s) => s.currentMapId);

  useEffect(() => {
    if (user === undefined) return;

    if (user === null) {
      resetLayers();
      clearMaps();
      return;
    }

    if (!currentMapId) {
      void ensureDefaultMap();
      return;
    }

    void loadLayersForMap(currentMapId);
  }, [
    user,
    currentMapId,
    ensureDefaultMap,
    loadLayersForMap,
    resetLayers,
    clearMaps,
  ]);

  return null;
}
