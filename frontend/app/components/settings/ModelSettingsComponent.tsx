"use client";

import { useState, useMemo } from "react";
import { useInitializedSettingsStore } from "../../hooks/useInitializedSettingsStore";
import { ChevronDown, ChevronUp, Info } from "lucide-react";

export default function ModelSettingsComponent() {
  const [collapsed, setCollapsed] = useState(true);

  const modelSettings = useInitializedSettingsStore((s) => s.model_settings);
  const setModelProvider = useInitializedSettingsStore(
    (s) => s.setModelProvider,
  );
  const setModelName = useInitializedSettingsStore((s) => s.setModelName);
  const setMaxTokens = useInitializedSettingsStore((s) => s.setMaxTokens);
  const setSystemPrompt = useInitializedSettingsStore((s) => s.setSystemPrompt);

  const availableProviders = useInitializedSettingsStore(
    (s) => s.available_model_providers,
  );
  const availableModelNames = useInitializedSettingsStore(
    (s) => s.available_model_names,
  );
  const modelOptions = useInitializedSettingsStore((s) => s.model_options);
  const setAvailableModelNames = useInitializedSettingsStore(
    (s) => s.setAvailableModelNames,
  );

  // Get currently selected model details
  const selectedModel = useMemo(() => {
    const models = modelOptions[modelSettings.model_provider] || [];
    return models.find((m) => m.name === modelSettings.model_name);
  }, [modelOptions, modelSettings.model_provider, modelSettings.model_name]);

  // Format cost for display
  const formatCost = (cost: number | null | undefined) => {
    if (cost === null || cost === undefined) return "N/A";
    return `$${cost.toFixed(2)}`;
  };

  return (
    <div className="border border-primary-300 rounded bg-neutral-50 dark:bg-neutral-900 overflow-hidden">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between px-4 py-3 bg-primary-100 hover:bg-primary-200 dark:bg-primary-900 dark:hover:bg-primary-800 transition-colors"
      >
        <h2 className="text-lg font-semibold text-primary-900 dark:text-primary-100">
          Model Settings
        </h2>
        {collapsed ? (
          <ChevronDown className="w-6 h-6 text-primary-600" />
        ) : (
          <ChevronUp className="w-6 h-6 text-primary-600" />
        )}
      </button>

      {!collapsed && (
        <div className="p-4 pt-0 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-1">
                Provider
              </label>
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
                className="w-full border border-primary-300 rounded p-2 bg-white dark:bg-neutral-800 text-primary-900 dark:text-primary-100"
              >
                {availableProviders.map((prov) => (
                  <option key={prov} value={prov}>
                    {prov.charAt(0).toUpperCase() + prov.slice(1)}
                  </option>
                ))}
              </select>
            </div>

            <div className="col-span-2">
              <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-1">
                Model
              </label>
              <select
                value={modelSettings.model_name}
                onChange={(e) => {
                  const newModelName = e.target.value;
                  setModelName(newModelName);
                  const models = modelOptions[modelSettings.model_provider] || [];
                  const selectedModelData = models.find((m) => m.name === newModelName);
                  if (selectedModelData) {
                    setMaxTokens(selectedModelData.max_tokens);
                  }
                }}
                className="w-full border border-primary-300 rounded p-2 bg-white dark:bg-neutral-800 text-primary-900 dark:text-primary-100"
              >
                {availableModelNames.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </div>

            <div className="col-span-2">
              <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-1">
                Max Tokens
              </label>
              <input
                type="number"
                value={modelSettings.max_tokens}
                onChange={(e) => setMaxTokens(Number(e.target.value))}
                placeholder="Max Tokens"
                className="w-full border border-primary-300 rounded p-2 bg-white dark:bg-neutral-800 text-primary-900 dark:text-primary-100"
              />
            </div>
          </div>

          {/* Model Information Card */}
          {selectedModel && (
            <div className="border border-secondary-300 rounded bg-secondary-50 dark:bg-secondary-950 p-3 space-y-2">
              <div className="flex items-start gap-2">
                <Info className="w-4 h-4 text-secondary-600 dark:text-secondary-400 flex-shrink-0 mt-0.5" />
                <div className="flex-1 space-y-2">
                  {selectedModel.description && (
                    <p className="text-sm text-primary-700 dark:text-primary-300">
                      {selectedModel.description}
                    </p>
                  )}

                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {(selectedModel.input_cost_per_million !== null &&
                      selectedModel.input_cost_per_million !== undefined) && (
                      <div>
                        <span className="text-primary-600 dark:text-primary-400 font-medium">
                          Input:
                        </span>{" "}
                        <span className="text-primary-800 dark:text-primary-200">
                          {formatCost(selectedModel.input_cost_per_million)}/M tokens
                        </span>
                      </div>
                    )}

                    {(selectedModel.output_cost_per_million !== null &&
                      selectedModel.output_cost_per_million !== undefined) && (
                      <div>
                        <span className="text-primary-600 dark:text-primary-400 font-medium">
                          Output:
                        </span>{" "}
                        <span className="text-primary-800 dark:text-primary-200">
                          {formatCost(selectedModel.output_cost_per_million)}/M tokens
                        </span>
                      </div>
                    )}

                    {(selectedModel.cache_cost_per_million !== null &&
                      selectedModel.cache_cost_per_million !== undefined) && (
                      <div>
                        <span className="text-primary-600 dark:text-primary-400 font-medium">
                          Cache:
                        </span>{" "}
                        <span className="text-primary-800 dark:text-primary-200">
                          {formatCost(selectedModel.cache_cost_per_million)}/M tokens
                        </span>
                      </div>
                    )}

                    {selectedModel.supports_tools && (
                      <div className="flex items-center gap-1">
                        <span className="text-tertiary-600 dark:text-tertiary-400">
                          ✓ Tools
                        </span>
                      </div>
                    )}

                    {selectedModel.supports_vision && (
                      <div className="flex items-center gap-1">
                        <span className="text-tertiary-600 dark:text-tertiary-400">
                          ✓ Vision
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-1">
              System Prompt
            </label>
            <textarea
              value={modelSettings.system_prompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="Optional system prompt override..."
              className="w-full border border-primary-300 rounded p-2 h-24 bg-white dark:bg-neutral-800 text-primary-900 dark:text-primary-100"
            />
          </div>
        </div>
      )}
    </div>
  );
}

