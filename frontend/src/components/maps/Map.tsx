// src/components/maps/Map.tsx
import React from 'react';
import OpenLayersMap from './OpenLayersMap';
import dynamic from 'next/dynamic';

export type MapType = 'openlayers' | 'leaflet';

// Dynamically import LeafletMap with SSR disabled
const LeafletMap = dynamic(() => import('./LeafletMap'), { ssr: false });

interface MapProps {
  mapType: MapType;
  layers?: any[];
  areas?: any[];
}

const Map: React.FC<MapProps> = ({ mapType, layers, areas }) => {
  return mapType === 'leaflet' ? (
    <LeafletMap layers={layers} areas={areas} />
  ) : (
    <OpenLayersMap layers={layers} areas={areas} />
  );
};

export default Map;
