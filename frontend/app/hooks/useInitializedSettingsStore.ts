import { useEffect } from "react";
import { useSettingsStore, SettingsState } from "../stores/settingsStore";

export function useInitializedSettingsStore<T>(
  selector: (state: SettingsState) => T,
): T {
  const value = useSettingsStore(selector);
  const initializeIfNeeded = useSettingsStore((s) => s.initializeIfNeeded);

  useEffect(() => {
    initializeIfNeeded();
  }, []);

  return value;
}
