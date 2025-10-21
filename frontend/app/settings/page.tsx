"use client";

import React, { useState, useRef, useEffect } from "react";
import Sidebar from "../components/sidebar/Sidebar";
import { GeoServerBackend, SettingsSnapshot } from "../stores/settingsStore";
import { useUIStore } from "../stores/uiStore";
import ColorSettingsComponent from "../components/settings/ColorSettingsComponent";
import ThemeToggleComponent from "../components/settings/ThemeToggleComponent";
import ModelSettingsComponent from "../components/settings/ModelSettingsComponent";
import ToolSettingsComponent from "../components/settings/ToolSettingsComponent";
import GeoServerSettingsComponent from "../components/settings/GeoServerSettingsComponent";

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
  const toggleBackendInsecure = useInitializedSettingsStore(
    (s) => s.toggleBackendInsecure,
  );

  const setAvailableExampleGeoServers = useInitializedSettingsStore(
    (s) => s.setAvailableExampleGeoServers,
  );

  const setSessionId = useInitializedSettingsStore((s) => s.setSessionId);

  // Get Settings
  const getSettings = useInitializedSettingsStore((s) => s.getSettings);
  const setSettings = useInitializedSettingsStore((s) => s.setSettings);
  const availableExampleGeoServers = useInitializedSettingsStore(
    (s) => s.available_example_geoservers,
  );
  // local state
  const [selectedExampleGeoServer, setSelectedExampleGeoServer] = useState("");
  const [newBackend, setNewBackend] = useState<
    Omit<GeoServerBackend, "enabled">
  >({ url: "", name: "", description: "", username: "", password: "" });
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

  // Interpolated progress for smooth animations
  const [interpolatedProgress, setInterpolatedProgress] = useState<{
    [url: string]: {
      encoded: number; // Baseline from real backend data
      displayEncoded: number; // Interpolated value for display
      percentage: number;
      velocity: number; // layers per second
      lastUpdate: number; // timestamp
    };
  }>({});

  const API_BASE_URL = getApiBase();

  // Read interpolation configuration from environment variables
  const getEmbeddingConfig = () => {
    if (typeof window !== 'undefined') {
      const runtimeConfig = (window as any).__RUNTIME_CONFIG__ || {};
      
      return {
        interpolationEnabled: runtimeConfig.NEXT_PUBLIC_EMBEDDING_INTERPOLATION_ENABLED === 'true' || 
                            process.env.NEXT_PUBLIC_EMBEDDING_INTERPOLATION_ENABLED === 'true',
        pollingInterval: parseInt(
          runtimeConfig.NEXT_PUBLIC_EMBEDDING_POLLING_INTERVAL_MS || 
          process.env.NEXT_PUBLIC_EMBEDDING_POLLING_INTERVAL_MS || 
          '3000'
        ),
        defaultVelocity: parseFloat(
          runtimeConfig.NEXT_PUBLIC_EMBEDDING_DEFAULT_VELOCITY || 
          process.env.NEXT_PUBLIC_EMBEDDING_DEFAULT_VELOCITY || 
          '3'
        ),
      };
    }
    // Server-side defaults
    return {
      interpolationEnabled: false,
      pollingInterval: 3000,
      defaultVelocity: 3,
    };
  };

  const embeddingConfig = getEmbeddingConfig();

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
      allow_insecure: backend.allow_insecure ?? false,
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
          displayEncoded: 0,
          percentage: 0,
          velocity: embeddingConfig.defaultVelocity,
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

  const handleAddExampleGeoServer = async () => {
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
          displayEncoded: 0,
          percentage: 0,
          velocity: embeddingConfig.defaultVelocity,
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
  };

  // Handle toggling allow_insecure and re-prefetch
  const handleToggleBackendInsecure = async (url: string) => {
    // Find the backend
    const backend = backends.find((b) => b.url === url);
    if (!backend) return;

    // Toggle the flag in the store
    toggleBackendInsecure(url);

    // Get the updated backend state (after toggle)
    const updatedBackend = {
      ...backend,
      allow_insecure: !backend.allow_insecure,
    };

    // Set status to waiting immediately
    setEmbeddingStatus((prev) => ({
      ...prev,
      [url]: {
        ...prev[url],
        state: "waiting",
        error: null,
        error_type: undefined,
        error_details: undefined,
      },
    }));

    try {
      // Re-prefetch with the updated allow_insecure flag
      await prefetchBackend(updatedBackend);
    } catch (err: any) {
      console.error("Failed to re-prefetch backend:", err);
      // Error will be shown via embedding status polling
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
                // CRITICAL FIX: Use the REAL encoded value from status, not interpolated value
                // The interpolated value may have drifted ahead during animation
                const prevRealEncoded = embeddingStatus[url]?.encoded || prevInterp.encoded;
                const layersDelta = status.encoded - prevRealEncoded;
                const velocity = timeDelta > 0 && layersDelta > 0 ? layersDelta / timeDelta : 0;

                // Use measured velocity if positive, otherwise keep previous velocity
                // This allows velocity to adapt over time while preventing resets
                const newVelocity = velocity > 0 
                  ? velocity 
                  : (prevInterp.velocity > 0 ? prevInterp.velocity : embeddingConfig.defaultVelocity);

                updated[url] = {
                  encoded: status.encoded, // Always use real value as baseline
                  displayEncoded: status.encoded, // Reset display to real value
                  percentage: status.percentage,
                  velocity: newVelocity,
                  lastUpdate: now,
                };
              } else {
                // First data point - use default velocity for immediate smooth animation
                updated[url] = {
                  encoded: status.encoded,
                  displayEncoded: status.encoded,
                  percentage: status.percentage,
                  velocity: embeddingConfig.defaultVelocity,
                  lastUpdate: now,
                };
              }
            } else {
              // Not processing - reset
              updated[url] = {
                encoded: status.encoded,
                displayEncoded: status.encoded,
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
  }, [backends, API_BASE_URL, embeddingConfig.defaultVelocity]);

  // Poll embedding status using configured interval when there are enabled backends
  React.useEffect(() => {
    // Fetch initial status immediately when component mounts or backends change
    const enabledBackends = backends.filter((b) => b.enabled);
    if (enabledBackends.length > 0) {
      shouldPollRef.current = true; // Reset polling flag when backends change
      fetchEmbeddingStatus();
    } else {
      shouldPollRef.current = false;
    }

    // Set up polling interval using configured value
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
    }, embeddingConfig.pollingInterval);

    return () => clearInterval(interval);
  }, [backends, fetchEmbeddingStatus, embeddingConfig.pollingInterval]);

  // Smooth interpolation effect for progress bars (only if enabled)
  React.useEffect(() => {
    // Skip interpolation if disabled
    if (!embeddingConfig.interpolationEnabled) {
      return;
    }

    let animationFrameId: number;

    const animate = () => {
      const now = Date.now();

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
            // Calculate time since the LAST REAL UPDATE (not last animation frame)
            const timeSinceRealUpdate = (now - interp.lastUpdate) / 1000; // seconds
            
            // CRITICAL FIX: Always calculate from the REAL encoded value (interp.encoded)
            // which is set from the actual backend response, not from previous animations
            const predictedProgress =
              interp.encoded + interp.velocity * timeSinceRealUpdate;

            // Cap at the total to avoid overshooting
            const cappedProgress = Math.min(predictedProgress, status.total);
            const cappedPercentage =
              status.total > 0 ? (cappedProgress / status.total) * 100 : 0;

            // Update the displayed values without changing the baseline encoded value or lastUpdate
            // This ensures linear interpolation from the last real update
            updated[url] = {
              encoded: interp.encoded, // Keep the real baseline, don't update it during animation
              displayEncoded: cappedProgress, // Show interpolated value
              percentage: Math.min(cappedPercentage, 99.9), // Never show 100% unless complete
              velocity: interp.velocity,
              lastUpdate: interp.lastUpdate, // Keep the real update timestamp
            };
            hasChanges = true;
          } else {
            updated[url] = interp;
          }
        });

        return hasChanges ? updated : prev;
      });

      // Schedule next frame
      animationFrameId = requestAnimationFrame(animate);
    };

    // Start animation loop
    animationFrameId = requestAnimationFrame(animate);

    return () => {
      if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
      }
    };
  }, [embeddingStatus, embeddingConfig.interpolationEnabled]);

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
        className="hidden fixed inset-0 bg-neutral-950 bg-opacity-50 z-20"
      >
        <div className="fixed top-0 left-0 bottom-0 w-64 bg-primary-800 z-30 text-neutral-50 p-4">
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
              className="bg-tertiary-600 text-neutral-50 px-4 py-2 rounded hover:bg-tertiary-700 font-medium shadow-sm cursor-pointer"
              style={{ backgroundColor: 'var(--tertiary-600)' }}
            >
              Export Settings
            </button>
            <label 
              className="bg-second-primary-600 text-neutral-50 px-4 py-2 rounded cursor-pointer hover:bg-second-primary-700 font-medium shadow-sm inline-block"
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
          <section>
            <ModelSettingsComponent />
          </section>

          {/* Theme Preference */}
          <section>
            <ThemeToggleComponent />
          </section>

          {/* Color Customization */}
          <section>
            <ColorSettingsComponent />
          </section>

          {/* Tools Configuration */}
          <section>
            <ToolSettingsComponent />
          </section>

          {/* GeoServer Backends */}
          <section>
            <GeoServerSettingsComponent
              newBackend={newBackend}
              setNewBackend={setNewBackend}
              handleAddBackend={handleAddBackend}
              selectedExampleGeoServer={selectedExampleGeoServer}
              setSelectedExampleGeoServer={setSelectedExampleGeoServer}
              handleAddExampleGeoServer={handleAddExampleGeoServer}
              backendLoading={backendLoading}
              backendError={backendError}
              backendSuccess={backendSuccess}
              embeddingStatus={embeddingStatus}
              interpolatedProgress={interpolatedProgress}
              handleToggleBackendInsecure={handleToggleBackendInsecure}
            />
          </section>
        </main>
      </div>
    </>
  );
}
