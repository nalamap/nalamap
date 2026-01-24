"use client";

import { useState } from "react";
import { useMapStore } from "../../stores/mapStore";
import { useLayerStore } from "../../stores/layerStore";
import UploadSection from "./UploadSection";
import BasemapSelector from "./BasemapSelector";
import LayerList from "./LayerList";

type BasemapKey =
  | "osm"
  | "carto-positron"
  | "carto-dark"
  | "google-satellite"
  | "google-hybrid"
  | "google-terrain";

export default function LayerManagement() {
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [newMapName, setNewMapName] = useState("");

  const maps = useMapStore((state) => state.maps);
  const currentMapId = useMapStore((state) => state.currentMapId);
  const setCurrentMapId = useMapStore((state) => state.setCurrentMapId);
  const createMap = useMapStore((state) => state.createMap);

  const setBasemap = useMapStore((state) => state.setBasemap);
  const layers = useLayerStore((state) => state.layers);
  const addLayer = useLayerStore((state) => state.addLayer);
  const saveLayersToMap = useLayerStore((state) => state.saveLayersToMap);
  const toggleLayerVisibility = useLayerStore(
    (state) => state.toggleLayerVisibility,
  );
  const removeLayer = useLayerStore((state) => state.removeLayer);
  const reorderLayers = useLayerStore((state) => state.reorderLayers);
  const updateLayerStyle = useLayerStore((state) => state.updateLayerStyle);
  const setZoomTo = useLayerStore((s) => s.setZoomTo);

  const handleSaveMap = async () => {
    if (!currentMapId) return;
    setIsSaving(true);
    setSaveMessage(null);
    await saveLayersToMap(currentMapId);
    setSaveMessage("Saved to map.");
    setIsSaving(false);
    setTimeout(() => setSaveMessage(null), 3000);
  };

  const handleCreateMap = async () => {
    const name = newMapName.trim();
    if (!name) return;
    setSaveMessage(null);
    const created = await createMap(name);
    if (created) {
      setNewMapName("");
      setSaveMessage("Map created.");
      setTimeout(() => setSaveMessage(null), 3000);
    }
  };

  const handleBasemapChange = (selected: string) => {
    const basemaps: Record<BasemapKey, { url: string; attribution: string }> = {
      osm: {
        url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      },
      "carto-positron": {
        url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="https://carto.com/attribution">CARTO</a>',
      },
      "carto-dark": {
        url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="https://carto.com/attribution">CARTO</a>',
      },
      "google-satellite": {
        url: "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attribution: "&copy; Google Satellite",
      },
      "google-hybrid": {
        url: "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
        attribution: "&copy; Google Hybrid",
      },
      "google-terrain": {
        url: "https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}",
        attribution: "&copy; Google Terrain",
      },
    };
    setBasemap(basemaps[selected as BasemapKey] || basemaps["carto-positron"]);
  };

  return (
    <div className="w-full h-full bg-primary-50 p-4 border-r border-primary-300 overflow-auto">
      <div className="mb-4 rounded border border-primary-200 bg-primary-100 p-3">
        <h2 className="text-sm font-semibold text-primary-800 mb-2">Maps</h2>
        <div className="flex items-center gap-2">
          <select
            className="flex-1 rounded border border-primary-300 bg-white px-2 py-1 text-sm"
            value={currentMapId ?? ""}
            onChange={(e) =>
              setCurrentMapId(e.target.value ? e.target.value : null)
            }
          >
            {maps.length === 0 && <option value="">No maps</option>}
            {maps.map((map) => (
              <option key={map.id} value={map.id}>
                {map.name}
              </option>
            ))}
          </select>
          <button
            onClick={handleSaveMap}
            disabled={!currentMapId || isSaving}
            className="rounded bg-secondary-700 px-3 py-1 text-sm text-white hover:bg-secondary-800 disabled:opacity-50"
          >
            {isSaving ? "Saving..." : "Save"}
          </button>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <input
            className="flex-1 rounded border border-primary-300 bg-white px-2 py-1 text-sm"
            placeholder="New map name"
            value={newMapName}
            onChange={(e) => setNewMapName(e.target.value)}
          />
          <button
            onClick={handleCreateMap}
            disabled={!newMapName.trim()}
            className="rounded border border-primary-300 px-3 py-1 text-sm text-primary-800 hover:bg-primary-200 disabled:opacity-50"
          >
            Create
          </button>
        </div>
        {saveMessage && (
          <p className="mt-2 text-xs text-primary-700">{saveMessage}</p>
        )}
      </div>
      <h2 className="text-xl font-bold mb-4 text-center">Layer Management</h2>

      <UploadSection addLayer={addLayer} updateLayerStyle={updateLayerStyle} />

      <hr className="my-4" />

      <LayerList
        layers={layers}
        toggleLayerVisibility={toggleLayerVisibility}
        removeLayer={removeLayer}
        reorderLayers={reorderLayers}
        updateLayerStyle={updateLayerStyle}
        setZoomTo={setZoomTo}
      />

      <hr className="my-4" />

      <BasemapSelector onBasemapChange={handleBasemapChange} />
    </div>
  );
}
