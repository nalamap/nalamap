"use client";

interface BasemapSelectorProps {
  onBasemapChange: (basemapKey: string) => void;
}

export default function BasemapSelector({
  onBasemapChange,
}: BasemapSelectorProps) {
  const handleBasemapChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onBasemapChange(e.target.value);
  };

  return (
    <div>
      <h3 className="font-semibold mb-2">Basemap</h3>
      <select
        className="w-full p-2 border rounded"
        onChange={handleBasemapChange}
        defaultValue="carto-positron"
      >
        <option value="osm">OpenStreetMap</option>
        <option value="carto-positron">Carto Positron</option>
        <option value="carto-dark">Carto Dark Matter</option>
        <option value="google-satellite">Google Satellite</option>
        <option value="google-hybrid">Google Hybrid</option>
        <option value="google-terrain">Google Terrain</option>
      </select>
    </div>
  );
}
