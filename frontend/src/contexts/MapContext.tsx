// src/contexts/MapContext.tsx
import { createContext, useContext, useState, ReactNode } from 'react';
import { MapType } from '../components/maps/Map';

interface MapContextProps {
  mapType: MapType;
  setMapType: (value: MapType) => void;
  toggleMapType: () => void;
}

const MapContext = createContext<MapContextProps | undefined>(undefined);

export const MapProvider = ({ children }: { children: ReactNode }) => {
  const [mapType, setMapType] = useState<MapType>('openlayers');

  const toggleMapType = () => {
    setMapType((prev) => (prev === 'openlayers' ? 'maplibre' : 'openlayers'));
  };

  return (
    <MapContext.Provider value={{ mapType, setMapType, toggleMapType }}>
      {children}
    </MapContext.Provider>
  );
};

export const useMapContext = () => {
  const context = useContext(MapContext);
  if (!context) {
    throw new Error('useMapContext must be used within a MapProvider');
  }
  return context;
};
