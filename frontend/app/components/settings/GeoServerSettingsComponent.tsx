"use client";

import { useState } from "react";
import { useInitializedSettingsStore } from "../../hooks/useInitializedSettingsStore";
import { ChevronDown, ChevronUp } from "lucide-react";
import { GeoServerBackend } from "../../stores/settingsStore";

interface GeoServerSettingsComponentProps {
  newBackend: Omit<GeoServerBackend, "enabled">;
  setNewBackend: (backend: Omit<GeoServerBackend, "enabled">) => void;
  handleAddBackend: () => void;
  selectedExampleGeoServer: string;
  setSelectedExampleGeoServer: (url: string) => void;
  handleAddExampleGeoServer: () => void;
  backendLoading: boolean;
  backendError: string | null;
  backendSuccess: string | null;
  embeddingStatus: {
    [url: string]: {
      total: number;
      encoded: number;
      percentage: number;
      state: string;
      in_progress: boolean;
      complete: boolean;
      error: string | null;
      error_type?: string | null;
      error_details?: string | null;
    };
  };
  interpolatedProgress: {
    [url: string]: {
      encoded: number;
      displayEncoded: number;
      percentage: number;
      velocity: number;
      lastUpdate: number;
    };
  };
  handleToggleBackendInsecure?: (url: string) => void;
}

