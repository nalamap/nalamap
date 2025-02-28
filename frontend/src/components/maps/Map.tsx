// src/components/maps/Map.tsx
import React from 'react';
import OpenLayersMap from './OpenLayersMap';
import MaplibreMap from './MaplibreMap';
import dynamic from 'next/dynamic';
import { useSearch } from '@/contexts/SearchContext';

export type MapType = 'openlayers' | 'maplibre';

// Dynamically import LeafletMap with SSR disabled
const LeafletMap = dynamic(() => import('./LeafletMap'), { ssr: false });

interface MapProps {
  mapType: MapType;
  layers?: any[];
  areas?: any[];
}

const Map: React.FC<MapProps> = ({ mapType, layers, areas }) => {
  return mapType === 'maplibre' ? (
    <MaplibreMap layers={layers} areas={areas} />
  ) : (
    <OpenLayersMap layers={layers} areas={areas} />
  );
};

export default Map;
