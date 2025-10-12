"use client";

import { useEffect } from "react";
import { useSettingsStore } from "../stores/settingsStore";

/**
 * Component that initializes settings on app load.
 * This ensures color settings and other configuration are loaded early,
 * preventing FOUC (Flash of Unstyled Content) when custom colors are set.
 * 
 * This component renders nothing - it only triggers initialization.
 */
export default function SettingsInitializer() {
  const initializeIfNeeded = useSettingsStore((s) => s.initializeIfNeeded);
  const initialized = useSettingsStore((s) => s.initialized);

  useEffect(() => {
    // Initialize settings as soon as the app loads
    if (!initialized) {
      initializeIfNeeded();
    }
  }, [initialized, initializeIfNeeded]);

  return null; // This component doesn't render anything
}
