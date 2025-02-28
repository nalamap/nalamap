import React, { useState } from 'react';
import Map, { NavigationControl, Source, Layer } from 'react-map-gl/maplibre';
import maplibregl, { StyleSpecification } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useSearch } from '@/contexts/SearchContext';

interface MaplibreMapProps {
  layers?: any[];
  areas?: any[];
}

// Default MapLibre demo style
const defaultStyle = 'https://demotiles.maplibre.org/style.json';

// OpenStreetMap raster style as an inline style object
const osmStyle: StyleSpecification = {
  version: 8,
  name: 'OSM',
  sources: {
    osm: {
      type: 'raster',
      tiles: [
        'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
        'https://b.tile.openstreetmap.org/{z}/{x}/{y}.png',
        'https://c.tile.openstreetmap.org/{z}/{x}/{y}.png'
      ],
      tileSize: 256,
      attribution: '© OpenStreetMap contributors'
    }
  },
  layers: [
    {
      id: 'osm',
      type: 'raster',
      source: 'osm',
      minzoom: 0,
      maxzoom: 19
    }
  ]
};

const MaplibreMap: React.FC<MaplibreMapProps> = ({ layers = [], areas = [] }) => {
  const [mapStyle, setMapStyle] = useState<string | StyleSpecification>(defaultStyle);
  const { selectedResult } = useSearch();

  const toggleBasemap = () => {
    setMapStyle((prevStyle) => (prevStyle === defaultStyle ? osmStyle : defaultStyle));
  };

  return (
    <div className="relative w-full h-full">
      <Map
        initialViewState={{
          longitude: 0,
          latitude: 0,
          zoom: 2
        }}
        style={{ width: '100%', height: '100%' }}
        mapStyle={mapStyle}
        mapLib={maplibregl}
      >
        <NavigationControl position="top-right" />

        {selectedResult && selectedResult.source_type === 'WFS' && (
          <Source id="selected-geojson" type="geojson" data={selectedResult.access_url}>
            <Layer
              id="selected-geojson-layer"
              type="fill" // or "line", "circle", etc. based on your data
              layout={{}}
              paint={{
                'fill-color': '#088',
                'fill-opacity': 0.5
              }}
            />
          </Source>
        )}

        {/* If selectedResult is a PNG layer, you'll need to add it differently.
            For example, you might use an ImageSource with custom coordinates.
            This might require an imperative approach if not supported declaratively. */}
      </Map>

      <button
        onClick={toggleBasemap}
        style={{
          position: 'absolute',
          top: 10,
          left: 10,
          padding: '8px 12px',
          backgroundColor: '#fff',
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer',
          zIndex: 1
        }}
      >
        Switch Basemap
      </button>
    </div>
  );
};

export default MaplibreMap;
