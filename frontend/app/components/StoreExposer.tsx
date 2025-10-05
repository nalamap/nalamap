"use client";

import { useEffect } from 'react';
import { useLayerStore } from '../stores/layerStore';
import { useMapStore } from '../stores/mapStore';
import { useSettingsStore } from '../stores/settingsStore';

/**
 * Component that exposes Zustand stores to the window object for E2E testing AND debugging.
 * This must run client-side to access the window object.
 */
export default function StoreExposer() {
  useEffect(() => {
    // Expose stores to window
    (window as any).useLayerStore = useLayerStore;
    (window as any).useMapStore = useMapStore;
    (window as any).useSettingsStore = useSettingsStore;
    (window as any).__STORES_EXPOSED__ = true;
    
    // Force a DOM attribute so we can detect this ran
    document.body.setAttribute('data-stores-exposed', 'true');
    
    // Log to console for debugging
    if (typeof window !== 'undefined' && window.location.search.includes('debug')) {
      console.log('[StoreExposer] Stores exposed successfully');
    }
  }, []);

  // This component doesn't render anything
  return null;
}
