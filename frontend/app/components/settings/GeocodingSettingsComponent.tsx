"use client";

import React, { useState, useEffect, useCallback } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { getApiBase } from "../../utils/apiBase";

interface TagEmbeddingStatus {
  state: "empty" | "waiting" | "processing" | "populated" | "error";
  total: number;
  encoded: number;
  percentage: number;
  tag_count: number;
  last_updated: string | null;
  error_message: string | null;
}

const POLLING_INTERVAL_MS = 3000;

export default function GeocodingSettingsComponent() {
  const [collapsed, setCollapsed] = useState(true);
  const [status, setStatus] = useState<TagEmbeddingStatus | null>(null);
  const [scope, setScope] = useState<"popular" | "extended">("popular");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const API_BASE_URL = getApiBase();

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(
        `${API_BASE_URL}/settings/geocoding/embedding-status`,
        { credentials: "include" },
      );
      if (res.ok) {
        const data: TagEmbeddingStatus = await res.json();
        setStatus(data);
      }
    } catch {
      // Silently fail — status is optional
    }
  }, [API_BASE_URL]);

  // Fetch initial status when section is expanded
  useEffect(() => {
    if (!collapsed) {
      fetchStatus();
    }
  }, [collapsed, fetchStatus]);

  // Poll while waiting or processing
  useEffect(() => {
    if (collapsed) return;
    const shouldPoll =
      status?.state === "waiting" || status?.state === "processing";
    if (!shouldPoll) return;

    const interval = setInterval(fetchStatus, POLLING_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [collapsed, status?.state, fetchStatus]);

  const triggerPopulate = async (forceRefresh: boolean) => {
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      const res = await fetch(
        `${API_BASE_URL}/settings/geocoding/populate-tags`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ scope, force_refresh: forceRefresh }),
        },
      );
      if (res.ok) {
        const data = await res.json();
        // Optimistically show waiting state
        setStatus((prev) =>
          prev
            ? { ...prev, state: data.state === "already_populated" ? "populated" : "waiting" }
            : null,
        );
        if (data.state !== "already_populated") {
          // Trigger a status refresh after a short delay so polling picks it up
          setTimeout(fetchStatus, 500);
        }
      } else {
        const data = await res.json().catch(() => ({}));
        setErrorMessage(data?.detail || "Failed to start population task.");
      }
    } catch {
      setErrorMessage("Network error — could not reach the server.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const statusDot = () => {
    if (!status) return null;
    const dotColor =
      status.state === "populated"
        ? "bg-green-500"
        : status.state === "error"
          ? "bg-red-500"
          : status.state === "waiting" || status.state === "processing"
            ? "bg-yellow-400 animate-pulse"
            : "bg-yellow-400";
    return <span className={`inline-block w-2.5 h-2.5 rounded-full mr-2 ${dotColor}`} />;
  };

  const statusLabel = () => {
    if (!status) return "Loading…";
    if (status.state === "populated") {
      const updated = status.last_updated
        ? ` · last updated ${status.last_updated.slice(0, 10)}`
        : "";
      return `Populated (${status.tag_count.toLocaleString()} tags${updated})`;
    }
    if (status.state === "processing") {
      return `Building database… ${status.encoded.toLocaleString()} / ${status.total.toLocaleString()} tags`;
    }
    if (status.state === "waiting") return "Waiting to start…";
    if (status.state === "error") return status.error_message || "Error";
    return "Not initialized";
  };

  const isActive = status?.state === "waiting" || status?.state === "processing";
  const isPopulated = status?.state === "populated";

  return (
    <div className="obsidian-panel settings-panel">
      <button
        type="button"
        onClick={() => setCollapsed(!collapsed)}
        className="obsidian-panel-header settings-panel-header"
      >
        <h2 className="obsidian-heading text-lg">
          Geocoding Tag Database
        </h2>
        {collapsed ? (
          <ChevronDown className="h-6 w-6" />
        ) : (
          <ChevronUp className="h-6 w-6" />
        )}
      </button>

      {!collapsed && (
        <div className="obsidian-panel-body settings-panel-body space-y-4">
          <p className="text-sm text-primary-800 dark:text-primary-300">
            Populate a local vector database with OSM tag embeddings to enable
            semantic geocoding. When populated, tag resolution is faster and
            more accurate than pure LLM expansion.
          </p>

          {/* Status */}
          <div className="flex items-center text-sm font-medium text-primary-900 dark:text-primary-100">
            {statusDot()}
            <span>{statusLabel()}</span>
          </div>

          {/* Progress bar (during population) */}
          {isActive && (
            <div>
              <div className="flex justify-between text-xs text-primary-700 dark:text-primary-300 mb-1">
                <span>
                  {status!.state === "waiting"
                    ? "Waiting to start"
                    : "Encoding tags"}
                </span>
                <span>{status!.percentage.toFixed(1)}%</span>
              </div>
              <div
                className="w-full h-2 rounded overflow-hidden"
                style={{ backgroundColor: "var(--primary-200)" }}
              >
                <div
                  className={`h-full transition-all duration-300 ${status!.state === "waiting" ? "animate-pulse" : ""}`}
                  style={{
                    width: `${status!.state === "waiting" ? 5 : status!.percentage}%`,
                    backgroundColor:
                      status!.state === "waiting"
                        ? "var(--secondary-500)"
                        : "var(--second-primary-500)",
                  }}
                />
              </div>
            </div>
          )}

          {/* Error display */}
          {status?.state === "error" && status.error_message && (
            <div className="obsidian-note obsidian-note-danger text-sm font-medium">
              {status.error_message}
            </div>
          )}

          {/* Fallback note when empty */}
          {status?.state === "empty" && (
            <p className="text-sm text-primary-700 dark:text-primary-400 italic">
              Tag resolution will fall back to LLM-only expansion (less
              accurate, higher cost).
            </p>
          )}

          {/* Scope selector */}
          {!isActive && (
            <div className="space-y-1">
              <label
                htmlFor="geocoding-scope"
                className="text-sm font-medium text-primary-900 dark:text-primary-100"
              >
                Tag scope
              </label>
              <select
                id="geocoding-scope"
                value={scope}
                onChange={(e) =>
                  setScope(e.target.value as "popular" | "extended")
                }
                className="obsidian-select"
              >
                <option value="popular">
                  Popular / Wiki tags (recommended)
                </option>
                <option value="extended">Extended (count &gt; 100)</option>
              </select>
            </div>
          )}

          {/* Action buttons */}
          {!isActive && (
            <div className="flex flex-wrap gap-2">
              {!isPopulated ? (
                <button
                  onClick={() => triggerPopulate(false)}
                  disabled={isSubmitting}
                  className={`obsidian-button-primary ${isSubmitting ? "opacity-50 cursor-not-allowed" : ""}`}
                >
                  {isSubmitting ? "Starting…" : "Initialize Tag Database"}
                </button>
              ) : (
                <>
                  <button
                    onClick={() => triggerPopulate(false)}
                    disabled={isSubmitting}
                    className={`obsidian-button-primary ${isSubmitting ? "opacity-50 cursor-not-allowed" : ""}`}
                  >
                    {isSubmitting ? "Starting…" : "Refresh Tag Database"}
                  </button>
                  <button
                    onClick={() => triggerPopulate(true)}
                    disabled={isSubmitting}
                    className={`obsidian-button-danger ${isSubmitting ? "opacity-50 cursor-not-allowed" : ""}`}
                  >
                    {isSubmitting ? "Starting…" : "Clear & Rebuild"}
                  </button>
                </>
              )}
            </div>
          )}

          {/* Submit error */}
          {errorMessage && (
            <p className="text-sm text-red-600 dark:text-red-400 font-medium">
              {errorMessage}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
