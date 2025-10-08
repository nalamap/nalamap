import { useEffect, useRef } from "react";
import { useSettingsStore, SettingsState } from "../stores/settingsStore";

// Global flag to ensure initialization happens only once across ALL hook instances
// This prevents race conditions when multiple components use the hook simultaneously
let globalInitStarted = false;

export function useInitializedSettingsStore<T>(
  selector: (state: SettingsState) => T,
): T {
  const value = useSettingsStore(selector);
  const initializeIfNeeded = useSettingsStore((s) => s.initializeIfNeeded);
  const initialized = useSettingsStore((s) => s.initialized);

  useEffect(() => {
    // Use global flag to ensure only ONE initialization attempt across all hook instances
    if (!initialized && !globalInitStarted) {
      globalInitStarted = true;
      initializeIfNeeded();
    }
  }, [initialized, initializeIfNeeded]);

  return value;
}