export default function GeoServerSettingsComponent({
  newBackend,
  setNewBackend,
  handleAddBackend,
  selectedExampleGeoServer,
  setSelectedExampleGeoServer,
  handleAddExampleGeoServer,
  backendLoading,
  backendError,
  backendSuccess,
  embeddingStatus,
  interpolatedProgress,
  handleToggleBackendInsecure,
}: GeoServerSettingsComponentProps) {
  const [collapsed, setCollapsed] = useState(true);

  const backends = useInitializedSettingsStore((s) => s.geoserver_backends);
  const removeBackend = useInitializedSettingsStore((s) => s.removeBackend);
  const toggleBackend = useInitializedSettingsStore((s) => s.toggleBackend);
  const toggleBackendInsecureStore = useInitializedSettingsStore(
    (s) => s.toggleBackendInsecure,
  );
  
  // Use the handler if provided, otherwise fall back to store action
  const toggleBackendInsecure = handleToggleBackendInsecure || toggleBackendInsecureStore;
  const availableExampleGeoServers = useInitializedSettingsStore(
    (s) => s.available_example_geoservers,
  );

  return (
    <div className="border border-primary-300 rounded bg-primary-50 dark:bg-neutral-900 overflow-hidden">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between px-4 py-3 bg-primary-100 hover:bg-primary-200 dark:bg-primary-900 dark:hover:bg-primary-800 transition-colors"
      >
        <h2 className="text-lg font-semibold text-primary-900 dark:text-primary-100">
          GeoServer Backends
        </h2>
        {collapsed ? (
          <ChevronDown className="w-6 h-6 text-primary-600 dark:text-primary-400" />
        ) : (
          <ChevronUp className="w-6 h-6 text-primary-600 dark:text-primary-400" />
        )}
      </button>

      {!collapsed && (
        <div className="p-4 pt-0 space-y-6">
          {/* Example GeoServers Section */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-primary-900 dark:text-primary-100">
              Example GeoServers
            </h3>
            <p className="text-sm text-primary-800 dark:text-primary-300">
              Choose from publicly available example GeoServers to quickly get
              started with geospatial data.
            </p>
            <div className="flex space-x-2 mb-4">
              <select
                value={selectedExampleGeoServer}
                onChange={(e) => setSelectedExampleGeoServer(e.target.value)}
                className="border border-primary-300 dark:border-primary-700 rounded p-2 flex-grow bg-primary-50 dark:bg-primary-950 text-primary-900 dark:text-primary-100"
              >
                <option value="" className="bg-primary-50 text-primary-900">Select an example GeoServer</option>
                {availableExampleGeoServers.map((geoserver) => (
                  <option key={geoserver.url} value={geoserver.url} className="bg-primary-50 text-primary-900">
                    {geoserver.name} - {geoserver.url}
                  </option>
                ))}
              </select>
              <button
                onClick={handleAddExampleGeoServer}
                disabled={!selectedExampleGeoServer || backendLoading}
                className={`bg-second-primary-600 text-white px-4 py-2 rounded font-medium shadow-sm ${!selectedExampleGeoServer || backendLoading ? "opacity-50 cursor-not-allowed" : "hover:bg-second-primary-700 cursor-pointer"}`}
                style={{
                  backgroundColor:
                    !selectedExampleGeoServer || backendLoading
                      ? undefined
                      : "var(--second-primary-600)",
                }}
              >
                {backendLoading ? "Adding..." : "Add Example GeoServer"}
              </button>
            </div>
            {availableExampleGeoServers.map((geoserver) => (
              <div
                key={geoserver.url}
                className="border border-primary-200 rounded p-4 bg-primary-50 dark:bg-neutral-800 space-y-2"
              >
                <h4 className="text-lg font-semibold text-primary-900 dark:text-primary-100">
                  {geoserver.name}
                </h4>
                <p className="text-sm text-primary-800 dark:text-primary-300">{geoserver.url}</p>
                <div className="text-sm text-primary-900 dark:text-primary-200 prose prose-sm max-w-none">
                  {geoserver.description}
                </div>
              </div>
            ))}
          </div>

          {/* Custom Backend Section */}
          <div className="space-y-4 border-t border-primary-200 pt-6">
            <h3 className="text-lg font-semibold text-primary-900 dark:text-primary-100">
              Add Custom Backend
            </h3>
            <div className="space-y-3">
              <input
                value={newBackend.url}
                onChange={(e) =>
                  setNewBackend({ ...newBackend, url: e.target.value })
                }
                placeholder="GeoServer URL"
                className="border border-primary-300 dark:border-primary-700 rounded p-2 w-full bg-primary-50 dark:bg-primary-950 text-primary-900 dark:text-primary-100"
              />
              <input
                value={newBackend.name}
                onChange={(e) =>
                  setNewBackend({ ...newBackend, name: e.target.value })
                }
                placeholder="Name (optional)"
                className="border border-primary-300 dark:border-primary-700 rounded p-2 w-full bg-primary-50 dark:bg-primary-950 text-primary-900 dark:text-primary-100"
              />
              <textarea
                value={newBackend.description}
                onChange={(e) =>
                  setNewBackend({ ...newBackend, description: e.target.value })
                }
                placeholder="Description (optional)"
                className="border border-primary-300 dark:border-primary-700 rounded p-2 w-full h-20 bg-primary-50 dark:bg-primary-950 text-primary-900 dark:text-primary-100"
              />
              <input
                value={newBackend.username}
                onChange={(e) =>
                  setNewBackend({ ...newBackend, username: e.target.value })
                }
                placeholder="Username (optional)"
                className="border border-primary-300 dark:border-primary-700 rounded p-2 w-full bg-primary-50 dark:bg-primary-950 text-primary-900 dark:text-primary-100"
              />
              <input
                type="password"
                value={newBackend.password}
                onChange={(e) =>
                  setNewBackend({ ...newBackend, password: e.target.value })
                }
                placeholder="Password (optional)"
                className="border border-primary-300 dark:border-primary-700 rounded p-2 w-full bg-primary-50 dark:bg-primary-950 text-primary-900 dark:text-primary-100"
              />
              <label className="flex items-center space-x-2 p-3 bg-warning-50 dark:bg-warning-900/20 border border-warning-300 dark:border-warning-700 rounded">
                <input
                  type="checkbox"
                  checked={newBackend.allow_insecure || false}
                  onChange={(e) =>
                    setNewBackend({
                      ...newBackend,
                      allow_insecure: e.target.checked,
                    })
                  }
                  className="form-checkbox h-4 w-4 text-warning-600"
                />
                <span className="text-sm text-gray-900 dark:text-warning-300 flex items-center">
                  Allow insecure connections (expired/self-signed SSL certificates)
                  <span className="ml-1 text-base" title="Warning: Only enable for trusted servers">
                    ⚠️
                  </span>
                </span>
              </label>
              <button
                onClick={handleAddBackend}
                disabled={backendLoading}
                className={`bg-second-primary-600 text-white px-4 py-2 rounded font-medium shadow-sm ${backendLoading ? "opacity-50 cursor-not-allowed" : "hover:bg-second-primary-700 cursor-pointer"}`}
                style={{
                  backgroundColor: backendLoading
                    ? undefined
                    : "var(--second-primary-600)",
                }}
              >
                {backendLoading ? "Checking…" : "Add Backend"}
              </button>
              {backendLoading && (
                <div className="w-full mt-2 h-2 bg-primary-200 rounded">
                  <div className="h-2 bg-second-primary-500 rounded animate-pulse w-full" />
                </div>
              )}
              {backendError && (
                <p className="text-red-600 text-sm font-medium">
                  {backendError}
                </p>
              )}
              {backendSuccess && (
                <p className="text-tertiary-600 text-sm font-medium">
                  {backendSuccess}
                </p>
              )}
            </div>
          </div>

          {/* Backend List */}
          <div className="space-y-3 border-t border-primary-200 pt-6">
            <h3 className="text-lg font-semibold text-primary-900 dark:text-primary-100">
              Configured Backends
            </h3>
            <ul className="space-y-3">
              {backends.map((b, i) => (
                <li
                  key={i}
                  className="flex justify-between items-center border border-primary-200 rounded p-4 bg-primary-50 dark:bg-neutral-800"
                >
                  <label className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={b.enabled}
                      onChange={() => toggleBackend(b.url)}
                      className="form-checkbox h-5 w-5 text-tertiary-600"
                    />
                    <div className="flex-1">
                      <p
                        className={`font-medium ${b.enabled ? "text-primary-900 dark:text-primary-100" : "text-neutral-600 dark:text-primary-600"}`}
                      >
                        <strong>{b.name || "URL"}:</strong> {b.url}
                      </p>
                      {b.description && (
                        <p
                          className={`${b.enabled ? "text-primary-800 dark:text-primary-300" : "text-neutral-600 dark:text-primary-600"} text-sm`}
                        >
                          {b.description}
                        </p>
                      )}
                      {b.username && (
                        <p
                          className={`${b.enabled ? "text-primary-900 dark:text-primary-100" : "text-neutral-600 dark:text-primary-600"} text-sm`}
                        >
                          <strong>Username:</strong> {b.username}
                        </p>
                      )}

                      {/* Embedding Progress */}
                      {b.enabled &&
                        embeddingStatus[b.url] &&
                        (embeddingStatus[b.url].total > 0 ||
                          embeddingStatus[b.url].state === "waiting" ||
                          embeddingStatus[b.url].state === "unknown") && (
                          <div className="mt-2">
                            <div className="flex justify-between items-center text-xs mb-1">
                              <span
                                className={
                                  embeddingStatus[b.url].complete ||
                                  embeddingStatus[b.url].state === "completed"
                                    ? "text-tertiary-600 dark:text-tertiary-400 font-medium"
                                    : embeddingStatus[b.url].state === "error"
                                      ? "text-red-600 dark:text-red-400 font-medium"
                                      : embeddingStatus[b.url].state ===
                                          "waiting"
                                        ? "text-secondary-600 dark:text-secondary-400 font-medium"
                                        : embeddingStatus[b.url].state ===
                                            "unknown"
                                          ? "text-primary-800 dark:text-primary-400 font-medium"
                                          : "text-second-primary-600 dark:text-second-primary-400 font-medium"
                                }
                              >
                                {embeddingStatus[b.url].complete ||
                                embeddingStatus[b.url].state === "completed"
                                  ? "✓ Embedding complete"
                                  : embeddingStatus[b.url].state === "error"
                                    ? "✗ Error: " +
                                      (embeddingStatus[b.url].error ||
                                        "Unknown error")
                                    : embeddingStatus[b.url].state === "waiting"
                                      ? "⏱️ Waiting to start"
                                      : embeddingStatus[b.url].state ===
                                          "unknown"
                                        ? "⏸️ Status unknown (checking...)"
                                        : "⏳ Embedding in progress"}
                                {embeddingStatus[b.url].total > 0 && (
                                  <>
                                    :{" "}
                                    {interpolatedProgress[b.url]
                                      ? Math.floor(
                                          interpolatedProgress[b.url].displayEncoded,
                                        )
                                      : embeddingStatus[b.url].encoded}{" "}
                                    / {embeddingStatus[b.url].total} layers
                                  </>
                                )}
                              </span>
                              {embeddingStatus[b.url].total > 0 && (
                                <span className="text-primary-600 font-medium">
                                  {interpolatedProgress[b.url]
                                    ? interpolatedProgress[
                                        b.url
                                      ].percentage.toFixed(1)
                                    : embeddingStatus[b.url].percentage}
                                  %
                                </span>
                              )}
                            </div>
                            {embeddingStatus[b.url].state !== "error" &&
                              (embeddingStatus[b.url].total > 0 ||
                                embeddingStatus[b.url].state === "waiting" ||
                                embeddingStatus[b.url].state === "unknown") && (
                                <div
                                  className="w-full h-2 bg-primary-200 rounded overflow-hidden"
                                  style={{
                                    backgroundColor: "var(--primary-200)",
                                  }}
                                >
                                  <div
                                    className={`h-full transition-all duration-100 ${
                                      embeddingStatus[b.url].state === "waiting"
                                        ? "animate-pulse"
                                        : ""
                                    }`}
                                    style={{
                                      width: `${
                                        embeddingStatus[b.url].state ===
                                          "waiting" ||
                                        embeddingStatus[b.url].state ===
                                          "unknown"
                                          ? 5
                                          : interpolatedProgress[b.url]
                                            ? interpolatedProgress[b.url]
                                                .percentage
                                            : embeddingStatus[b.url].percentage
                                      }%`,
                                      backgroundColor:
                                        embeddingStatus[b.url].complete ||
                                        embeddingStatus[b.url].state ===
                                          "completed"
                                          ? "var(--tertiary-500)"
                                          : embeddingStatus[b.url].state ===
                                              "waiting"
                                            ? "var(--secondary-500)"
                                            : "var(--second-primary-500)",
                                    }}
                                  />
                                </div>
                              )}
                          </div>
                        )}

                      {/* Enhanced Error Display */}
                      {b.enabled &&
                        embeddingStatus[b.url] &&
                        embeddingStatus[b.url].state === "error" && (
                          <div className="mt-2 bg-error-100 dark:bg-error-900 border-l-4 border-l-error-500 border border-error-300 dark:border-error-700 rounded shadow-sm overflow-hidden">
                            <div className="p-3 bg-error-100 dark:bg-error-900">
                              <p className="text-sm font-semibold text-error-900 dark:text-error-100 flex items-center gap-2">
                                <span className="text-lg text-error-600 dark:text-error-300">✗</span>
                                <span>{embeddingStatus[b.url].error || "Connection error"}</span>
                              </p>
                              {embeddingStatus[b.url].error_details && (
                                <details className="mt-3 group">
                                  <summary className="text-xs text-gray-900 dark:text-error-200 cursor-pointer hover:text-error-900 dark:hover:text-error-100 font-medium list-none flex items-center gap-1.5 select-none">
                                    <span className="inline-block transition-transform group-open:rotate-90">▶</span>
                                    Show technical details
                                  </summary>
                                  <pre className="text-xs mt-2 p-2 bg-error-200 dark:bg-error-800 border border-error-300 dark:border-error-600 rounded overflow-x-auto whitespace-pre-wrap text-gray-900 dark:text-error-100 font-mono">
                                    {embeddingStatus[b.url].error_details}
                                  </pre>
                                </details>
                              )}
                            </div>
                            {embeddingStatus[b.url].error_type === "ssl_certificate" && (
                              <div className="px-3 py-2 bg-error-200 dark:bg-error-800 border-t border-error-300 dark:border-error-600">
                                <p className="text-xs text-gray-900 dark:text-error-100 flex items-start gap-1.5">
                                  <span className="text-base shrink-0">💡</span>
                                  <span>Try enabling "Allow insecure connections" below</span>
                                </p>
                              </div>
                            )}
                          </div>
                        )}

                      {/* Allow Insecure Toggle */}
                      {b.enabled && (
                        <div className="mt-2">
                          <label className="flex items-center space-x-2 text-xs p-2.5 bg-warning-100 dark:bg-warning-900 border-l-4 border-l-warning-500 border border-warning-300 dark:border-warning-700 rounded cursor-pointer hover:bg-warning-200 dark:hover:bg-warning-800 transition-colors shadow-sm">
                            <input
                              type="checkbox"
                              checked={b.allow_insecure || false}
                              onChange={() => toggleBackendInsecure(b.url)}
                              className="form-checkbox h-4 w-4 text-warning-600 rounded border-gray-400"
                            />
                            <span className="text-gray-900 dark:text-warning-100 flex items-center gap-1.5 font-medium">
                              <span className="text-base">⚠️</span>
                              <span>Allow insecure connections</span>
                              <span
                                className="text-[10px] text-gray-700 dark:text-warning-200 font-normal"
                                title="Bypass SSL certificate verification (expired/self-signed). Only use for trusted servers."
                              >
                                (expired/self-signed SSL)
                              </span>
                            </span>
                          </label>
                        </div>
                      )}
                    </div>
                  </label>
                  <button
                    onClick={() => removeBackend(b.url)}
                    className="text-red-600 hover:underline ml-2 font-medium"
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
