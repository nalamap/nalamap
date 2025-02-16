// src/pages/index.tsx
import type { NextPage } from 'next';
import { useState } from 'react';
import Map, { MapType } from '../components/maps/Map';

const Home: NextPage = () => {
  const [mapType, setMapType] = useState<MapType>('openlayers');
  return (
    <>
      <div className="flex-1">
        <Map mapType={mapType} layers={[]} areas={[]} />
      </div>
      </>
  );
  
};

export default Home;