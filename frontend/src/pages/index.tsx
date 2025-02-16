// src/pages/index.tsx
import type { NextPage } from 'next';
import { useState } from 'react';
import Map, { MapType } from '../components/maps/Map';
import { useMapContext } from '../contexts/MapContext';

const Home: NextPage = () => {
  const { mapType } = useMapContext();
  return (
    <>
      <Map mapType={mapType} layers={[]} areas={[]} />
    </>
  );
  
};

export default Home;