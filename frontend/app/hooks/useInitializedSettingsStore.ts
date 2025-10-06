import { useEffect, useRef } from "react";
import { useSettingsStore, SettingsState } from "../stores/settingsStore";

export function useInitializedSettingsStore<T>(
  selector: (state: SettingsState) => T,
): T {
  const value = useSettingsStore(selector);
  const initializeIfNeeded = useSettingsStore((s) => s.initializeIfNeeded);
  const initialized = useSettingsStore((s) => s.initialized);
  const initStartedRef = useRef(false);

  useEffect(() => {
    // Only call initialization once per component lifecycle
    // and only if not already initialized
    if (!initialized && !initStartedRef.current) {
      initStartedRef.current = true;
      initializeIfNeeded();
    }
  }, [initialized, initializeIfNeeded]);

  return value;
}
