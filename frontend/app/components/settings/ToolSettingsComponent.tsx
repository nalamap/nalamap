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
    ogcapi: "OGC API",
    attributes: "Attribute Operations",
    styling: "Styling",
    data_retrieval: "Data Retrieval",
    metadata: "Metadata",
    other: "Other",
  };

  return (
    <div className="obsidian-panel settings-panel">
      <button
        type="button"
        onClick={() => setCollapsed(!collapsed)}
        className="obsidian-panel-header settings-panel-header"
      >
        <h2 className="obsidian-heading text-lg">
          Tools Configuration
        </h2>
        {collapsed ? (
          <ChevronDown className="h-6 w-6" />
        ) : (
          <ChevronUp className="h-6 w-6" />
        )}
      </button>

      {!collapsed && (
        <div className="obsidian-panel-body settings-panel-body space-y-4">
          <div className="flex space-x-2">
            <select
              value={newToolName}
              onChange={(e) => setNewToolName(e.target.value)}
              className="obsidian-select flex-grow"
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
                if (newToolName) {
                  addToolConfig(newToolName);
                }
                setNewToolName("");
              }}
              className="obsidian-button-primary px-4 py-2"
            >
              Add Tool
            </button>
          </div>
          
          {/* Display tools grouped by category */}
          {Object.entries(categorizedTools).map(([category, categoryTools]) => (
            <div key={category} className="space-y-2">
              <h3 className="obsidian-kicker pb-1">
                {categoryDisplayNames[category] || category}
              </h3>
              <ul className="space-y-3">
                {categoryTools.map((t, i) => {
                  const toolMeta = toolOptions[t.name];
                  const displayName = toolMeta?.display_name || t.name;
                  const group = toolMeta?.group;
                  
                  return (
                    <li key={i} className="obsidian-card space-y-2">
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
                              className={`font-medium ${t.enabled ? "text-primary-900 dark:text-primary-100" : "text-primary-600 dark:text-primary-600"}`}
                            >
                              {displayName}
                            </span>
                            {group && (
                              <span className="text-xs text-primary-700 dark:text-primary-400">
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
                            className="obsidian-button-ghost px-3 py-2 text-sm"
                          >
                            {toolPromptVisibility[t.name] ? "Hide Prompt" : "Show Prompt"}
                          </button>
                          <button
                            onClick={() => removeToolConfig(t.name)}
                            className="obsidian-button-danger px-3 py-2 text-sm"
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
                          className="obsidian-textarea h-20"
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
