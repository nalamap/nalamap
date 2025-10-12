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
  const toolOptions = useInitializedSettingsStore((s) => s.tool_options);

  const [newToolName, setNewToolName] = useState("");

  // Group tools by category
  const categorizedTools: { [category: string]: typeof tools } = {};
  tools.forEach((tool) => {
    const category = toolOptions[tool.name]?.category || "other";
    if (!categorizedTools[category]) {
      categorizedTools[category] = [];
    }
    categorizedTools[category].push(tool);
  });

  const categoryDisplayNames: { [key: string]: string } = {
    geocoding: "Geocoding",
    geoprocessing: "Geoprocessing",
    attributes: "Attribute Operations",
    styling: "Styling",
    data_retrieval: "Data Retrieval",
    metadata: "Metadata",
    other: "Other",
  };

  return (
    <div className="border border-primary-300 rounded bg-neutral-50 dark:bg-neutral-900 overflow-hidden">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between px-4 py-3 bg-primary-100 hover:bg-primary-200 dark:bg-primary-900 dark:hover:bg-primary-800 transition-colors"
      >
        <h2 className="text-lg font-semibold text-primary-900 dark:text-primary-100">
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
                  {toolOptions[tool]?.display_name || tool}
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
          
          {/* Display tools grouped by category */}
          {Object.entries(categorizedTools).map(([category, categoryTools]) => (
            <div key={category} className="space-y-2">
              <h3 className="text-sm font-semibold text-primary-700 dark:text-primary-300 uppercase tracking-wide border-b border-primary-200 pb-1">
                {categoryDisplayNames[category] || category}
              </h3>
              <ul className="space-y-3">
                {categoryTools.map((t, i) => {
                  const toolMeta = toolOptions[t.name];
                  const displayName = toolMeta?.display_name || t.name;
                  const group = toolMeta?.group;
                  
                  return (
                    <li key={i} className="border border-primary-200 rounded p-4 space-y-2 bg-white dark:bg-neutral-800">
                      <div className="flex justify-between items-center">
                        <label className="flex items-center space-x-2">
                          <input
                            type="checkbox"
                            checked={t.enabled}
                            onChange={() => toggleToolConfig(t.name)}
                            className="form-checkbox h-5 w-5 text-tertiary-600"
                          />
                          <div className="flex flex-col">
                            <span
                              className={`font-medium ${t.enabled ? "text-primary-900 dark:text-primary-100" : "text-primary-400 dark:text-primary-600"}`}
                            >
                              {displayName}
                            </span>
                            {group && (
                              <span className="text-xs text-primary-500 dark:text-primary-400">
                                Group: {group}
                              </span>
                            )}
                          </div>
                        </label>
                        <div className="flex items-center space-x-2">
                          <button
                            onClick={() =>
                              setToolPromptVisibility((prev) => ({
                                ...prev,
                                [t.name]: !prev[t.name],
                              }))
                            }
                            className="text-primary-600 hover:text-primary-800 dark:text-primary-400 dark:hover:text-primary-200 font-medium text-sm"
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
                          className="border border-primary-300 rounded p-2 w-full h-20 bg-white dark:bg-neutral-700 text-primary-900 dark:text-primary-100"
                        />
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
