"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import Sidebar from "../components/sidebar/Sidebar";
import { useUIStore } from "../stores/uiStore";
import { useInitializedSettingsStore } from "../hooks/useInitializedSettingsStore";
import { Activity, Clock, Zap, TrendingUp, AlertCircle } from "lucide-react";

interface MetricsStats {
  period_hours: number;
  total_requests: number;
  time_range?: {
    start: string;
    end: string;
  };
  response_time: {
    min: number;
    max: number;
    avg: number;
    median: number;
    p50: number;
    p95: number;
    p99: number;
  };
  agent_execution_time: {
    min: number;
    max: number;
    avg: number;
    median: number;
    p50: number;
    p95: number;
    p99: number;
  };
  llm: {
    total_calls: number;
    avg_calls_per_request: number;
    total_time: number;
    time_stats: {
      min: number;
      max: number;
      avg: number;
    };
  };
  tools: {
    total_calls: number;
    avg_calls_per_request: number;
    top_tools: Array<{
      name: string;
      total_calls: number;
      avg_time: number;
      min_time: number;
      max_time: number;
    }>;
  };
  tokens: {
    total: number;
    avg_per_request: number;
    stats: {
      min: number;
      max: number;
      avg: number;
    };
  };
  message_pruning: {
    total_reduction: number;
    avg_reduction: number;
  };
  errors: {
    total: number;
    rate: number;
  };
}

interface MetricsResponse {
  status: string;
  data: MetricsStats;
  storage_info: {
    total_entries: number;
  };
}

