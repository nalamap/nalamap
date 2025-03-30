"use client";

import { useState } from "react";

export default function LayerManagement() {
  const [uploadedLayers, setUploadedLayers] = useState<any[]>([]);
  const [basemap, setBasemap] = useState("osm");

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files && files.length > 0) {
      const newLayer = {
        name: files[0].name,
        source_type: "uploaded",
      };
      setUploadedLayers((prev) => [...prev, newLayer]);
    }
  };

  return (
    <div className="w-64 bg-gray-100 p-4 border-r overflow-y-auto">
      <h2 className="text-xl font-bold mb-4">Layer Management</h2>

      {/* Upload Section */}
      <div className="mb-4">
        <h3 className="font-semibold mb-2">Upload Data</h3>
        <div className="border border-dashed border-gray-400 p-4 rounded bg-white text-center cursor-pointer">
          <input
            type="file"
            accept=".geojson,.kml,.json,.zip"
            onChange={handleFileUpload}
            className="w-full cursor-pointer"
          />
          <p className="text-sm text-gray-500 mt-2">Drag & drop or click to upload</p>
        </div>
      </div>

      <hr className="my-4" />

      {/* User Layers Section */}
      <div className="mb-4">
        <h3 className="font-semibold mb-2">User Layers</h3>
        {uploadedLayers.length === 0 ? (
          <p className="text-sm text-gray-500">No layers added yet.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {uploadedLayers.map((layer, idx) => (
              <li key={idx} className="bg-white p-2 rounded shadow">
                <div className="font-bold text-gray-800">{layer.name}</div>
                <div className="text-xs text-gray-500">{layer.source_type}</div>
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
          value={basemap}
          onChange={(e) => setBasemap(e.target.value)}
        >
          <option value="osm">OpenStreetMap</option>
          <option value="carto-light">Carto Light</option>
          <option value="satellite">Satellite</option>
        </select>
      </div>
    </div>
  );
}
