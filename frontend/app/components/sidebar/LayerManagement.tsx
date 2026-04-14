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
  const updateLayer = useLayerStore((state) => state.updateLayer);
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
    <div className="layer-panel">
      <div className="layer-panel-section">
        <p className="obsidian-kicker mb-2">Workspace</p>
        <h2 className="obsidian-heading text-lg">Maps</h2>
        <div className="flex items-center gap-2">
          <select
            className="obsidian-select flex-1 text-sm"
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
            className="obsidian-button-primary px-3 py-2 text-sm disabled:opacity-50"
          >
            {isSaving ? "Saving..." : "Save"}
          </button>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <input
            className="obsidian-input flex-1 text-sm"
            placeholder="New map name"
            value={newMapName}
            onChange={(e) => setNewMapName(e.target.value)}
          />
          <button
            onClick={handleCreateMap}
            disabled={!newMapName.trim()}
            className="obsidian-button-ghost px-3 py-2 text-sm disabled:opacity-50"
          >
            Create
          </button>
        </div>
        {saveMessage && (
          <p className="obsidian-status-success mt-2 text-xs">{saveMessage}</p>
        )}
      </div>
      <div>
        <p className="obsidian-kicker mb-2">Map Workspace</p>
        <h2 className="layer-panel-title">Layer Management</h2>
      </div>

      <UploadSection addLayer={addLayer} updateLayerStyle={updateLayerStyle} />

      <hr className="obsidian-divider" />

      <LayerList
        layers={layers}
        toggleLayerVisibility={toggleLayerVisibility}
        removeLayer={removeLayer}
        reorderLayers={reorderLayers}
        updateLayer={updateLayer}
        updateLayerStyle={updateLayerStyle}
        setZoomTo={setZoomTo}
      />

      <hr className="obsidian-divider" />

      <BasemapSelector onBasemapChange={handleBasemapChange} />
    </div>
  );
}
