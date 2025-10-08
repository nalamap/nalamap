"use client";

import { useState } from "react";
import { useInitializedSettingsStore } from "../../hooks/useInitializedSettingsStore";
import { ChevronDown, ChevronUp } from "lucide-react";

export default function ToolSettingsComponent() {
  const [collapsed, setCollapsed] = useState(true);
  const [toolPromptVisibility, setToolPromptVisibility] = useState<{
    [toolName: string]: boolean;
  }>({});

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
  const availableTools = useInitializedSettingsStore((s) => s.available_tools);

  const [newToolName, setNewToolName] = useState("");

  return (
    <div className="border border-primary-300 rounded bg-white overflow-hidden">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between p-4 hover:bg-primary-50 transition-colors"
      >
        <h2 className="text-2xl font-semibold text-primary-800">
          Tools Configuration
        </h2>
        {collapsed ? (
          <ChevronDown className="w-6 h-6 text-primary-600" />
        ) : (
          <ChevronUp className="w-6 h-6 text-primary-600" />
        )}
      </button>

      {!collapsed && (
        <div className="p-4 pt-0 space-y-4">
          <div className="flex space-x-2">
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
        </div>
      )}
    </div>
  );
}
