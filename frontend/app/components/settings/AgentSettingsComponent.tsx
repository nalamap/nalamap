"use client";

import { useState } from "react";
import { useInitializedSettingsStore } from "../../hooks/useInitializedSettingsStore";
import { ChevronDown, ChevronUp, Info } from "lucide-react";

export default function AgentSettingsComponent() {
  const [collapsed, setCollapsed] = useState(true);

  const modelSettings = useInitializedSettingsStore((s) => s.model_settings);
  const setSystemPrompt = useInitializedSettingsStore((s) => s.setSystemPrompt);
  const setEnableDynamicTools = useInitializedSettingsStore(
    (s) => s.setEnableDynamicTools,
  );
  const setToolSelectionStrategy = useInitializedSettingsStore(
    (s) => s.setToolSelectionStrategy,
  );
  const setToolSimilarityThreshold = useInitializedSettingsStore(
    (s) => s.setToolSimilarityThreshold,
  );
  const setMaxToolsPerQuery = useInitializedSettingsStore(
    (s) => s.setMaxToolsPerQuery,
  );
  const setUseSummarization = useInitializedSettingsStore(
    (s) => s.setUseSummarization,
  );

  const toolStrategies = [
    { value: "all", label: "All Tools", description: "Provide all available tools (default behavior)" },
    { value: "semantic", label: "Semantic Matching", description: "Select tools based on query similarity" },
    { value: "conservative", label: "Conservative", description: "Balanced selection with common tools" },
    { value: "minimal", label: "Minimal", description: "Only most relevant tools for the query" },
  ];

  return (
    <div className="border border-primary-300 dark:border-primary-700 rounded bg-primary-50 dark:bg-neutral-900 overflow-hidden">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between px-4 py-3 bg-primary-100 hover:bg-primary-200 dark:bg-primary-900 dark:hover:bg-primary-800 transition-colors"
      >
        <h2 className="text-lg font-semibold text-primary-900 dark:text-primary-100">
          Agent Settings
        </h2>
        {collapsed ? (
          <ChevronDown className="w-6 h-6 text-primary-600 dark:text-primary-400" />
        ) : (
          <ChevronUp className="w-6 h-6 text-primary-600 dark:text-primary-400" />
        )}
      </button>

      {!collapsed && (
        <div className="p-4 pt-0 space-y-4">
          {/* System Prompt */}
          <div>
            <label className="block text-sm font-medium text-primary-900 dark:text-primary-300 mb-1">
              System Prompt
            </label>
            <textarea
              value={modelSettings.system_prompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="Optional system prompt override..."
              className="w-full border border-primary-300 dark:border-primary-700 rounded p-2 h-24 bg-primary-50 dark:bg-primary-950 text-primary-900 dark:text-primary-100"
            />
            <p className="text-xs text-primary-700 dark:text-primary-400 mt-1">
              Customize the agent's behavior and personality
            </p>
          </div>

          {/* Enable Dynamic Tool Selection */}
          <div className="col-span-2">
            <div className="flex items-start gap-2">
              <input
                type="checkbox"
                id="enable-dynamic-tools"
                checked={modelSettings.enable_dynamic_tools ?? false}
                onChange={(e) => setEnableDynamicTools(e.target.checked)}
                className="mt-1 h-4 w-4 rounded border-primary-300 dark:border-primary-700 text-tertiary-600 focus:ring-tertiary-500"
              />
              <div className="flex-1">
                <label
                  htmlFor="enable-dynamic-tools"
                  className="text-sm font-medium text-primary-900 dark:text-primary-300 cursor-pointer"
                >
                  Enable Dynamic Tool Selection
                </label>
                <p className="text-xs text-primary-700 dark:text-primary-400 mt-1">
                  Intelligently select tools based on the query using semantic similarity.
                  Reduces token usage and improves response times by providing only relevant tools.
                  Works with all languages through embeddings.
                </p>
              </div>
            </div>
          </div>

          {/* Dynamic Tool Settings (shown when enabled) */}
          {modelSettings.enable_dynamic_tools && (
            <>
              {/* Tool Selection Strategy */}
              <div>
                <label className="block text-sm font-medium text-primary-900 dark:text-primary-300 mb-1">
                  Tool Selection Strategy
                </label>
                <select
                  value={modelSettings.tool_selection_strategy || "conservative"}
                  onChange={(e) => setToolSelectionStrategy(e.target.value)}
                  className="w-full border border-primary-300 dark:border-primary-700 rounded p-2 bg-primary-50 dark:bg-primary-950 text-primary-900 dark:text-primary-100"
                >
                  {toolStrategies.map((strategy) => (
                    <option key={strategy.value} value={strategy.value} className="bg-primary-50 text-primary-900">
                      {strategy.label}
                    </option>
                  ))}
                </select>
                <div className="mt-2 space-y-1">
                  {toolStrategies.map((strategy) => (
                    <div
                      key={strategy.value}
                      className={`text-xs p-2 rounded ${
                        modelSettings.tool_selection_strategy === strategy.value
                          ? "bg-tertiary-100 dark:bg-tertiary-900 text-tertiary-900 dark:text-tertiary-100"
                          : "bg-primary-100 dark:bg-primary-800 text-primary-700 dark:text-primary-400"
                      }`}
                    >
                      <span className="font-semibold">{strategy.label}:</span> {strategy.description}
                    </div>
                  ))}
                </div>
              </div>

              {/* Tool Similarity Threshold */}
              <div>
                <label className="block text-sm font-medium text-primary-900 dark:text-primary-300 mb-1">
                  Tool Similarity Threshold: {modelSettings.tool_similarity_threshold?.toFixed(2) ?? "0.30"}
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={modelSettings.tool_similarity_threshold ?? 0.3}
                  onChange={(e) => setToolSimilarityThreshold(Number(e.target.value))}
                  className="w-full h-2 bg-primary-200 dark:bg-primary-800 rounded-lg appearance-none cursor-pointer accent-tertiary-600"
                />
                <div className="flex justify-between text-xs text-primary-700 dark:text-primary-400 mt-1">
                  <span>0.00 (More tools)</span>
                  <span>1.00 (Fewer tools)</span>
                </div>
                <p className="text-xs text-primary-700 dark:text-primary-400 mt-1">
                  Minimum similarity score for tool selection. Lower values include more tools, higher values are more selective.
                </p>
              </div>

              {/* Max Tools Per Query */}
              <div>
                <label className="block text-sm font-medium text-primary-900 dark:text-primary-300 mb-1">
                  Max Tools Per Query
                  <span className="text-xs text-primary-700 dark:text-primary-400 ml-1">
                    (optional)
                  </span>
                </label>
                <input
                  type="number"
                  value={modelSettings.max_tools_per_query ?? ""}
                  onChange={(e) => {
                    const value = e.target.value;
                    if (value === "" || value === null) {
                      setMaxToolsPerQuery(null);
                    } else {
                      const numValue = Number(value);
                      setMaxToolsPerQuery(Math.max(1, numValue));
                    }
                  }}
                  min="1"
                  placeholder="Unlimited"
                  className="w-full border border-primary-300 dark:border-primary-700 rounded p-2 bg-primary-50 dark:bg-primary-950 text-primary-900 dark:text-primary-100"
                />
                <p className="text-xs text-primary-700 dark:text-primary-400 mt-1">
                  Maximum number of tools to provide to the agent. Leave empty for unlimited.
                </p>
              </div>

              {/* Information Banner */}
              <div className="border border-info-300 dark:border-info-700 rounded bg-info-50 dark:bg-info-900 p-3">
                <div className="flex items-start gap-2">
                  <Info className="w-4 h-4 text-info-600 dark:text-info-400 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <p className="text-xs text-info-900 dark:text-info-200">
                      <span className="font-semibold">Dynamic Tool Selection Benefits:</span>
                    </p>
                    <ul className="text-xs text-info-800 dark:text-info-300 mt-1 space-y-0.5 list-disc list-inside">
                      <li>Reduces token usage by providing only relevant tools</li>
                      <li>Improves response times with smaller context</li>
                      <li>Works with any language through semantic similarity</li>
                      <li>Automatic fallback to all tools if embeddings unavailable</li>
                    </ul>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Enable Conversation Summarization */}
          <div className="col-span-2">
            <div className="flex items-start gap-2">
              <input
                type="checkbox"
                id="enable-summarization"
                checked={modelSettings.use_summarization ?? false}
                onChange={(e) => setUseSummarization(e.target.checked)}
                className="mt-1 h-4 w-4 rounded border-primary-300 dark:border-primary-700 text-tertiary-600 focus:ring-tertiary-500"
              />
              <div className="flex-1">
                <label
                  htmlFor="enable-summarization"
                  className="text-sm font-medium text-primary-900 dark:text-primary-300 cursor-pointer"
                >
                  Enable Conversation Summarization
                </label>
                <p className="text-xs text-primary-700 dark:text-primary-400 mt-1">
                  Automatically condense older messages in long conversations to reduce token usage.
                  Recent messages are preserved while older messages are summarized by the LLM.
                  Requires a session ID for tracking conversation state.
                </p>
                <div className="mt-2 border border-info-300 dark:border-info-700 rounded bg-info-50 dark:bg-info-900 p-2">
                  <div className="flex items-start gap-2">
                    <Info className="w-3 h-3 text-info-600 dark:text-info-400 flex-shrink-0 mt-0.5" />
                    <p className="text-xs text-info-900 dark:text-info-200">
                      <span className="font-semibold">Benefits:</span> Enables infinite conversation length,
                      reduces token costs by 50-80%, maintains context quality. Automatically triggers
                      when conversation exceeds threshold.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
