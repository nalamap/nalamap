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
    <div className="basemap-selector">
      <p className="obsidian-kicker mb-2">Context Layer</p>
      <h3 className="mb-3">Basemap</h3>
      <select
        className="obsidian-select"
        onChange={handleBasemapChange}
        defaultValue="carto-positron"
        data-testid="basemap-select"
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
