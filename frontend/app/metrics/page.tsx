"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import Sidebar from "../components/sidebar/Sidebar";
import { useUIStore } from "../stores/uiStore";
import { useInitializedSettingsStore } from "../hooks/useInitializedSettingsStore";
import {
  Activity,
  Clock,
  Zap,
  TrendingUp,
  AlertCircle,
  Target,
  CheckCircle,
  XCircle,
  Menu,
  X,
} from "lucide-react";

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
  // Week 3: Tool Usage Analytics
  tool_usage: {
    top_tools: Array<{
      name: string;
      invocations: number;
      successes: number;
      failures: number;
      success_rate: number;
    }>;
    total_invocations: number;
    total_successes: number;
    total_failures: number;
    success_rate: number;
  };
  // Week 3: Tool Selector Performance Monitoring
  tool_selector: {
    enabled: boolean;
    avg_selection_time_ms: number;
    avg_tools_selected: number;
    fallback_count: number;
    fallback_rate: number;
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

function MetricsShell({
  sidebarWidth,
  onHandleMouseDown,
  mobileMenuOpen,
  setMobileMenuOpen,
  children,
}: {
  sidebarWidth: number;
  onHandleMouseDown: (e: React.MouseEvent) => void;
  mobileMenuOpen: boolean;
  setMobileMenuOpen: (open: boolean) => void;
  children: React.ReactNode;
}) {
  return (
    <>
      <button
        className="obsidian-mobile-trigger obsidian-mobile-only top-4 left-4"
        onClick={() => setMobileMenuOpen(true)}
        aria-label="Open metrics navigation"
      >
        <Menu className="h-6 w-6" />
      </button>
      {mobileMenuOpen && (
        <div
          className="obsidian-overlay"
          onClick={() => setMobileMenuOpen(false)}
        >
          <div
            className="obsidian-drawer"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="obsidian-icon-button absolute top-4 right-4"
              onClick={() => setMobileMenuOpen(false)}
              aria-label="Close metrics navigation"
            >
              <X className="h-5 w-5" />
            </button>
            <Sidebar />
          </div>
        </div>
      )}
      <div className="obsidian-shell">
        <div
          className="obsidian-rail hidden md:flex flex-none"
          style={{ flexBasis: `${sidebarWidth}%` }}
        >
          <Sidebar compact />
          <div
            className="obsidian-resize-handle"
            onMouseDown={onHandleMouseDown}
          />
        </div>
        {children}
      </div>
    </>
  );
}

function MetricsStateCard({
  icon,
  title,
  copy,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  copy: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="metrics-state">
      <div className="metrics-state-card">
        <div className="mb-4 flex justify-center">{icon}</div>
        <h2 className="metrics-state-title">{title}</h2>
        <p className="metrics-state-copy">{copy}</p>
        {action && <div className="mt-5 flex justify-center">{action}</div>}
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: React.ReactNode;
  icon: React.ReactNode;
}) {
  return (
    <div className="metrics-card">
      <div className="metrics-card-header">
        <div className="metrics-card-label">{label}</div>
        {icon}
      </div>
      <div className="metrics-card-value">{value}</div>
    </div>
  );
}

function MetricSection({
  title,
  icon,
  badge,
  children,
}: {
  title: string;
  icon?: React.ReactNode;
  badge?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="metrics-section">
      <div className="metrics-section-header">
        <div className="flex items-center gap-3">
          {icon}
          <h2 className="metrics-section-title">{title}</h2>
        </div>
        {badge}
      </div>
      {children}
    </section>
  );
}

function MetricStat({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: React.ReactNode;
  tone?: "default" | "success" | "warning" | "danger";
}) {
  const toneClass =
    tone === "success"
      ? "metrics-tone-success"
      : tone === "warning"
        ? "metrics-tone-warning"
        : tone === "danger"
          ? "metrics-tone-danger"
          : "";

  return (
    <div>
      <div className="metrics-stat-label">{label}</div>
      <div className={`metrics-stat-value ${toneClass}`.trim()}>{value}</div>
    </div>
  );
}

function MetricsNote({
  tone,
  children,
}: {
  tone: "warning" | "danger";
  children: React.ReactNode;
}) {
  return (
    <div className={`metrics-note ${tone === "danger" ? "metrics-note-danger" : "metrics-note-warning"}`}>
      {children}
    </div>
  );
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
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const fetchMetrics = React.useCallback(async () => {
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
  }, [timeRange]);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

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
      <MetricsShell
        sidebarWidth={sidebarWidth}
        onHandleMouseDown={onHandleMouseDown}
        mobileMenuOpen={mobileMenuOpen}
        setMobileMenuOpen={setMobileMenuOpen}
      >
        <main className="obsidian-main-panel obsidian-page-shell">
          <div className="obsidian-page metrics-page">
            <MetricsStateCard
              icon={<Activity className="h-12 w-12 metrics-tone-info animate-pulse" />}
              title="Loading Metrics"
              copy="Collecting current performance snapshots for requests, tools, and model usage."
            />
          </div>
        </main>
      </MetricsShell>
    );
  }

  if (error) {
    return (
      <MetricsShell
        sidebarWidth={sidebarWidth}
        onHandleMouseDown={onHandleMouseDown}
        mobileMenuOpen={mobileMenuOpen}
        setMobileMenuOpen={setMobileMenuOpen}
      >
        <main className="obsidian-main-panel obsidian-page-shell">
          <div className="obsidian-page metrics-page">
            <MetricsStateCard
              icon={<AlertCircle className="h-12 w-12 metrics-tone-danger" />}
              title="Error Loading Metrics"
              copy={error}
              action={
                <button onClick={fetchMetrics} className="obsidian-button-primary">
                  Retry
                </button>
              }
            />
          </div>
        </main>
      </MetricsShell>
    );
  }

  if (!metrics || metrics.total_requests === 0) {
    return (
      <MetricsShell
        sidebarWidth={sidebarWidth}
        onHandleMouseDown={onHandleMouseDown}
        mobileMenuOpen={mobileMenuOpen}
        setMobileMenuOpen={setMobileMenuOpen}
      >
        <main className="obsidian-main-panel obsidian-page-shell">
          <div className="obsidian-page metrics-page">
            <MetricsStateCard
              icon={<Activity className="h-12 w-12 metrics-tone-info" />}
              title="No Metrics Available"
              copy="No metrics data exists for the selected time range. Enable performance metrics in settings and run a few requests."
            />
          </div>
        </main>
      </MetricsShell>
    );
  }

  return (
    <MetricsShell
      sidebarWidth={sidebarWidth}
      onHandleMouseDown={onHandleMouseDown}
      mobileMenuOpen={mobileMenuOpen}
      setMobileMenuOpen={setMobileMenuOpen}
    >
      <main className="obsidian-main-panel obsidian-page-shell">
        <div className="obsidian-page metrics-page">
          <div className="space-y-3">
            <p className="obsidian-kicker">Operations</p>
            <h1 className="obsidian-page-title">Performance Metrics</h1>
            <p className="obsidian-page-copy">
              Agent performance analytics across latency, tool execution,
              selection quality, and token usage.
            </p>
          </div>

          <div className="metrics-toolbar">
            <label htmlFor="metrics-time-range" className="obsidian-form-label">
              Time Range
            </label>
            <select
              id="metrics-time-range"
              value={timeRange}
              onChange={(e) => setTimeRange(Number(e.target.value))}
              className="obsidian-select w-auto min-w-[11rem]"
            >
              <option value={1}>Last Hour</option>
              <option value={6}>Last 6 Hours</option>
              <option value={24}>Last 24 Hours</option>
              <option value={168}>Last Week</option>
            </select>
            <button onClick={fetchMetrics} className="obsidian-button-primary">
              Refresh
            </button>
            {storageInfo && (
              <span className="metrics-toolbar-copy">
                {formatNumber(storageInfo.total_entries)} entries stored
              </span>
            )}
          </div>

          <div className="metrics-summary-grid">
            <MetricCard
              label="Total Requests"
              value={formatNumber(metrics.total_requests)}
              icon={<Activity className="h-5 w-5 metrics-tone-info" />}
            />
            <MetricCard
              label="Avg Response Time"
              value={formatTime(metrics.response_time.avg)}
              icon={<Clock className="h-5 w-5 metrics-tone-info" />}
            />
            <MetricCard
              label="Total LLM Calls"
              value={formatNumber(metrics.llm.total_calls)}
              icon={<Zap className="h-5 w-5 metrics-tone-warning" />}
            />
            <MetricCard
              label="Error Rate"
              value={`${(metrics.errors.rate * 100).toFixed(2)}%`}
              icon={<AlertCircle className="h-5 w-5 metrics-tone-danger" />}
            />
          </div>

          <MetricSection
            title="Response Time Analysis"
            icon={<Clock className="h-5 w-5 metrics-tone-info" />}
          >
            <div className="metrics-stats-grid md:grid-cols-4">
              <MetricStat label="Min" value={formatTime(metrics.response_time.min)} />
              <MetricStat label="Average" value={formatTime(metrics.response_time.avg)} />
              <MetricStat label="P95" value={formatTime(metrics.response_time.p95)} />
              <MetricStat label="Max" value={formatTime(metrics.response_time.max)} />
            </div>
          </MetricSection>

          <MetricSection
            title="LLM Performance"
            icon={<Zap className="h-5 w-5 metrics-tone-warning" />}
          >
            <div className="metrics-stats-grid md:grid-cols-4">
              <MetricStat label="Total Calls" value={formatNumber(metrics.llm.total_calls)} />
              <MetricStat label="Avg per Request" value={metrics.llm.avg_calls_per_request.toFixed(1)} />
              <MetricStat label="Total Time" value={formatTime(metrics.llm.total_time)} />
              <MetricStat label="Avg Time" value={formatTime(metrics.llm.time_stats.avg)} />
            </div>
          </MetricSection>

          <MetricSection
            title="Top Tools"
            icon={<TrendingUp className="h-5 w-5 metrics-tone-info" />}
          >
            {metrics.tools.top_tools.length > 0 ? (
              <div className="space-y-3">
                {metrics.tools.top_tools.slice(0, 10).map((tool, index) => (
                  <div key={tool.name} className="metrics-row">
                    <div className="metrics-row-primary">
                      <span className="metrics-rank">#{index + 1}</span>
                      <span className="metrics-row-title">{tool.name}</span>
                    </div>
                    <div className="metrics-row-meta">
                      <div className="metrics-row-metric">
                        <div className="metrics-stat-label">Calls</div>
                        <div className="metrics-row-value">
                          {formatNumber(tool.total_calls)}
                        </div>
                      </div>
                      <div className="metrics-row-metric">
                        <div className="metrics-stat-label">Avg</div>
                        <div className="metrics-row-value">
                          {formatTime(tool.avg_time)}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="obsidian-status-muted text-sm">
                No tool usage data available.
              </p>
            )}
          </MetricSection>

          {metrics.tool_selector && metrics.tool_selector.enabled && (
            <MetricSection
              title="Tool Selection Performance"
              icon={<Target className="h-5 w-5 metrics-tone-success" />}
              badge={<span className="metrics-badge metrics-badge-success">Week 3</span>}
            >
              <div className="metrics-stats-grid md:grid-cols-4">
                <MetricStat
                  label="Avg Selection Time"
                  value={`${metrics.tool_selector.avg_selection_time_ms.toFixed(1)}ms`}
                />
                <MetricStat
                  label="Avg Tools Selected"
                  value={metrics.tool_selector.avg_tools_selected.toFixed(1)}
                />
                <MetricStat
                  label="Fallback Count"
                  value={formatNumber(metrics.tool_selector.fallback_count)}
                />
                <MetricStat
                  label="Fallback Rate"
                  value={`${(metrics.tool_selector.fallback_rate * 100).toFixed(1)}%`}
                  tone={metrics.tool_selector.fallback_rate > 0.1 ? "warning" : "default"}
                />
              </div>
              {metrics.tool_selector.fallback_rate > 0.1 && (
                <div className="mt-4">
                  <MetricsNote tone="warning">
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>
                      High fallback rate detected. Consider enabling embeddings
                      for semantic tool selection.
                    </span>
                  </MetricsNote>
                </div>
              )}
            </MetricSection>
          )}

          {metrics.tool_usage && metrics.tool_usage.top_tools.length > 0 && (
            <MetricSection
              title="Tool Usage Analytics"
              icon={<Activity className="h-5 w-5 metrics-tone-info" />}
              badge={<span className="metrics-badge metrics-badge-info">Week 3</span>}
            >
              <div className="metrics-stats-grid md:grid-cols-4 mb-6">
                <MetricStat
                  label="Total Invocations"
                  value={formatNumber(metrics.tool_usage.total_invocations)}
                />
                <MetricStat
                  label="Successful"
                  value={
                    <span className="inline-flex items-center gap-1">
                      <CheckCircle className="h-4 w-4" />
                      {formatNumber(metrics.tool_usage.total_successes)}
                    </span>
                  }
                  tone="success"
                />
                <MetricStat
                  label="Failed"
                  value={
                    <span className="inline-flex items-center gap-1">
                      <XCircle className="h-4 w-4" />
                      {formatNumber(metrics.tool_usage.total_failures)}
                    </span>
                  }
                  tone="danger"
                />
                <MetricStat
                  label="Success Rate"
                  value={`${(metrics.tool_usage.success_rate * 100).toFixed(1)}%`}
                  tone={metrics.tool_usage.success_rate < 0.8 ? "danger" : "success"}
                />
              </div>

              <div className="space-y-3">
                <div className="metrics-stat-label">Top Tools by Usage</div>
                {metrics.tool_usage.top_tools.slice(0, 15).map((tool, index) => {
                  const successRate = tool.success_rate * 100;
                  const tone =
                    successRate >= 95
                      ? "success"
                      : successRate >= 80
                        ? "warning"
                        : "danger";

                  return (
                    <div key={tool.name} className="metrics-row">
                      <div className="metrics-row-primary">
                        <span className="metrics-rank">#{index + 1}</span>
                        <span className="metrics-row-title">{tool.name}</span>
                      </div>
                      <div className="metrics-row-meta">
                        <div className="metrics-row-metric">
                          <div className="metrics-stat-label">Invocations</div>
                          <div className="metrics-row-value">
                            {formatNumber(tool.invocations)}
                          </div>
                        </div>
                        <div className="metrics-row-metric">
                          <div className="metrics-stat-label">Success</div>
                          <div className="metrics-row-value metrics-tone-success">
                            {formatNumber(tool.successes)}
                          </div>
                        </div>
                        <div className="metrics-row-metric">
                          <div className="metrics-stat-label">Failed</div>
                          <div className="metrics-row-value metrics-tone-danger">
                            {formatNumber(tool.failures)}
                          </div>
                        </div>
                        <div className="metrics-row-metric">
                          <div className="metrics-stat-label">Rate</div>
                          <div className={`metrics-row-value metrics-tone-${tone}`}>
                            {successRate.toFixed(1)}%
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {metrics.tool_usage.top_tools.some((tool) => tool.success_rate < 0.8) && (
                <div className="mt-4">
                  <MetricsNote tone="danger">
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>
                      Some tools have success rates below 80%. Investigate those
                      failures before relying on them in automated flows.
                    </span>
                  </MetricsNote>
                </div>
              )}
            </MetricSection>
          )}

          <MetricSection title="Token Usage">
            <div className="metrics-stats-grid md:grid-cols-4">
              <MetricStat label="Total Tokens" value={formatNumber(metrics.tokens.total)} />
              <MetricStat
                label="Avg per Request"
                value={formatNumber(Math.round(metrics.tokens.avg_per_request))}
              />
              <MetricStat
                label="Estimated Cost"
                value={(() => {
                  const inputCost = selectedModel?.input_cost_per_million;
                  const outputCost = selectedModel?.output_cost_per_million;

                  if (
                    inputCost === null ||
                    inputCost === undefined ||
                    outputCost === null ||
                    outputCost === undefined
                  ) {
                    return "N/A";
                  }

                  const avgCostPerMillion = (inputCost + outputCost) / 2;
                  const estimatedCost =
                    (metrics.tokens.total / 1_000_000) * avgCostPerMillion;
                  return `$${estimatedCost.toFixed(4)}`;
                })()}
              />
              <MetricStat
                label="Cost Model"
                value={
                  selectedModel?.input_cost_per_million !== null &&
                  selectedModel?.input_cost_per_million !== undefined
                    ? modelSettings.model_name
                    : "Model costs unavailable"
                }
              />
            </div>
          </MetricSection>

          <MetricSection title="Message Pruning Effectiveness">
            <div className="metrics-stats-grid">
              <MetricStat
                label="Total Messages Pruned"
                value={formatNumber(metrics.message_pruning.total_reduction)}
              />
              <MetricStat
                label="Avg per Request"
                value={metrics.message_pruning.avg_reduction.toFixed(1)}
              />
            </div>
          </MetricSection>
        </div>
      </main>
    </MetricsShell>
  );
}
