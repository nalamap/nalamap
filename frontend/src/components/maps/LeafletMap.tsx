// src/components/maps/LeafletMap.tsx
import React from 'react';
import { MapContainer, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

interface LeafletMapProps {
  layers?: any[];
  areas?: any[];
}

const LeafletMap: React.FC<LeafletMapProps> = ({ layers = [], areas = [] }) => {
  return (
    <MapContainer center={[0, 0]} zoom={5} className="w-full h-full">
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution="&copy; OpenStreetMap contributors"
      />
      {/* Additional layers or area overlays can be rendered here */}
    </MapContainer>
  );
};

export default LeafletMap;
