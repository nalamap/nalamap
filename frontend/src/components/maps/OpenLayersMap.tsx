// src/components/maps/OpenLayersMap.tsx
import React, { useEffect, useRef } from 'react';
import 'ol/ol.css';
import Map from 'ol/Map';
import View from 'ol/View';
import TileLayer from 'ol/layer/Tile';
import OSM from 'ol/source/OSM';

interface OpenLayersMapProps {
  layers?: any[];
  areas?: any[];
}

const OpenLayersMap: React.FC<OpenLayersMapProps> = ({ layers = [], areas = [] }) => {
  const mapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!mapRef.current) return;
    // Initialize OpenLayers Map with a default OSM layer
    const map = new Map({
      target: mapRef.current,
      layers: [
        new TileLayer({
          source: new OSM(),
        }),
        // Additional layers passed via props can be added here
      ],
      view: new View({
        center: [0, 0],
        zoom: 2,
      }),
    });

    // Optionally add logic here to incorporate 'areas' overlays

    return () => {
      map.setTarget("");
    };
  }, [layers, areas]);

  return <div ref={mapRef} className="w-full h-full" />;
};

export default OpenLayersMap;
