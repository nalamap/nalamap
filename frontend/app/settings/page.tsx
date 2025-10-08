"use client";

import React, { useState, useRef, useEffect } from "react";
import Sidebar from "../components/sidebar/Sidebar";
import { GeoServerBackend, SettingsSnapshot } from "../stores/settingsStore";
import { useUIStore } from "../stores/uiStore";

import { useInitializedSettingsStore } from "../hooks/useInitializedSettingsStore";
import { getApiBase } from "../utils/apiBase";

type BackendPrefetchInput = Omit<GeoServerBackend, "enabled"> & {
  enabled?: boolean;
};

export default function SettingsPage() {
  // UI store for layout
  const sidebarWidth = useUIStore((s) => s.sidebarWidth);
  const setSidebarWidth = useUIStore((s) => s.setSidebarWidth);
  
  // Drag handling for sidebar resize
  const dragInfo = useRef<{
    active: boolean;
    startX: number;
    initialWidth: number;
  }>({ active: false, startX: 0, initialWidth: 0 });

  const onMouseMove = (e: MouseEvent) => {
    if (!dragInfo.current.active) return;
    const deltaX = e.clientX - dragInfo.current.startX;
    const deltaPercent = (deltaX / window.innerWidth) * 100;
    const newWidth = Math.max(2, Math.min(20, dragInfo.current.initialWidth + deltaPercent));
    setSidebarWidth(newWidth);
  };

  const onMouseUp = () => {
    dragInfo.current.active = false;
    document.removeEventListener("mousemove", onMouseMove);
    document.removeEventListener("mouseup", onMouseUp);
  };

  const onHandleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    dragInfo.current = {
      active: true,
      startX: e.clientX,
      initialWidth: sidebarWidth,
    };
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  };
  
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
  const availableExampleGeoServers = useInitializedSettingsStore(
    (s) => s.available_example_geoservers,
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
  const setAvailableExampleGeoServers = useInitializedSettingsStore(
    (s) => s.setAvailableExampleGeoServers,
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
  const [selectedExampleGeoServer, setSelectedExampleGeoServer] = useState("");
  const [newBackend, setNewBackend] = useState<
    Omit<GeoServerBackend, "enabled">
  >({ url: "", name: "", description: "", username: "", password: "" });
  const [newToolName, setNewToolName] = useState("");
  const [backendError, setBackendError] = useState<string | null>(null);
  const [backendSuccess, setBackendSuccess] = useState<string | null>(null);
  const [backendLoading, setBackendLoading] = useState(false);
  const [importingBackends, setImportingBackends] = useState(false);
  const [toolsSectionCollapsed, setToolsSectionCollapsed] = useState(true);
  const [toolPromptVisibility, setToolPromptVisibility] = useState<{
    [toolName: string]: boolean;
  }>({});
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

  // Interpolated progress for smooth animations
  const [interpolatedProgress, setInterpolatedProgress] = useState<{
    [url: string]: {
      encoded: number;
      percentage: number;
      velocity: number; // layers per second
      lastUpdate: number; // timestamp
    };
  }>({});

  const API_BASE_URL = getApiBase();

  // Constants for progress interpolation
  const DEFAULT_VELOCITY = 1.5; // layers per second (conservative estimate)
  const INTERPOLATION_FPS = 3; // frames per second
  const INTERPOLATION_INTERVAL = 1000 / INTERPOLATION_FPS; // milliseconds

  // Ref to track if we should continue polling
  const shouldPollRef = React.useRef(true);

  const normalizeBackend = (
    backend: BackendPrefetchInput,
  ): GeoServerBackend => {
    let url = backend.url.trim();

    // Add https:// if protocol is missing to prevent connection errors
    if (url && !url.match(/^https?:\/\//i)) {
      url = `https://${url}`;
    }

    // Strip trailing slashes to match backend normalization (backend calls rstrip('/'))
    // This ensures URL keys match when querying embedding status
    url = url.replace(/\/+$/, "");

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
      session_id: currentSettings.session_id, // Preserve current session_id, ignore imported session_id
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

      // Initialize embedding status to 'waiting' state BEFORE adding backend
      // This ensures UI shows progress bar immediately when backend appears
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

      // Initialize interpolatedProgress so progress bar shows immediately
      setInterpolatedProgress((prev) => ({
        ...prev,
        [normalizedBackend.url]: {
          encoded: 0,
          percentage: 0,
          velocity: DEFAULT_VELOCITY,
          lastUpdate: Date.now(),
        },
      }));

      // Add backend to list (this triggers useEffect to fetch status)
      addBackend(normalizedBackend);

      setNewBackend({
        url: "",
        name: "",
        description: "",
        username: "",
        password: "",
      });

      // Start preloading in background - user can now navigate away
      await prefetchBackend(normalizedBackend);

      // The prefetch returns total_layers=0 initially, actual total will come from
      // embedding-status polling. The useEffect will call fetchEmbeddingStatus()
      // automatically when the backends state updates.

      setBackendSuccess(
        `Backend queued for processing. Embedding will start shortly.`,
      );
    } catch (err: any) {
      setBackendError(err?.message || "Failed to preload GeoServer backend.");
    } finally {
      setBackendLoading(false);
    }
  };

  // Fetch embedding status for enabled backends
  const fetchEmbeddingStatus = React.useCallback(async () => {
    const enabledBackends = backends.filter((b) => b.enabled);
    if (enabledBackends.length === 0) {
      setEmbeddingStatus({});
      setInterpolatedProgress({});
      shouldPollRef.current = false;
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
        const newStatus = data.backends || {};
        const now = Date.now();

        // Calculate velocity for each backend
        setInterpolatedProgress((prev) => {
          const updated: typeof prev = {};
          Object.keys(newStatus).forEach((url) => {
            const status = newStatus[url];
            const prevInterp = prev[url];

            if (status.state === "processing" && status.in_progress) {
              if (prevInterp && prevInterp.lastUpdate) {
                const timeDelta = (now - prevInterp.lastUpdate) / 1000; // seconds
                const layersDelta = status.encoded - prevInterp.encoded;
                const velocity = timeDelta > 0 ? layersDelta / timeDelta : 0;

                updated[url] = {
                  encoded: status.encoded,
                  percentage: status.percentage,
                  velocity:
                    velocity > 0
                      ? velocity
                      : prevInterp.velocity || DEFAULT_VELOCITY,
                  lastUpdate: now,
                };
              } else {
                // First data point - use default velocity for immediate smooth animation
                updated[url] = {
                  encoded: status.encoded,
                  percentage: status.percentage,
                  velocity: DEFAULT_VELOCITY,
                  lastUpdate: now,
                };
              }
            } else {
              // Not processing - reset
              updated[url] = {
                encoded: status.encoded,
                percentage: status.percentage,
                velocity: 0,
                lastUpdate: now,
              };
            }
          });
          return updated;
        });

        setEmbeddingStatus(newStatus);

        // Check if all backends are complete or errored - stop polling if so
        const allComplete = Object.values(newStatus).every(
          (status: any) =>
            status.state === "completed" ||
            status.state === "error" ||
            status.complete === true,
        );
        if (allComplete && Object.keys(newStatus).length > 0) {
          shouldPollRef.current = false;
        }
      }
    } catch (err) {
      // Silently fail - embedding status is optional
      console.error("Failed to fetch embedding status:", err);
    }
  }, [backends, API_BASE_URL, DEFAULT_VELOCITY]);

  // Poll embedding status every 10 seconds when there are enabled backends
  React.useEffect(() => {
    // Fetch initial status immediately when component mounts or backends change
    const enabledBackends = backends.filter((b) => b.enabled);
    if (enabledBackends.length > 0) {
      shouldPollRef.current = true; // Reset polling flag when backends change
      fetchEmbeddingStatus();
    } else {
      shouldPollRef.current = false;
    }

    // Set up polling interval
    const interval = setInterval(() => {
      const currentEnabledBackends = backends.filter((b) => b.enabled);
      if (currentEnabledBackends.length === 0) {
        shouldPollRef.current = false;
        return;
      }

      // Only poll if we haven't determined all backends are complete
      if (shouldPollRef.current) {
        fetchEmbeddingStatus();
      }
    }, 5000); // 5 seconds

    return () => clearInterval(interval);
  }, [backends, fetchEmbeddingStatus]);

  // Smooth interpolation effect for progress bars
  React.useEffect(() => {
    let timeoutId: NodeJS.Timeout;
    let lastAnimationTime = Date.now();

    const animate = () => {
      const now = Date.now();
      const timeSinceLastAnimation = now - lastAnimationTime;

      // Only update at configured FPS
      if (timeSinceLastAnimation >= INTERPOLATION_INTERVAL) {
        lastAnimationTime = now;

        setInterpolatedProgress((prev) => {
          const updated: typeof prev = {};
          let hasChanges = false;

          Object.keys(prev).forEach((url) => {
            const interp = prev[url];
            const status = embeddingStatus[url];

            if (
              status &&
              status.state === "processing" &&
              status.in_progress &&
              interp.velocity > 0
            ) {
              const timeSinceUpdate = (now - interp.lastUpdate) / 1000; // seconds
              const predictedProgress =
                interp.encoded + interp.velocity * timeSinceUpdate;

              // Cap at the total to avoid overshooting
              const cappedProgress = Math.min(predictedProgress, status.total);
              const cappedPercentage =
                status.total > 0 ? (cappedProgress / status.total) * 100 : 0;

              // Only update if we haven't reached the real progress yet
              if (cappedProgress > interp.encoded) {
                updated[url] = {
                  ...interp,
                  encoded: cappedProgress,
                  percentage: Math.min(cappedPercentage, 99.9), // Never show 100% unless complete
                };
                hasChanges = true;
              } else {
                updated[url] = interp;
              }
            } else {
              updated[url] = interp;
            }
          });

          return hasChanges ? updated : prev;
        });
      }

      // Schedule next frame
      timeoutId = setTimeout(animate, INTERPOLATION_INTERVAL);
    };

    // Start animation loop
    timeoutId = setTimeout(animate, INTERPOLATION_INTERVAL);

    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [embeddingStatus]);

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
    <>
      {/* Mobile menu toggle */}
      <button
        className="md:hidden fixed top-4 left-4 z-20 p-2 bg-primary-200 rounded-full hover:bg-primary-300"
        onClick={() => {
          const menu = document.getElementById("mobile-settings-menu");
          if (menu) menu.classList.toggle("hidden");
        }}
      >
        <svg
          className="w-6 h-6 text-primary-700"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 6h16M4 12h16M4 18h16"
          />
        </svg>
      </button>
      <div
        id="mobile-settings-menu"
        className="hidden fixed inset-0 bg-black bg-opacity-50 z-20"
      >
        <div className="fixed top-0 left-0 bottom-0 w-64 bg-primary-800 z-30 text-white p-4">
          <button
            className="absolute top-4 right-4"
            onClick={() => {
              const menu = document.getElementById("mobile-settings-menu");
              if (menu) menu.classList.add("hidden");
            }}
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
          <Sidebar />
        </div>
      </div>
      <div className="flex h-screen w-screen overflow-hidden">
        {/* Sidebar / Menu */}
        <div 
          className="hidden md:flex flex-none relative bg-primary-800"
          style={{ flexBasis: `${sidebarWidth}%` }}
        >
          <Sidebar />
          <div
            className="absolute top-0 right-0 bottom-0 w-1 hover:bg-primary-400 cursor-ew-resize z-10"
            onMouseDown={onHandleMouseDown}
          />
        </div>

        {/* Main content */}
        <main className="flex-1 overflow-auto p-6 space-y-8 scroll-smooth bg-primary-50">
          <h1 className="text-3xl font-bold text-primary-900">Settings</h1>
          {/* Export/Import Settings */}
          <div className="flex space-x-4 mb-8">
            <button
              onClick={exportSettings}
              className="bg-tertiary-600 text-white px-4 py-2 rounded hover:bg-tertiary-700 font-medium shadow-sm cursor-pointer"
              style={{ backgroundColor: 'var(--tertiary-600)' }}
            >
              Export Settings
            </button>
            <label 
              className="bg-second-primary-600 text-white px-4 py-2 rounded cursor-pointer hover:bg-second-primary-700 font-medium shadow-sm inline-block"
              style={{ backgroundColor: 'var(--second-primary-600)' }}
            >
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
            <h2 className="text-2xl font-semibold text-primary-800">Model Settings</h2>
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
              className="border border-primary-300 rounded p-2 bg-white text-primary-900"
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
              className="border border-primary-300 rounded p-2 bg-white text-primary-900"
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
              className="border border-primary-300 rounded p-2 bg-white text-primary-900"
            />
            <textarea
              value={modelSettings.system_prompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="System Prompt"
              className="border border-primary-300 rounded p-2 col-span-2 h-24 bg-white text-primary-900"
            />
          </div>
        </section>

        {/* Tools Configuration */}
        <section className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-semibold text-primary-800">Tools Configuration</h2>
            <button
              onClick={() => setToolsSectionCollapsed(!toolsSectionCollapsed)}
              className="text-primary-600 hover:text-primary-800 font-medium flex items-center space-x-1"
            >
              <span>{toolsSectionCollapsed ? "Show" : "Hide"}</span>
              <svg
                className={`w-5 h-5 transform transition-transform ${toolsSectionCollapsed ? "rotate-180" : ""}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          </div>
          
          {!toolsSectionCollapsed && (
            <>
              <div className="flex space-x-2 mb-4">
                <select
                  value={newToolName}
                  onChange={(e) => setNewToolName(e.target.value)}
                  className="border border-primary-300 rounded p-2 flex-grow bg-white text-primary-900"
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
                  className="bg-second-primary-600 text-white px-4 py-2 rounded hover:bg-second-primary-700 font-medium shadow-sm cursor-pointer"
                  style={{ backgroundColor: 'var(--second-primary-600)' }}
                >
                  Add Tool
                </button>
              </div>
              <ul className="space-y-3">
                {tools.map((t, i) => (
                  <li key={i} className="border border-primary-200 rounded p-4 space-y-2 bg-white">
                    <div className="flex justify-between items-center">
                      <label className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          checked={t.enabled}
                          onChange={() => toggleToolConfig(t.name)}
                          className="form-checkbox h-5 w-5 text-tertiary-600"
                        />
                        <span
                          className={`font-medium ${t.enabled ? "text-primary-900" : "text-primary-400"}`}
                        >
                          {t.name}
                        </span>
                      </label>
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() =>
                            setToolPromptVisibility((prev) => ({
                              ...prev,
                              [t.name]: !prev[t.name],
                            }))
                          }
                          className="text-primary-600 hover:text-primary-800 font-medium text-sm"
                        >
                          {toolPromptVisibility[t.name] ? "Hide Prompt" : "Show Prompt"}
                        </button>
                        <button
                          onClick={() => removeToolConfig(t.name)}
                          className="text-red-600 hover:underline font-medium"
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                    {toolPromptVisibility[t.name] && (
                      <textarea
                        value={t.prompt_override}
                        onChange={(e) =>
                          setToolPromptOverride(t.name, e.target.value)
                        }
                        placeholder="Prompt Override (leave empty to use default)"
                        className="border border-primary-300 rounded p-2 w-full h-20 bg-white text-primary-900"
                      />
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>

        {/* Example GeoServers */}
        <section className="space-y-4">
          <h2 className="text-2xl font-semibold text-primary-800">Example GeoServers</h2>
          <p className="text-sm text-primary-600">
            Choose from publicly available example GeoServers to quickly get started with geospatial data.
          </p>
          <div className="flex space-x-2 mb-4">
            <select
              value={selectedExampleGeoServer}
              onChange={(e) => setSelectedExampleGeoServer(e.target.value)}
              className="border border-primary-300 rounded p-2 flex-grow bg-white text-primary-900"
            >
              <option value="">Select an example GeoServer</option>
              {availableExampleGeoServers.map((geoserver) => (
                <option key={geoserver.url} value={geoserver.url}>
                  {geoserver.name} - {geoserver.url}
                </option>
              ))}
            </select>
            <button
              onClick={async () => {
                if (!selectedExampleGeoServer) return;
                const selected = availableExampleGeoServers.find(
                  (gs) => gs.url === selectedExampleGeoServer
                );
                if (!selected) return;

                // Use the same add backend logic with the example geoserver values
                setBackendError(null);
                setBackendSuccess(null);
                setBackendLoading(true);
                setImportingBackends(false);

                try {
                  const normalizedBackend = normalizeBackend({
                    url: selected.url,
                    name: selected.name,
                    description: selected.description,
                    username: selected.username || "",
                    password: selected.password || "",
                    enabled: true,
                  });

                  // Initialize embedding status to 'waiting' state BEFORE adding backend
                  // This ensures UI shows progress bar immediately when backend appears
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

                  setInterpolatedProgress((prev) => ({
                    ...prev,
                    [normalizedBackend.url]: {
                      encoded: 0,
                      percentage: 0,
                      velocity: DEFAULT_VELOCITY,
                      lastUpdate: Date.now(),
                    },
                  }));

                  // Add backend to list (this triggers useEffect to fetch status)
                  addBackend(normalizedBackend);

                  setSelectedExampleGeoServer("");

                  await prefetchBackend(normalizedBackend);

                  // The prefetch returns total_layers=0 initially, actual total will come from
                  // embedding-status polling. The useEffect will call fetchEmbeddingStatus()
                  // automatically when the backends state updates.

                  setBackendSuccess(
                    `Example backend "${selected.name}" added and queued for processing.`,
                  );
                } catch (err: any) {
                  setBackendError(
                    err?.message || "Failed to add example GeoServer backend.",
                  );
                } finally {
                  setBackendLoading(false);
                }
              }}
              disabled={!selectedExampleGeoServer || backendLoading}
              className={`bg-second-primary-600 text-white px-4 py-2 rounded font-medium shadow-sm ${!selectedExampleGeoServer || backendLoading ? "opacity-50 cursor-not-allowed" : "hover:bg-second-primary-700 cursor-pointer"}`}
              style={{ backgroundColor: (!selectedExampleGeoServer || backendLoading) ? undefined : 'var(--second-primary-600)' }}
            >
              {backendLoading ? "Adding..." : "Add Example GeoServer"}
            </button>
          </div>
          {availableExampleGeoServers.map((geoserver) => (
            <div
              key={geoserver.url}
              className="border border-primary-200 rounded p-4 bg-white space-y-2"
            >
              <h3 className="text-lg font-semibold text-primary-900">
                {geoserver.name}
              </h3>
              <p className="text-sm text-primary-600">{geoserver.url}</p>
              <div className="text-sm text-primary-700 prose prose-sm max-w-none">
                {geoserver.description}
              </div>
            </div>
          ))}
        </section>

        {/* GeoServer Backends */}
        <section className="space-y-4">
          <h2 className="text-2xl font-semibold text-primary-800">GeoServer Backends</h2>
          <div className="space-y-3 mb-4">
            <input
              value={newBackend.url}
              onChange={(e) =>
                setNewBackend({ ...newBackend, url: e.target.value })
              }
              placeholder="GeoServer URL"
              className="border border-primary-300 rounded p-2 w-full bg-white text-primary-900"
            />
            <input
              value={newBackend.name}
              onChange={(e) =>
                setNewBackend({ ...newBackend, name: e.target.value })
              }
              placeholder="Name (optional)"
              className="border border-primary-300 rounded p-2 w-full bg-white text-primary-900"
            />
            <textarea
              value={newBackend.description}
              onChange={(e) =>
                setNewBackend({ ...newBackend, description: e.target.value })
              }
              placeholder="Description (optional)"
              className="border border-primary-300 rounded p-2 w-full h-20 bg-white text-primary-900"
            />
            <input
              value={newBackend.username}
              onChange={(e) =>
                setNewBackend({ ...newBackend, username: e.target.value })
              }
              placeholder="Username (optional)"
              className="border border-primary-300 rounded p-2 w-full bg-white text-primary-900"
            />
            <input
              type="password"
              value={newBackend.password}
              onChange={(e) =>
                setNewBackend({ ...newBackend, password: e.target.value })
              }
              placeholder="Password (optional)"
              className="border border-primary-300 rounded p-2 w-full bg-white text-primary-900"
            />
            <button
              onClick={handleAddBackend}
              disabled={backendLoading}
              className={`bg-second-primary-600 text-white px-4 py-2 rounded font-medium shadow-sm ${backendLoading ? "opacity-50 cursor-not-allowed" : "hover:bg-second-primary-700 cursor-pointer"}`}
              style={{ backgroundColor: backendLoading ? undefined : 'var(--second-primary-600)' }}
            >
              {backendLoading
                ? importingBackends
                  ? "Prefetching…"
                  : "Checking…"
                : "Add Backend"}
            </button>
            {backendLoading && (
              <div className="w-full mt-2 h-2 bg-primary-200 rounded">
                <div className="h-2 bg-second-primary-500 rounded animate-pulse w-full" />
              </div>
            )}
            {backendError && (
              <p className="text-red-600 text-sm font-medium">{backendError}</p>
            )}
            {backendSuccess && (
              <p className="text-tertiary-600 text-sm font-medium">{backendSuccess}</p>
            )}
          </div>
          <ul className="space-y-3">
            {backends.map((b, i) => (
              <li
                key={i}
                className="flex justify-between items-center border border-primary-200 rounded p-4 bg-white"
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
                      className={`font-medium ${b.enabled ? "text-primary-900" : "text-primary-400"}`}
                    >
                      <strong>{b.name || "URL"}:</strong> {b.url}
                    </p>
                    {b.description && (
                      <p
                        className={`${b.enabled ? "text-primary-700" : "text-primary-400"} text-sm`}
                      >
                        {b.description}
                      </p>
                    )}
                    {b.username && (
                      <p
                        className={`${b.enabled ? "text-primary-900" : "text-primary-400"} text-sm`}
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
                                  ? "text-tertiary-600 font-medium"
                                  : embeddingStatus[b.url].state === "error"
                                    ? "text-red-600 font-medium"
                                    : embeddingStatus[b.url].state === "waiting"
                                      ? "text-secondary-600 font-medium"
                                      : embeddingStatus[b.url].state ===
                                          "unknown"
                                        ? "text-primary-500 font-medium"
                                        : "text-second-primary-600 font-medium"
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
                                    : embeddingStatus[b.url].state === "unknown"
                                      ? "⏸️ Status unknown (checking...)"
                                      : "⏳ Embedding in progress"}
                              {embeddingStatus[b.url].total > 0 && (
                                <>
                                  :{" "}
                                  {interpolatedProgress[b.url]
                                    ? Math.floor(
                                        interpolatedProgress[b.url].encoded,
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
                              <div className="w-full h-2 bg-primary-200 rounded overflow-hidden">
                                <div
                                  className={`h-full transition-all duration-100 ${
                                    embeddingStatus[b.url].complete ||
                                    embeddingStatus[b.url].state === "completed"
                                      ? "bg-tertiary-500"
                                      : embeddingStatus[b.url].state ===
                                          "waiting"
                                        ? "bg-secondary-500 animate-pulse"
                                        : embeddingStatus[b.url].in_progress
                                          ? "bg-second-primary-500"
                                          : "bg-second-primary-500"
                                  }`}
                                  style={{
                                    width: `${
                                      embeddingStatus[b.url].state ===
                                        "waiting" ||
                                      embeddingStatus[b.url].state === "unknown"
                                        ? 5
                                        : interpolatedProgress[b.url]
                                          ? interpolatedProgress[b.url]
                                              .percentage
                                          : embeddingStatus[b.url].percentage
                                    }%`,
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
                  className="text-red-600 hover:underline ml-2 font-medium"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        </section>
        </main>
      </div>
    </>
  );
}
