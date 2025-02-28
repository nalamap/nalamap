// src/pages/_app.tsx
import '../styles/globals.css';
import type { AppProps } from 'next/app';
import Sidebar from '../components/common/Sidebar';
import { MapProvider } from '../contexts/MapContext';
import SearchPrompt from '../components/common/SearchPrompt';
import { SearchProvider } from '@/contexts/SearchContext';


function GeoWeaverFrontend({ Component, pageProps }: AppProps) {
  return (
    <>
      <MapProvider>
        <SearchProvider>
        <div className="flex h-screen">
          <Sidebar />
          <div className="flex-1 min-h-0 min-w-0 w-full h-full">
            <Component {...pageProps} />
          </div>
        </div>
        </SearchProvider>
      </MapProvider>
    </>
  );
}

export default GeoWeaverFrontend;