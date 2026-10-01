"use client";

import { useState } from "react";
import { useInitializedSettingsStore } from "../../hooks/useInitializedSettingsStore";
import { ChevronDown, ChevronUp } from "lucide-react";
import { OGCAPIBackend } from "../../stores/settingsStore";

const EMPTY_BACKEND: Omit<OGCAPIBackend, "enabled"> = {
  url: "",
  name: "",
  description: "",
};

export default function OGCAPISettingsComponent() {
  const [collapsed, setCollapsed] = useState(true);
  const [newBackend, setNewBackend] =
    useState<Omit<OGCAPIBackend, "enabled">>(EMPTY_BACKEND);

  const backends = useInitializedSettingsStore((s) => s.ogcapi_backends) || [];
  const addBackend = useInitializedSettingsStore((s) => s.addOGCAPIBackend);
  const removeBackend = useInitializedSettingsStore(
    (s) => s.removeOGCAPIBackend,
  );
  const toggleBackend = useInitializedSettingsStore(
    (s) => s.toggleOGCAPIBackend,
  );
  const toggleInsecure = useInitializedSettingsStore(
    (s) => s.toggleOGCAPIBackendInsecure,
  );

  const canAdd = newBackend.url.trim() !== "" && newBackend.name.trim() !== "";

  const handleAdd = () => {
    if (!canAdd) return;
    addBackend({
      ...newBackend,
      url: newBackend.url.trim(),
      name: newBackend.name.trim(),
      enabled: true,
    });
    setNewBackend(EMPTY_BACKEND);
  };

  const inputClass =
    "w-full border border-primary-300 dark:border-primary-700 rounded p-2 bg-primary-50 dark:bg-primary-950 text-primary-900 dark:text-primary-100";

  return (
    <div className="border border-primary-300 rounded bg-primary-50 dark:bg-neutral-900 overflow-hidden">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between px-4 py-3 bg-primary-100 hover:bg-primary-200 dark:bg-primary-900 dark:hover:bg-primary-800 transition-colors"
      >
        <h2 className="text-lg font-semibold text-primary-900 dark:text-primary-100">
          OGC API Backends
        </h2>
        {collapsed ? (
          <ChevronDown className="w-6 h-6 text-primary-600 dark:text-primary-400" />
        ) : (
          <ChevronUp className="w-6 h-6 text-primary-600 dark:text-primary-400" />
        )}
      </button>

      {!collapsed && (
        <div className="p-4 pt-0 space-y-6">
          <div className="space-y-4 pt-4">
            <h3 className="text-lg font-semibold text-primary-900 dark:text-primary-100">
              Add OGC API Backend
            </h3>
            <p className="text-sm text-primary-800 dark:text-primary-300">
              Register an OGC API (Features/Tiles) server so the assistant can
              search its collections and add them to the map.
            </p>
            <div className="space-y-3">
              <input
                value={newBackend.url}
                onChange={(e) =>
                  setNewBackend({ ...newBackend, url: e.target.value })
                }
                placeholder="OGC API base URL (e.g. https://ogcapi.example.com/v1)"
                className={inputClass}
              />
              <input
                value={newBackend.name}
                onChange={(e) =>
                  setNewBackend({ ...newBackend, name: e.target.value })
                }
                placeholder="Name (required)"
                className={inputClass}
              />
              <input
                value={newBackend.description || ""}
                onChange={(e) =>
                  setNewBackend({ ...newBackend, description: e.target.value })
                }
                placeholder="Description (optional)"
                className={inputClass}
              />
              <button
                onClick={handleAdd}
                disabled={!canAdd}
                className={`bg-second-primary-600 text-white px-4 py-2 rounded font-medium shadow-sm ${!canAdd ? "opacity-50 cursor-not-allowed" : "hover:bg-second-primary-700 cursor-pointer"}`}
                style={{
                  backgroundColor: canAdd
                    ? "var(--second-primary-600)"
                    : undefined,
                }}
              >
                Add OGC API Backend
              </button>
            </div>
          </div>

          <div className="space-y-3 border-t border-primary-200 pt-6">
            <h3 className="text-lg font-semibold text-primary-900 dark:text-primary-100">
              Configured Backends
            </h3>
            {backends.length === 0 && (
              <p className="text-sm text-primary-800 dark:text-primary-300">
                No OGC API backends configured.
              </p>
            )}
            {backends.map((b) => (
              <div
                key={b.url}
                className="border border-primary-200 rounded p-4 bg-primary-50 dark:bg-neutral-800 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <h4 className="font-semibold text-primary-900 dark:text-primary-100">
                    {b.name}
                  </h4>
                  <button
                    onClick={() => removeBackend(b.url)}
                    className="text-sm text-red-600 hover:underline cursor-pointer"
                  >
                    Remove
                  </button>
                </div>
                <p className="text-sm text-primary-800 dark:text-primary-300 break-all">
                  {b.url}
                </p>
                {b.description && (
                  <p className="text-sm text-primary-900 dark:text-primary-200">
                    {b.description}
                  </p>
                )}
                <label className="flex items-center space-x-2 text-sm text-primary-900 dark:text-primary-100">
                  <input
                    type="checkbox"
                    checked={b.enabled}
                    onChange={() => toggleBackend(b.url)}
                  />
                  <span>Enabled</span>
                </label>
                <label className="flex items-center space-x-2 text-sm text-primary-900 dark:text-primary-100">
                  <input
                    type="checkbox"
                    checked={!!b.allow_insecure}
                    onChange={() => toggleInsecure(b.url)}
                  />
                  <span>Allow insecure SSL (trusted dev servers only)</span>
                </label>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
