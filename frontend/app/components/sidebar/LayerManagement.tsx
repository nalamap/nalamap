"use client";

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
  const setBasemap = useMapStore((state) => state.setBasemap);
  const layers = useLayerStore((state) => state.layers);
  const addLayer = useLayerStore((state) => state.addLayer);
  const toggleLayerVisibility = useLayerStore(
    (state) => state.toggleLayerVisibility,
  );
  const removeLayer = useLayerStore((state) => state.removeLayer);
  const reorderLayers = useLayerStore((state) => state.reorderLayers);
  const updateLayerStyle = useLayerStore((state) => state.updateLayerStyle);
  const setZoomTo = useLayerStore((s) => s.setZoomTo);

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
