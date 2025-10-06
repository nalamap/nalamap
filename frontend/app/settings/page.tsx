"use client";

import React, { useState } from "react";
import Sidebar from "../components/sidebar/Sidebar";
import { GeoServerBackend, SettingsSnapshot } from "../stores/settingsStore";

import { useInitializedSettingsStore } from "../hooks/useInitializedSettingsStore";
import { getApiBase } from "../utils/apiBase";

type BackendPrefetchInput = Omit<GeoServerBackend, "enabled"> & {
  enabled?: boolean;
};

export default function SettingsPage() {
  // store hooks
  const portals = useInitializedSettingsStore((s) => s.search_portals);
  const addPortal = useInitializedSettingsStore((s) => s.addPortal);
  const removePortal = useInitializedSettingsStore((s) => s.removePortal);
  const togglePortal = useInitializedSettingsStore((s) => s.togglePortal);

  const backends = useInitializedSettingsStore((s) => s.geoserver_backends);
  const addBackend = useInitializedSettingsStore((s) => s.addBackend);
  const removeBackend = useInitializedSettingsStore((s) => s.removeBackend);
  const toggleBackend = useInitializedSettingsStore((s) => s.toggleBackend);

  const modelSettings = useInitializedSettingsStore((s) => s.model_settings);
  const setModelProvider = useInitializedSettingsStore(
    (s) => s.setModelProvider,
  );
  const setModelName = useInitializedSettingsStore((s) => s.setModelName);
  const setMaxTokens = useInitializedSettingsStore((s) => s.setMaxTokens);
  const setSystemPrompt = useInitializedSettingsStore((s) => s.setSystemPrompt);

  const tools = useInitializedSettingsStore((s) => s.tools);
  const addToolConfig = useInitializedSettingsStore((s) => s.addToolConfig);
  const removeToolConfig = useInitializedSettingsStore(
    (s) => s.removeToolConfig,
  );
  const toggleToolConfig = useInitializedSettingsStore(
    (s) => s.toggleToolConfig,
  );
  const setToolPromptOverride = useInitializedSettingsStore(
    (s) => s.setToolPromptOverride,
  );

  // available & fetched options
  const availableTools = useInitializedSettingsStore((s) => s.available_tools);
  const availablePortals = useInitializedSettingsStore(
    (s) => s.available_search_portals,
  );
  const availableProviders = useInitializedSettingsStore(
    (s) => s.available_model_providers,
  );
  const availableModelNames = useInitializedSettingsStore(
    (s) => s.available_model_names,
  );
  const toolOptions = useInitializedSettingsStore((s) => s.tool_options);
  const modelOptions = useInitializedSettingsStore((s) => s.model_options);

  const setAvailableTools = useInitializedSettingsStore(
    (s) => s.setAvailableTools,
  );
  const setAvailableSearchPortals = useInitializedSettingsStore(
    (s) => s.setAvailableSearchPortals,
  );
  const setAvailableModelProviders = useInitializedSettingsStore(
    (s) => s.setAvailableModelProviders,
  );
  const setAvailableModelNames = useInitializedSettingsStore(
    (s) => s.setAvailableModelNames,
  );
  const setToolOptions = useInitializedSettingsStore((s) => s.setToolOptions);
  const setModelOptions = useInitializedSettingsStore((s) => s.setModelOptions);

  const setSessionId = useInitializedSettingsStore((s) => s.setSessionId);

  // Get Seetings
  const getSettings = useInitializedSettingsStore((s) => s.getSettings);
  const setSettings = useInitializedSettingsStore((s) => s.setSettings);
  // local state
  const [newPortal, setNewPortal] = useState("");
  const [newBackend, setNewBackend] = useState<
    Omit<GeoServerBackend, "enabled">
  >({ url: "", name: "", description: "", username: "", password: "" });
  const [newToolName, setNewToolName] = useState("");
  const [backendError, setBackendError] = useState<string | null>(null);
  const [backendSuccess, setBackendSuccess] = useState<string | null>(null);
  const [backendLoading, setBackendLoading] = useState(false);
  const [importingBackends, setImportingBackends] = useState(false);
  const [embeddingStatus, setEmbeddingStatus] = useState<{
    [url: string]: {
      total: number;
      encoded: number;
      percentage: number;
      state: string;
      in_progress: boolean;
      complete: boolean;
      error: string | null;
    };
  }>({});

  const API_BASE_URL = getApiBase();

  const normalizeBackend = (
    backend: BackendPrefetchInput,
  ): GeoServerBackend => {
    let url = backend.url.trim();

    // Add https:// if protocol is missing to prevent connection errors
    if (url && !url.match(/^https?:\/\//i)) {
      url = `https://${url}`;
    }

    return {
      url,
      name: backend.name?.trim() || backend.name || undefined,
      description: backend.description,
      username: backend.username,
      password: backend.password,
      enabled: backend.enabled ?? true,
    };
  };

  const prefetchBackend = async (
    backend: BackendPrefetchInput,
  ): Promise<{ backend: GeoServerBackend; totalLayers: number }> => {
    const normalized = normalizeBackend(backend);
    if (!normalized.url) {
      throw new Error("Please provide a GeoServer URL.");
    }

    let responseJson: any = null;
    try {
      const res = await fetch(`${API_BASE_URL}/settings/geoserver/preload`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
          backend: normalized,
          session_id: getSettings().session_id || undefined,
        }),
      });

      try {
        responseJson = await res.json();
      } catch {
        responseJson = null;
      }

      if (!res.ok) {
        let message = res.statusText || "Failed to contact GeoServer backend.";
        if (responseJson?.detail) {
          message = responseJson.detail;
        }
        throw new Error(message);
      }
    } catch (err) {
      if (err instanceof Error) {
        throw err;
      }
      throw new Error("Failed to preload GeoServer backend.");
    }

    if (responseJson?.session_id) {
      setSessionId(responseJson.session_id);
    }

    return {
      backend: normalized,
      totalLayers:
        typeof responseJson?.total_layers === "number"
          ? responseJson.total_layers
          : 0,
    };
  };

  const applyImportedSettings = async (snapshot: SettingsSnapshot) => {
    setBackendError(null);
    setBackendSuccess(null);

    // Preserve current model_settings, tools, and options if not present in snapshot
    const currentSettings = getSettings();

    const sanitized: SettingsSnapshot = {
      search_portals: snapshot.search_portals || [],
      geoserver_backends: [], // Will be populated via prefetch
      model_settings: snapshot.model_settings || currentSettings.model_settings,
      tools: snapshot.tools || currentSettings.tools,
      tool_options: snapshot.tool_options || currentSettings.tool_options,
      model_options: snapshot.model_options || currentSettings.model_options,
      session_id: undefined, // Ignore imported session_id
    };
    setSettings(sanitized);

    const importedBackends = snapshot.geoserver_backends || [];
    if (importedBackends.length === 0) {
      setBackendSuccess("Settings imported successfully.");
      return;
    }

    setBackendLoading(true);
    setImportingBackends(true);
    try {
      const failures: string[] = [];
      let successCount = 0;

      for (const backend of importedBackends) {
        try {
          const result = await prefetchBackend(backend);
          addBackend(result.backend);
          successCount += 1;
        } catch (err) {
          console.error("Failed to preload imported GeoServer backend", err);
          failures.push(backend.url);
        }
      }

      if (successCount > 0) {
        setBackendSuccess(
          `Prefetched ${successCount} imported backend${successCount === 1 ? "" : "s"} successfully.`,
        );
      } else {
        setBackendSuccess(
          "Settings imported. Unable to preload any GeoServer backends.",
        );
      }

      if (failures.length > 0) {
        setBackendError(`Failed to preload: ${failures.join(", ")}`);
      }
    } finally {
      setBackendLoading(false);
      setImportingBackends(false);
    }
  };

  const handleAddBackend = async () => {
    setBackendError(null);
    setBackendSuccess(null);

    setBackendLoading(true);
    setImportingBackends(false);
    try {
      // Normalize and add backend to settings immediately
      const normalizedBackend = normalizeBackend({
        ...newBackend,
        enabled: true,
      });
      addBackend(normalizedBackend);

      // Initialize embedding status to 'waiting' state so UI shows immediately
      setEmbeddingStatus((prev) => ({
        ...prev,
        [normalizedBackend.url]: {
          total: 0,
          encoded: 0,
          percentage: 0,
          state: "waiting",
          in_progress: false,
          complete: false,
          error: null,
        },
      }));

      setNewBackend({
        url: "",
        name: "",
        description: "",
        username: "",
        password: "",
      });

      // Start preloading in background - user can now navigate away
      const { totalLayers } = await prefetchBackend(normalizedBackend);
      setBackendSuccess(
        `Prefetched ${totalLayers} layer${totalLayers === 1 ? "" : "s"} successfully.`,
      );
    } catch (err: any) {
      setBackendError(err?.message || "Failed to preload GeoServer backend.");
    } finally {
      setBackendLoading(false);
    }
  };

  // Fetch embedding status for enabled backends
  const fetchEmbeddingStatus = async () => {
    const enabledBackends = backends.filter((b) => b.enabled);
    if (enabledBackends.length === 0) {
      setEmbeddingStatus({});
      return;
    }

    const backendUrls = enabledBackends.map((b) => b.url).join(",");
    try {
      const res = await fetch(
        `${API_BASE_URL}/settings/geoserver/embedding-status?backend_urls=${encodeURIComponent(backendUrls)}`,
        {
          credentials: "include",
        },
      );
      if (res.ok) {
        const data = await res.json();
        setEmbeddingStatus(data.backends || {});
      }
    } catch (err) {
      // Silently fail - embedding status is optional
      console.error("Failed to fetch embedding status:", err);
    }
  };

  // Poll embedding status every 10 seconds when there are enabled backends
  React.useEffect(() => {
    fetchEmbeddingStatus();

    // Determine if we should continue polling
    const shouldPoll = () => {
      const enabledBackends = backends.filter((b) => b.enabled);
      if (enabledBackends.length === 0) {
        return false; // No backends to poll
      }

      // Check if any backend is in 'waiting' or 'processing' state
      const hasActiveBackends = enabledBackends.some((b) => {
        const status = embeddingStatus[b.url];
        return (
          status &&
          (status.state === "waiting" ||
            status.state === "processing" ||
            status.in_progress)
        );
      });

      return hasActiveBackends;
    };

    const interval = setInterval(() => {
      if (shouldPoll()) {
        fetchEmbeddingStatus();
      }
    }, 10000); // 10 seconds

    return () => clearInterval(interval);
  }, [backends.map((b) => b.url).join(","), embeddingStatus]);

  /** Export JSON */
  const exportSettings = () => {
    const dataStr = JSON.stringify(getSettings(), null, 2);
    const blob = new Blob([dataStr], { type: "application/json" });
    const href = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = href;
    link.download = "settings.json";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(href);
  };

  /** Import JSON */
  const importSettings = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      const content = evt.target?.result;
      if (typeof content !== "string") {
        alert("Invalid settings JSON");
        return;
      }

      let parsed: SettingsSnapshot;
      try {
        parsed = JSON.parse(content) as SettingsSnapshot;
      } catch {
        alert("Invalid settings JSON");
        return;
      }

      void (async () => {
        try {
          await applyImportedSettings(parsed);
        } catch (err) {
          console.error("Failed to import settings", err);
          alert("Failed to import settings");
        }
      })();
    };
    reader.readAsText(file);
    e.target.value = "";
  };

  return (
    <div className="relative h-screen w-screen overflow-hidden">
      <div className="fixed left-0 top-0 bottom-0 w-[4%] bg-gray-800">
        <Sidebar />
      </div>
      <main className="fixed top-0 left-[10%] right-[10%] bottom-0 w-[80%] overflow-auto p-6 space-y-8 scroll-smooth">
        <h1 className="text-3xl font-semibold">Settings</h1>
        {/* Export/Import Settings */}
        <div className="flex space-x-4 mb-8">
          <button
            onClick={exportSettings}
            className="bg-green-600 text-white px-4 py-2 rounded"
          >
            Export Settings
          </button>
          <label className="bg-blue-600 text-white px-4 py-2 rounded cursor-pointer">
            Import Settings
            <input
              type="file"
              accept="application/json"
              onChange={importSettings}
              className="hidden"
            />
          </label>
        </div>

        {/* Model Settings */}
        <section className="space-y-4">
          <h2 className="text-2xl">Model Settings</h2>
          <div className="grid grid-cols-2 gap-4">
            <select
              value={modelSettings.model_provider}
              onChange={(e) => {
                const prov = e.target.value;
                setModelProvider(prov);
                const models = modelOptions[prov] || [];
                const names = models.map((m) => m.name);
                setAvailableModelNames(names);
                if (models.length) {
                  setModelName(names[0]);
                  setMaxTokens(models[0].max_tokens);
                }
              }}
              className="border rounded p-2"
            >
              {availableProviders.map((prov) => (
                <option key={prov} value={prov}>
                  {prov}
                </option>
              ))}
            </select>
            <select
              value={modelSettings.model_name}
              onChange={(e) => setModelName(e.target.value)}
              className="border rounded p-2"
            >
              {availableModelNames.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            <input
              type="number"
              value={modelSettings.max_tokens}
              onChange={(e) => setMaxTokens(Number(e.target.value))}
              placeholder="Max Tokens"
              className="border rounded p-2"
            />
            <textarea
              value={modelSettings.system_prompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="System Prompt"
              className="border rounded p-2 col-span-2 h-24"
            />
          </div>
        </section>

        {/* Tools Configuration */}
        <section className="space-y-4">
          <h2 className="text-2xl">Tools Configuration</h2>
          <div className="flex space-x-2 mb-4">
            <select
              value={newToolName}
              onChange={(e) => setNewToolName(e.target.value)}
              className="border rounded p-2 flex-grow"
            >
              <option value="">Select tool to add</option>
              {availableTools.map((tool) => (
                <option key={tool} value={tool}>
                  {tool}
                </option>
              ))}
            </select>
            <button
              onClick={() => {
                newToolName && addToolConfig(newToolName);
                setNewToolName("");
              }}
              className="bg-blue-600 text-white px-4 py-2 rounded"
            >
              Add Tool
            </button>
          </div>
          <ul className="space-y-3">
            {tools.map((t, i) => (
              <li key={i} className="border rounded p-4 space-y-2">
                <div className="flex justify-between items-center">
                  <label className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={t.enabled}
                      onChange={() => toggleToolConfig(t.name)}
                      className="form-checkbox h-5 w-5 text-green-600"
                    />
                    <span
                      className={`${t.enabled ? "text-gray-900" : "text-gray-400"}`}
                    >
                      {t.name}
                    </span>
                  </label>
                  <button
                    onClick={() => removeToolConfig(t.name)}
                    className="text-red-600 hover:underline"
                  >
                    Remove
                  </button>
                </div>
                <textarea
                  value={t.prompt_override}
                  onChange={(e) =>
                    setToolPromptOverride(t.name, e.target.value)
                  }
                  placeholder="Prompt Override"
                  className="border rounded p-2 w-full h-20"
                />
              </li>
            ))}
          </ul>
        </section>

        {/* Geodata Portals */}
        <section className="space-y-4">
          <h2 className="text-2xl">Geodata Portals</h2>
          <div className="flex space-x-2 mb-4">
            <select
              value={newPortal}
              onChange={(e) => setNewPortal(e.target.value)}
              className="border rounded p-2 flex-grow"
            >
              <option value="">Select portal to add</option>
              {availablePortals.map((portal) => (
                <option key={portal} value={portal}>
                  {portal}
                </option>
              ))}
            </select>
            <button
              onClick={() => {
                newPortal && addPortal(newPortal);
                setNewPortal("");
              }}
              className="bg-blue-600 text-white px-4 py-2 rounded"
            >
              Add Portal
            </button>
          </div>
          <ul className="space-y-3">
            {portals.map((p, i) => (
              <li
                key={i}
                className="flex justify-between items-center border rounded p-4"
              >
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={p.enabled}
                    onChange={() => togglePortal(p.url)}
                    className="form-checkbox h-5 w-5 text-green-600"
                  />
                  <span
                    className={`${p.enabled ? "text-gray-900" : "text-gray-400"}`}
                  >
                    {p.url}
                  </span>
                </label>
                <button
                  onClick={() => removePortal(p.url)}
                  className="text-red-600 hover:underline"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        </section>

        {/* GeoServer Backends */}
        <section className="space-y-4">
          <h2 className="text-2xl">GeoServer Backends</h2>
          <div className="space-y-3 mb-4">
            <input
              value={newBackend.url}
              onChange={(e) =>
                setNewBackend({ ...newBackend, url: e.target.value })
              }
              placeholder="GeoServer URL"
              className="border rounded p-2 w-full"
            />
            <input
              value={newBackend.name}
              onChange={(e) =>
                setNewBackend({ ...newBackend, name: e.target.value })
              }
              placeholder="Name (optional)"
              className="border rounded p-2 w-full"
            />
            <textarea
              value={newBackend.description}
              onChange={(e) =>
                setNewBackend({ ...newBackend, description: e.target.value })
              }
              placeholder="Description (optional)"
              className="border rounded p-2 w-full h-20"
            />
            <input
              value={newBackend.username}
              onChange={(e) =>
                setNewBackend({ ...newBackend, username: e.target.value })
              }
              placeholder="Username (optional)"
              className="border rounded p-2 w-full"
            />
            <input
              type="password"
              value={newBackend.password}
              onChange={(e) =>
                setNewBackend({ ...newBackend, password: e.target.value })
              }
              placeholder="Password (optional)"
              className="border rounded p-2 w-full"
            />
            <button
              onClick={handleAddBackend}
              disabled={backendLoading}
              className={`bg-blue-600 text-white px-4 py-2 rounded ${backendLoading ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              {backendLoading
                ? importingBackends
                  ? "Prefetching…"
                  : "Checking…"
                : "Add Backend"}
            </button>
            {backendLoading && (
              <div className="w-full mt-2 h-2 bg-gray-200 rounded">
                <div className="h-2 bg-blue-500 rounded animate-pulse w-full" />
              </div>
            )}
            {backendError && (
              <p className="text-red-600 text-sm">{backendError}</p>
            )}
            {backendSuccess && (
              <p className="text-green-600 text-sm">{backendSuccess}</p>
            )}
          </div>
          <ul className="space-y-3">
            {backends.map((b, i) => (
              <li
                key={i}
                className="flex justify-between items-center border rounded p-4"
              >
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={b.enabled}
                    onChange={() => toggleBackend(b.url)}
                    className="form-checkbox h-5 w-5 text-green-600"
                  />
                  <div className="flex-1">
                    <p
                      className={`${b.enabled ? "text-gray-900" : "text-gray-400"}`}
                    >
                      <strong>{b.name || "URL"}:</strong> {b.url}
                    </p>
                    {b.description && (
                      <p
                        className={`${b.enabled ? "text-gray-700" : "text-gray-400"} text-sm`}
                      >
                        {b.description}
                      </p>
                    )}
                    {b.username && (
                      <p
                        className={`${b.enabled ? "text-gray-900" : "text-gray-400"}`}
                      >
                        <strong>Username:</strong> {b.username}
                      </p>
                    )}

                    {/* Embedding Progress */}
                    {b.enabled &&
                      embeddingStatus[b.url] &&
                      (embeddingStatus[b.url].total > 0 ||
                        embeddingStatus[b.url].state === "waiting") && (
                        <div className="mt-2">
                          <div className="flex justify-between items-center text-xs mb-1">
                            <span
                              className={
                                embeddingStatus[b.url].complete ||
                                embeddingStatus[b.url].state === "completed"
                                  ? "text-green-600"
                                  : embeddingStatus[b.url].state === "error"
                                    ? "text-red-600"
                                    : embeddingStatus[b.url].state === "waiting"
                                      ? "text-yellow-600"
                                      : "text-blue-600"
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
                                    : "⏳ Embedding in progress"}
                              {embeddingStatus[b.url].total > 0 && (
                                <>
                                  : {embeddingStatus[b.url].encoded} /{" "}
                                  {embeddingStatus[b.url].total} layers
                                </>
                              )}
                            </span>
                            {embeddingStatus[b.url].total > 0 && (
                              <span className="text-gray-600">
                                {embeddingStatus[b.url].percentage}%
                              </span>
                            )}
                          </div>
                          {embeddingStatus[b.url].state !== "error" &&
                            embeddingStatus[b.url].total > 0 && (
                              <div className="w-full h-2 bg-gray-200 rounded overflow-hidden">
                                <div
                                  className={`h-full transition-all duration-300 ${
                                    embeddingStatus[b.url].complete ||
                                    embeddingStatus[b.url].state === "completed"
                                      ? "bg-green-500"
                                      : embeddingStatus[b.url].state ===
                                          "waiting"
                                        ? "bg-yellow-500 animate-pulse"
                                        : embeddingStatus[b.url].in_progress
                                          ? "bg-blue-500 animate-pulse"
                                          : "bg-blue-500"
                                  }`}
                                  style={{
                                    width: `${embeddingStatus[b.url].state === "waiting" ? 5 : embeddingStatus[b.url].percentage}%`,
                                  }}
                                />
                              </div>
                            )}
                        </div>
                      )}
                  </div>
                </label>
                <button
                  onClick={() => removeBackend(b.url)}
                  className="text-red-600 hover:underline ml-2"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        </section>
      </main>
    </div>
  );
}
