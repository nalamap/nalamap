"use client";

import { useRef } from "react";
import { useMapStore } from "../stores/mapStore";
import { useLayerStore } from "../stores/layerStore";
import { Eye, EyeOff, Trash2 } from "lucide-react";

export default function LayerManagement() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const setBasemap = useMapStore((state) => state.setBasemap);
  const layers = useLayerStore((state) => state.layers);
  const addLayer = useLayerStore((state) => state.addLayer);
  const toggleLayerVisibility = useLayerStore((state) => state.toggleLayerVisibility);
  const removeLayer = useLayerStore((state) => state.removeLayer);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // assemble form data
    const formData = new FormData();
    formData.append("file", file);
    const API_UPLOAD_URL = process.env.NEXT_PUBLIC_API_UPLOAD_URL || "http://localhost:8000/upload";


    try {
      // hit your backend upload endpoint
      // in dev this might be http://localhost:8000/upload;
      // in prod use NEXT_PUBLIC_API_URL
      const res = await fetch(
        API_UPLOAD_URL,
        {
          method: "POST",
          body: formData,
        }
      );

      if (!res.ok) {
        console.error("Upload failed", await res.text());
        return;
      }

      // expect { url: string; id: string } back
      const { url, id } = await res.json();

      // now add to your zustand store
      addLayer({
        id: id,
        name: file.name,
        data_type: "uploaded",
        data_link: url,
        visible: true,
        data_source_id: "manual",
        data_origin: "uploaded",
        data_source: "user"
      });
    } catch (err) {
      console.error("Error uploading file:", err);
    } finally {
      // reset so same file can be re‑picked
      e.target.value = "";
    }
  };


  const handleBasemapChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selected = e.target.value;
    const baseMapUrls: Record<string, string> = {
      osm: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      "carto-light": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
      satellite: "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    };
    setBasemap(baseMapUrls[selected] || baseMapUrls.osm);
  };

  return (
    <div className="w-full h-full bg-gray-100 p-4 border-r overflow-auto">
      <h2 className="text-xl font-bold mb-4">Layer Management</h2>

      {/* Upload Section */}
      <div className="mb-4">
        <h3 className="font-semibold mb-2">Upload Data</h3>
        <div
          className="border border-dashed border-gray-400 p-4 rounded bg-white text-center cursor-pointer"
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".geojson,.kml,.json,.zip"
            onChange={handleFileUpload}
            className="hidden"
          />
          <p className="text-sm text-gray-500">Drag & drop or click to upload</p>
        </div>
      </div>

      <hr className="my-4" />

      {/* User Layers Section */}
      <div className="mb-4">
        <h3 className="font-semibold mb-2">User Layers</h3>
        {layers.length === 0 ? (
          <p className="text-sm text-gray-500">No layers added yet.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {layers.map((layer) => (
              <li
                key={layer.id}
                className="bg-white p-2 rounded shadow flex items-center justify-between"
              >
                <div className="flex-1 min-w-0">
                  <div className="font-bold text-gray-800 truncate">{layer.name}</div>
                  <div className="text-xs text-gray-500">{layer.data_type}</div>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => toggleLayerVisibility(layer.id)}
                    title="Toggle Visibility"
                    className="text-gray-600 hover:text-blue-600"
                  >
                    {layer.visible ? <Eye size={16} /> : <EyeOff size={16} />}
                  </button>
                  <button
                    onClick={() => removeLayer(layer.id)}
                    title="Remove Layer"
                    className="text-red-500 hover:text-red-700"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <hr className="my-4" />

      {/* Basemap Switcher */}
      <div>
        <h3 className="font-semibold mb-2">Basemap</h3>
        <select
          className="w-full p-2 border rounded"
          onChange={handleBasemapChange}
          defaultValue="osm"
        >
          <option value="osm">OpenStreetMap</option>
          <option value="carto-light">Carto Light</option>
          <option value="satellite">Satellite</option>
        </select>
      </div>
    </div>
  );
}
