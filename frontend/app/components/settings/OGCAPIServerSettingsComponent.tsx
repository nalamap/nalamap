"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Plus, X } from "lucide-react";

import { useInitializedSettingsStore } from "../../hooks/useInitializedSettingsStore";
import { OGCAPIServer } from "../../stores/settingsStore";

export default function OGCAPIServerSettingsComponent() {
  const [collapsed, setCollapsed] = useState(true);
  const [selectedExampleServer, setSelectedExampleServer] = useState("");
  const [newServer, setNewServer] = useState<Omit<OGCAPIServer, "enabled">>({
    url: "",
    name: "",
    description: "",
    api_key: "",
    headers: {},
  });
  const [newHeaderKey, setNewHeaderKey] = useState("");
  const [newHeaderValue, setNewHeaderValue] = useState("");

  const ogcapiServers = useInitializedSettingsStore((s) => s.ogcapi_servers);
  const addOGCAPIServer = useInitializedSettingsStore((s) => s.addOGCAPIServer);
  const removeOGCAPIServer = useInitializedSettingsStore((s) => s.removeOGCAPIServer);
  const toggleOGCAPIServer = useInitializedSettingsStore((s) => s.toggleOGCAPIServer);
  const availableExamples = useInitializedSettingsStore(
    (s) => s.available_example_ogcapi_servers,
  );

  const handleAddExample = () => {
    const selected = availableExamples.find((server) => server.url === selectedExampleServer);
    if (!selected) return;

    addOGCAPIServer({
      url: selected.url,
      name: selected.name,
      description: selected.description,
      enabled: true,
    });
    setSelectedExampleServer("");
  };

  const handleAddCustom = () => {
    if (!newServer.url.trim()) return;

    addOGCAPIServer({
      ...newServer,
      enabled: true,
    });
    setNewServer({ url: "", name: "", description: "", api_key: "", headers: {} });
    setNewHeaderKey("");
    setNewHeaderValue("");
  };

  const handleAddHeader = () => {
    if (!newHeaderKey.trim() || !newHeaderValue.trim()) return;
    setNewServer({
      ...newServer,
      headers: {
        ...newServer.headers,
        [newHeaderKey]: newHeaderValue,
      },
    });
    setNewHeaderKey("");
    setNewHeaderValue("");
  };

  const handleRemoveHeader = (key: string) => {
    const remaining = { ...(newServer.headers || {}) };
    delete remaining[key];
    setNewServer({ ...newServer, headers: remaining });
  };

  return (
    <div className="obsidian-panel settings-panel">
      <button
        type="button"
        onClick={() => setCollapsed(!collapsed)}
        className="obsidian-panel-header settings-panel-header"
      >
        <h2 className="obsidian-heading text-lg">
          OGC API Servers
        </h2>
        {collapsed ? (
          <ChevronDown className="h-6 w-6" />
        ) : (
          <ChevronUp className="h-6 w-6" />
        )}
      </button>

      {!collapsed && (
        <div className="obsidian-panel-body settings-panel-body space-y-6">
          {availableExamples && availableExamples.length > 0 && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-primary-900 dark:text-primary-100">
                Example OGC API Servers
              </h3>
              <div className="flex space-x-2 mb-4">
                <select
                  value={selectedExampleServer}
                  onChange={(e) => setSelectedExampleServer(e.target.value)}
                  className="obsidian-select flex-grow"
                >
                  <option value="">Select an example OGC API server</option>
                  {availableExamples.map((server) => (
                    <option key={server.url} value={server.url}>
                      {server.name} - {server.url}
                    </option>
                  ))}
                </select>
                <button
                  onClick={handleAddExample}
                  disabled={!selectedExampleServer}
                  className={`obsidian-button-primary px-4 py-2 ${!selectedExampleServer ? "opacity-50 cursor-not-allowed" : ""}`}
                >
                  Add Example Server
                </button>
              </div>
            </div>
          )}

          <div
            className={`space-y-4 ${availableExamples && availableExamples.length > 0 ? "pt-6" : ""}`}
          >
            <h3 className="text-lg font-semibold text-primary-900 dark:text-primary-100">
              Add Custom OGC API Server
            </h3>
            <div className="space-y-3">
              <input
                value={newServer.url}
                onChange={(e) => setNewServer({ ...newServer, url: e.target.value })}
                placeholder="OGC API base URL (e.g., http://ogcapi:8000/v1 for Docker, http://localhost:8081/v1 locally)"
                className="obsidian-input"
              />
              <input
                value={newServer.name}
                onChange={(e) => setNewServer({ ...newServer, name: e.target.value })}
                placeholder="Name (optional)"
                className="obsidian-input"
              />
              <textarea
                value={newServer.description}
                onChange={(e) => setNewServer({ ...newServer, description: e.target.value })}
                placeholder="Description (optional)"
                className="obsidian-textarea h-20"
              />
              <input
                type="password"
                value={newServer.api_key || ""}
                onChange={(e) => setNewServer({ ...newServer, api_key: e.target.value })}
                placeholder="API Key (optional)"
                className="obsidian-input"
              />

              <div className="space-y-2">
                <h4 className="text-sm font-semibold text-primary-900 dark:text-primary-100">
                  Custom Headers (optional)
                </h4>
                {newServer.headers && Object.keys(newServer.headers).length > 0 && (
                  <div className="space-y-1 mb-2">
                    {Object.entries(newServer.headers).map(([key, value]) => (
                      <div
                        key={key}
                        className="obsidian-card flex items-center justify-between px-3 py-2"
                      >
                        <div className="flex-1 font-mono text-sm text-primary-900 dark:text-primary-100">
                          <span className="font-semibold">{key}:</span> {value}
                        </div>
                        <button
                          onClick={() => handleRemoveHeader(key)}
                          className="ml-2 text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                          aria-label={`Remove header ${key}`}
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                <div className="flex space-x-2">
                  <input
                    value={newHeaderKey}
                    onChange={(e) => setNewHeaderKey(e.target.value)}
                    placeholder="Header name"
                    className="obsidian-input flex-1"
                  />
                  <input
                    value={newHeaderValue}
                    onChange={(e) => setNewHeaderValue(e.target.value)}
                    placeholder="Header value"
                    className="obsidian-input flex-1"
                  />
                  <button
                    onClick={handleAddHeader}
                    disabled={!newHeaderKey.trim() || !newHeaderValue.trim()}
                    className={`obsidian-button-primary px-3 py-2 ${!newHeaderKey.trim() || !newHeaderValue.trim() ? "opacity-50 cursor-not-allowed" : ""}`}
                    aria-label="Add header"
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <button
                onClick={handleAddCustom}
                disabled={!newServer.url.trim()}
                className={`obsidian-button-primary px-4 py-2 ${!newServer.url.trim() ? "opacity-50 cursor-not-allowed" : ""}`}
              >
                Add OGC API Server
              </button>
            </div>
          </div>

          <div className="space-y-3 pt-6">
            <h3 className="text-lg font-semibold text-primary-900 dark:text-primary-100">
              Configured OGC API Servers
            </h3>
            {ogcapiServers && ogcapiServers.length > 0 ? (
              <ul className="space-y-3">
                {ogcapiServers.map((server, i) => (
                  <li
                    key={i}
                    className="obsidian-card flex justify-between items-center"
                  >
                    <label className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={server.enabled}
                        onChange={() => toggleOGCAPIServer(server.url)}
                        className="form-checkbox h-4 w-4 text-tertiary-600"
                      />
                      <div className="flex flex-col">
                        <span className="text-primary-900 dark:text-primary-100 font-medium">
                          {server.name || "Unnamed Server"}
                        </span>
                        <span className="text-sm text-primary-700 dark:text-primary-300">
                          {server.url}
                        </span>
                        {server.description && (
                          <span className="text-xs text-primary-600 dark:text-primary-400 mt-1">
                            {server.description}
                          </span>
                        )}
                      </div>
                    </label>
                    <button
                      onClick={() => removeOGCAPIServer(server.url)}
                      className="obsidian-button-danger px-3 py-2 text-sm"
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-primary-700 dark:text-primary-300">
                No OGC API servers configured.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
