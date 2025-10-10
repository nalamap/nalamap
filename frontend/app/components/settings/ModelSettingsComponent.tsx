"use client";

import { useState } from "react";
import { useInitializedSettingsStore } from "../../hooks/useInitializedSettingsStore";
import { ChevronDown, ChevronUp } from "lucide-react";

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
        <div className="p-4 pt-0">
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
        </div>
      )}
    </div>
  );
}