export default function MetricsPage() {
  // UI store for layout
  const sidebarWidth = useUIStore((s) => s.sidebarWidth);
  const setSidebarWidth = useUIStore((s) => s.setSidebarWidth);
  
  // Get model settings for cost calculation
  const modelSettings = useInitializedSettingsStore((s) => s.model_settings);
  const modelOptions = useInitializedSettingsStore((s) => s.model_options);
  
  // Get currently selected model details for cost estimation
  const selectedModel = useMemo(() => {
    const models = modelOptions[modelSettings.model_provider] || [];
    return models.find((m) => m.name === modelSettings.model_name);
  }, [modelOptions, modelSettings.model_provider, modelSettings.model_name]);
  
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

  const [metrics, setMetrics] = useState<MetricsStats | null>(null);
  const [storageInfo, setStorageInfo] = useState<{ total_entries: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState(1); // hours

  const fetchMetrics = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}/metrics?hours=${timeRange}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch metrics: ${response.statusText}`);
      }
      const data: MetricsResponse = await response.json();
      setMetrics(data.data);
      setStorageInfo(data.storage_info);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch metrics");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, [timeRange]);

  const formatTime = (seconds: number): string => {
    if (seconds < 1) {
      return `${Math.round(seconds * 1000)}ms`;
    }
    return `${seconds.toFixed(2)}s`;
  };

  const formatNumber = (num: number): string => {
    return num.toLocaleString();
  };

  if (loading) {
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
          <main className="flex-1 overflow-auto bg-primary-50 flex items-center justify-center">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-tertiary-600 mx-auto mb-4"></div>
              <p className="text-primary-700">Loading metrics...</p>
            </div>
          </main>
        </div>
      </>
    );
  }

  if (error) {
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
          <main className="flex-1 overflow-auto bg-primary-50 flex items-center justify-center">
            <div className="text-center max-w-md">
              <AlertCircle className="h-12 w-12 text-danger-600 mx-auto mb-4" />
              <h2 className="text-xl font-semibold text-primary-900 mb-2">
                Error Loading Metrics
              </h2>
              <p className="text-primary-700 mb-4">{error}</p>
              <button
                onClick={fetchMetrics}
                className="px-4 py-2 bg-tertiary-600 text-white rounded hover:bg-tertiary-700 transition-colors"
              >
                Retry
              </button>
            </div>
          </main>
        </div>
      </>
    );
  }

  if (!metrics || metrics.total_requests === 0) {
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
          <main className="flex-1 overflow-auto bg-primary-50 flex items-center justify-center">
            <div className="text-center max-w-md">
              <Activity className="h-12 w-12 text-primary-400 mx-auto mb-4" />
              <h2 className="text-xl font-semibold text-primary-900 mb-2">
                No Metrics Available
              </h2>
              <p className="text-primary-700 mb-4">
                No metrics data for the selected time range. Enable performance metrics in settings and make some requests.
              </p>
            </div>
          </main>
        </div>
      </>
    );
  }

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
          <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-primary-900 mb-2">
            Performance Metrics
          </h1>
          <p className="text-primary-700">
            Agent performance analytics and statistics
          </p>
        </div>

        {/* Time Range Selector */}
        <div className="mb-6 flex items-center gap-4">
          <label className="text-sm font-medium text-primary-900">
            Time Range:
          </label>
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(Number(e.target.value))}
            className="px-3 py-2 border border-primary-300 rounded bg-white text-primary-900"
          >
            <option value={1}>Last Hour</option>
            <option value={6}>Last 6 Hours</option>
            <option value={24}>Last 24 Hours</option>
            <option value={168}>Last Week</option>
          </select>
          <button
            onClick={fetchMetrics}
            className="px-4 py-2 bg-tertiary-600 text-white rounded hover:bg-tertiary-700 transition-colors"
          >
            Refresh
          </button>
          {storageInfo && (
            <span className="text-sm text-primary-600 ml-auto">
              {formatNumber(storageInfo.total_entries)} entries stored
            </span>
          )}
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {/* Total Requests */}
          <div className="bg-white rounded-lg shadow p-6 border border-primary-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-primary-600">
                Total Requests
              </span>
              <Activity className="h-5 w-5 text-tertiary-600" />
            </div>
            <div className="text-2xl font-bold text-primary-900">
              {formatNumber(metrics.total_requests)}
            </div>
          </div>

          {/* Avg Response Time */}
          <div className="bg-white rounded-lg shadow p-6 border border-primary-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-primary-600">
                Avg Response Time
              </span>
              <Clock className="h-5 w-5 text-info-600" />
            </div>
            <div className="text-2xl font-bold text-primary-900">
              {formatTime(metrics.response_time.avg)}
            </div>
          </div>

          {/* Total LLM Calls */}
          <div className="bg-white rounded-lg shadow p-6 border border-primary-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-primary-600">
                Total LLM Calls
              </span>
              <Zap className="h-5 w-5 text-warning-600" />
            </div>
            <div className="text-2xl font-bold text-primary-900">
              {formatNumber(metrics.llm.total_calls)}
            </div>
          </div>

          {/* Error Rate */}
          <div className="bg-white rounded-lg shadow p-6 border border-primary-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-primary-600">
                Error Rate
              </span>
              <AlertCircle className="h-5 w-5 text-danger-600" />
            </div>
            <div className="text-2xl font-bold text-primary-900">
              {(metrics.errors.rate * 100).toFixed(2)}%
            </div>
          </div>
        </div>

        {/* Response Time Details */}
        <div className="bg-white rounded-lg shadow p-6 border border-primary-200 mb-6">
          <h2 className="text-lg font-semibold text-primary-900 mb-4 flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Response Time Analysis
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="text-xs text-primary-600 mb-1">Min</div>
              <div className="text-lg font-semibold text-primary-900">
                {formatTime(metrics.response_time.min)}
              </div>
            </div>
            <div>
              <div className="text-xs text-primary-600 mb-1">Average</div>
              <div className="text-lg font-semibold text-primary-900">
                {formatTime(metrics.response_time.avg)}
              </div>
            </div>
            <div>
              <div className="text-xs text-primary-600 mb-1">P95</div>
              <div className="text-lg font-semibold text-primary-900">
                {formatTime(metrics.response_time.p95)}
              </div>
            </div>
            <div>
              <div className="text-xs text-primary-600 mb-1">Max</div>
              <div className="text-lg font-semibold text-primary-900">
                {formatTime(metrics.response_time.max)}
              </div>
            </div>
          </div>
        </div>

        {/* LLM Performance */}
        <div className="bg-white rounded-lg shadow p-6 border border-primary-200 mb-6">
          <h2 className="text-lg font-semibold text-primary-900 mb-4 flex items-center gap-2">
            <Zap className="h-5 w-5" />
            LLM Performance
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="text-xs text-primary-600 mb-1">Total Calls</div>
              <div className="text-lg font-semibold text-primary-900">
                {formatNumber(metrics.llm.total_calls)}
              </div>
            </div>
            <div>
              <div className="text-xs text-primary-600 mb-1">Avg per Request</div>
              <div className="text-lg font-semibold text-primary-900">
                {metrics.llm.avg_calls_per_request.toFixed(1)}
              </div>
            </div>
            <div>
              <div className="text-xs text-primary-600 mb-1">Total Time</div>
              <div className="text-lg font-semibold text-primary-900">
                {formatTime(metrics.llm.total_time)}
              </div>
            </div>
            <div>
              <div className="text-xs text-primary-600 mb-1">Avg Time</div>
              <div className="text-lg font-semibold text-primary-900">
                {formatTime(metrics.llm.time_stats.avg)}
              </div>
            </div>
          </div>
        </div>

        {/* Top Tools */}
        <div className="bg-white rounded-lg shadow p-6 border border-primary-200 mb-6">
          <h2 className="text-lg font-semibold text-primary-900 mb-4 flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Top Tools
          </h2>
          {metrics.tools.top_tools.length > 0 ? (
            <div className="space-y-3">
              {metrics.tools.top_tools.slice(0, 10).map((tool, index) => (
                <div key={tool.name} className="flex items-center justify-between">
                  <div className="flex items-center gap-3 flex-1">
                    <span className="text-sm font-medium text-primary-600 w-6">
                      #{index + 1}
                    </span>
                    <span className="font-medium text-primary-900 flex-1">
                      {tool.name}
                    </span>
                  </div>
                  <div className="flex items-center gap-6 text-sm">
                    <div>
                      <span className="text-primary-600">Calls: </span>
                      <span className="font-semibold text-primary-900">
                        {formatNumber(tool.total_calls)}
                      </span>
                    </div>
                    <div>
                      <span className="text-primary-600">Avg: </span>
                      <span className="font-semibold text-primary-900">
                        {formatTime(tool.avg_time)}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-primary-600 text-sm">No tool usage data available</p>
          )}
        </div>

        {/* Token Usage */}
        <div className="bg-white rounded-lg shadow p-6 border border-primary-200 mb-6">
          <h2 className="text-lg font-semibold text-primary-900 mb-4">
            Token Usage
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div>
              <div className="text-xs text-primary-600 mb-1">Total Tokens</div>
              <div className="text-lg font-semibold text-primary-900">
                {formatNumber(metrics.tokens.total)}
              </div>
            </div>
            <div>
              <div className="text-xs text-primary-600 mb-1">Avg per Request</div>
              <div className="text-lg font-semibold text-primary-900">
                {formatNumber(Math.round(metrics.tokens.avg_per_request))}
              </div>
            </div>
            <div>
              <div className="text-xs text-primary-600 mb-1">Estimated Cost</div>
              <div className="text-lg font-semibold text-primary-900">
                {(() => {
                  // Use actual model costs if available, otherwise show N/A
                  const inputCost = selectedModel?.input_cost_per_million;
                  const outputCost = selectedModel?.output_cost_per_million;
                  
                  if (inputCost === null || inputCost === undefined || 
                      outputCost === null || outputCost === undefined) {
                    return "N/A";
                  }
                  
                  // Rough estimate using average of input/output costs
                  // For more accuracy, we'd need separate input/output token counts from backend
                  const avgCostPerMillion = (inputCost + outputCost) / 2;
                  const estimatedCost = (metrics.tokens.total / 1000000) * avgCostPerMillion;
                  return `$${estimatedCost.toFixed(4)}`;
                })()}
              </div>
              <div className="text-xs text-primary-600">
                {selectedModel?.input_cost_per_million !== null && 
                 selectedModel?.input_cost_per_million !== undefined ? (
                  `Based on ${modelSettings.model_name}`
                ) : (
                  "Model costs not available"
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Message Pruning */}
        <div className="bg-white rounded-lg shadow p-6 border border-primary-200">
          <h2 className="text-lg font-semibold text-primary-900 mb-4">
            Message Pruning Effectiveness
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-xs text-primary-600 mb-1">Total Messages Pruned</div>
              <div className="text-lg font-semibold text-primary-900">
                {formatNumber(metrics.message_pruning.total_reduction)}
              </div>
            </div>
            <div>
              <div className="text-xs text-primary-600 mb-1">Avg per Request</div>
              <div className="text-lg font-semibold text-primary-900">
                {metrics.message_pruning.avg_reduction.toFixed(1)}
              </div>
            </div>
          </div>
        </div>
          </div>
        </main>
      </div>
    </>
  );
}
