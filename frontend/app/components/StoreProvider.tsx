'use client';

import { useLayerStore } from '../stores/layerStore';
import { useSettingsStore } from '../stores/settingsStore';

// Expose stores to window immediately for E2E testing
if (typeof window !== 'undefined') {
  (window as any).useLayerStore = useLayerStore;
  (window as any).useSettingsStore = useSettingsStore;
}

/**
 * Client component that ensures stores are initialized and exposed
 * for E2E testing.
 */
export default function StoreProvider() {
  // This component just needs to exist to ensure the module is loaded
  return null;
}
