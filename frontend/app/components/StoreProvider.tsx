'use client';

import { useEffect } from 'react';
import { useLayerStore } from '../stores/layerStore';
import { useSettingsStore } from '../stores/settingsStore';

/**
 * Client component that ensures stores are initialized and exposed
 * for E2E testing. Stores are attached to window after component mounts.
 */
export default function StoreProvider() {
  useEffect(() => {
    // Expose stores to window for E2E testing
    if (typeof window !== 'undefined') {
      (window as any).useLayerStore = useLayerStore;
      (window as any).useSettingsStore = useSettingsStore;
    }
  }, []);
  
  return null;
}
