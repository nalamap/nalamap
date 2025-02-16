// src/pages/index.tsx
import type { NextPage } from 'next';
import { useState } from 'react';
import Map, { MapType } from '../components/maps/Map';

const Home: NextPage = () => {
  const [mapType, setMapType] = useState<MapType>('openlayers');
  return (
    <>
      <div className="container mx-auto p-4">
      <div className="min-h-screen">
      <button
        onClick={() => setMapType(mapType === 'openlayers' ? 'leaflet' : 'openlayers')}
        className="m-4 p-2 bg-blue-600 text-white rounded"
      >
        Toggle Map Library
      </button>
      <div className="w-full h-96">
        <Map mapType={mapType} layers={[]} areas={[]} />
      </div>
    </div>
      </div>
    </>
  );
};

export default Home;