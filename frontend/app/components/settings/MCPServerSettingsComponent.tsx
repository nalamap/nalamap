"use client";

import { useState } from "react";
import { useInitializedSettingsStore } from "../../hooks/useInitializedSettingsStore";
import { ChevronDown, ChevronUp, Plus, X } from "lucide-react";
import { MCPServer } from "../../stores/settingsStore";

export default function MCPServerSettingsComponent() {
  const [collapsed, setCollapsed] = useState(true);
  const [selectedExampleMCPServer, setSelectedExampleMCPServer] = useState("");
  const [newMCPServer, setNewMCPServer] = useState<Omit<MCPServer, "enabled">>({
    url: "",
    name: "",
    description: "",
    api_key: "",
    headers: {},
  });
  const [newHeaderKey, setNewHeaderKey] = useState("");
  const [newHeaderValue, setNewHeaderValue] = useState("");

  const mcpServers = useInitializedSettingsStore((s) => s.mcp_servers);
  const addMCPServer = useInitializedSettingsStore((s) => s.addMCPServer);
  const removeMCPServer = useInitializedSettingsStore((s) => s.removeMCPServer);
  const toggleMCPServer = useInitializedSettingsStore((s) => s.toggleMCPServer);
  const availableExampleMCPServers = useInitializedSettingsStore(
    (s) => s.available_example_mcp_servers,
  );

  const handleAddExampleMCPServer = () => {
    const selected = availableExampleMCPServers.find(
      (server) => server.url === selectedExampleMCPServer,
    );
    if (selected) {
      addMCPServer({
        url: selected.url,
        name: selected.name,
        description: selected.description,
        enabled: true,
      });
      setSelectedExampleMCPServer("");
    }
  };

  const handleAddCustomMCPServer = () => {
    if (!newMCPServer.url.trim()) return;
    addMCPServer({
      ...newMCPServer,
      enabled: true,
    });
    setNewMCPServer({ url: "", name: "", description: "", api_key: "", headers: {} });
    setNewHeaderKey("");
    setNewHeaderValue("");
  };

  const handleAddHeader = () => {
    if (!newHeaderKey.trim() || !newHeaderValue.trim()) return;
    setNewMCPServer({
      ...newMCPServer,
      headers: {
        ...newMCPServer.headers,
        [newHeaderKey]: newHeaderValue,
      },
    });
    setNewHeaderKey("");
    setNewHeaderValue("");
  };

  const handleRemoveHeader = (key: string) => {
    const { [key]: removed, ...remainingHeaders } = newMCPServer.headers || {};
    setNewMCPServer({
      ...newMCPServer,
      headers: remainingHeaders,
    });
  };

  return (
    <div className="border border-primary-300 rounded bg-primary-50 dark:bg-neutral-900 overflow-hidden">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between px-4 py-3 bg-primary-100 hover:bg-primary-200 dark:bg-primary-900 dark:hover:bg-primary-800 transition-colors"
      >
        <h2 className="text-lg font-semibold text-primary-900 dark:text-primary-100">
          MCP Servers
        </h2>
        {collapsed ? (
          <ChevronDown className="w-6 h-6 text-primary-600 dark:text-primary-400" />
        ) : (
          <ChevronUp className="w-6 h-6 text-primary-600 dark:text-primary-400" />
        )}
      </button>

      {!collapsed && (
        <div className="p-4 pt-0 space-y-6">
          {/* Example MCP Servers Section */}
          {availableExampleMCPServers && availableExampleMCPServers.length > 0 && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-primary-900 dark:text-primary-100">
                Example MCP Servers
              </h3>
              <p className="text-sm text-primary-800 dark:text-primary-300">
                Choose from example Model Context Protocol servers to extend the agent with additional tools.
              </p>
              <div className="flex space-x-2 mb-4">
                <select
                  value={selectedExampleMCPServer}
                  onChange={(e) => setSelectedExampleMCPServer(e.target.value)}
                  className="border border-primary-300 dark:border-primary-700 rounded p-2 flex-grow bg-primary-50 dark:bg-primary-950 text-primary-900 dark:text-primary-100"
                >
                  <option value="" className="bg-primary-50 text-primary-900">
                    Select an example MCP server
                  </option>
                  {availableExampleMCPServers.map((server) => (
                    <option
                      key={server.url}
                      value={server.url}
                      className="bg-primary-50 text-primary-900"
                    >
                      {server.name} - {server.url}
                    </option>
                  ))}
                </select>
                <button
                  onClick={handleAddExampleMCPServer}
                  disabled={!selectedExampleMCPServer}
                  className={`bg-second-primary-600 text-white px-4 py-2 rounded font-medium shadow-sm ${!selectedExampleMCPServer ? "opacity-50 cursor-not-allowed" : "hover:bg-second-primary-700 cursor-pointer"}`}
                  style={{
                    backgroundColor: !selectedExampleMCPServer
                      ? undefined
                      : "var(--second-primary-600)",
                  }}
                >
                  Add Example Server
                </button>
              </div>
              {availableExampleMCPServers.map((server) => (
                <div
                  key={server.url}
                  className="border border-primary-200 rounded p-4 bg-primary-50 dark:bg-neutral-800 space-y-2"
                >
                  <h4 className="text-lg font-semibold text-primary-900 dark:text-primary-100">
                    {server.name}
                  </h4>
                  <p className="text-sm text-primary-800 dark:text-primary-300">
                    {server.url}
                  </p>
                  <div className="text-sm text-primary-900 dark:text-primary-200 prose prose-sm max-w-none">
                    {server.description}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Custom MCP Server Section */}
          <div className={`space-y-4 ${availableExampleMCPServers && availableExampleMCPServers.length > 0 ? 'border-t border-primary-200 pt-6' : ''}`}>
            <h3 className="text-lg font-semibold text-primary-900 dark:text-primary-100">
              Add Custom MCP Server
            </h3>
            <p className="text-sm text-primary-800 dark:text-primary-300">
              Add a Model Context Protocol (MCP) server to provide additional tools and capabilities to the agent.
            </p>
            <div className="space-y-3">
              <input
                value={newMCPServer.url}
                onChange={(e) =>
                  setNewMCPServer({ ...newMCPServer, url: e.target.value })
                }
                placeholder="MCP Server URL (e.g., http://localhost:8001/mcp)"
                className="border border-primary-300 dark:border-primary-700 rounded p-2 w-full bg-primary-50 dark:bg-primary-950 text-primary-900 dark:text-primary-100"
              />
              <input
                value={newMCPServer.name}
                onChange={(e) =>
                  setNewMCPServer({ ...newMCPServer, name: e.target.value })
                }
                placeholder="Name (optional)"
                className="border border-primary-300 dark:border-primary-700 rounded p-2 w-full bg-primary-50 dark:bg-primary-950 text-primary-900 dark:text-primary-100"
              />
              <textarea
                value={newMCPServer.description}
                onChange={(e) =>
                  setNewMCPServer({ ...newMCPServer, description: e.target.value })
                }
                placeholder="Description (optional)"
                className="border border-primary-300 dark:border-primary-700 rounded p-2 w-full h-20 bg-primary-50 dark:bg-primary-950 text-primary-900 dark:text-primary-100"
              />
              <input
                type="password"
                value={newMCPServer.api_key || ""}
                onChange={(e) =>
                  setNewMCPServer({ ...newMCPServer, api_key: e.target.value })
                }
                placeholder="API Key (optional, for authentication)"
                className="border border-primary-300 dark:border-primary-700 rounded p-2 w-full bg-primary-50 dark:bg-primary-950 text-primary-900 dark:text-primary-100"
              />
              <p className="text-xs text-primary-700 dark:text-primary-400">
                If the MCP server requires authentication, provide an API key. It will be sent as a Bearer token.
              </p>

              {/* Custom Headers Section */}
              <div className="space-y-2">
                <h4 className="text-sm font-semibold text-primary-900 dark:text-primary-100">
                  Custom Headers (optional)
                </h4>
                <p className="text-xs text-primary-700 dark:text-primary-400">
                  Add custom HTTP headers for advanced authentication (e.g., X-API-Key, Authorization with custom scheme).
                </p>
                
                {/* Display existing headers */}
                {newMCPServer.headers && Object.keys(newMCPServer.headers).length > 0 && (
                  <div className="space-y-1 mb-2">
                    {Object.entries(newMCPServer.headers).map(([key, value]) => (
                      <div
                        key={key}
                        className="flex items-center justify-between bg-primary-100 dark:bg-primary-800 rounded px-3 py-2"
                      >
                        <div className="flex-1 font-mono text-sm text-primary-900 dark:text-primary-100">
                          <span className="font-semibold">{key}:</span> {value}
                        </div>
                        <button
                          onClick={() => handleRemoveHeader(key)}
                          className="ml-2 text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                          aria-label={`Remove header ${key}`}
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Add new header */}
                <div className="flex space-x-2">
                  <input
                    value={newHeaderKey}
                    onChange={(e) => setNewHeaderKey(e.target.value)}
                    placeholder="Header name (e.g., X-API-Key)"
                    className="border border-primary-300 dark:border-primary-700 rounded p-2 flex-1 bg-primary-50 dark:bg-primary-950 text-primary-900 dark:text-primary-100"
                  />
                  <input
                    value={newHeaderValue}
                    onChange={(e) => setNewHeaderValue(e.target.value)}
                    placeholder="Header value"
                    className="border border-primary-300 dark:border-primary-700 rounded p-2 flex-1 bg-primary-50 dark:bg-primary-950 text-primary-900 dark:text-primary-100"
                  />
                  <button
                    onClick={handleAddHeader}
                    disabled={!newHeaderKey.trim() || !newHeaderValue.trim()}
                    className={`flex items-center space-x-1 px-3 py-2 rounded ${
                      !newHeaderKey.trim() || !newHeaderValue.trim()
                        ? "bg-primary-300 dark:bg-primary-700 text-primary-500 dark:text-primary-400 cursor-not-allowed"
                        : "bg-tertiary-600 hover:bg-tertiary-700 text-white cursor-pointer"
                    }`}
                    aria-label="Add header"
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <button
                onClick={handleAddCustomMCPServer}
                disabled={!newMCPServer.url.trim()}
                className={`bg-second-primary-600 text-white px-4 py-2 rounded font-medium shadow-sm ${!newMCPServer.url.trim() ? "opacity-50 cursor-not-allowed" : "hover:bg-second-primary-700 cursor-pointer"}`}
                style={{
                  backgroundColor: !newMCPServer.url.trim()
                    ? undefined
                    : "var(--second-primary-600)",
                }}
              >
                Add MCP Server
              </button>
            </div>
          </div>

          {/* MCP Server List */}
          <div className="space-y-3 border-t border-primary-200 pt-6">
            <h3 className="text-lg font-semibold text-primary-900 dark:text-primary-100">
              Configured MCP Servers
            </h3>
            {mcpServers && mcpServers.length > 0 ? (
              <ul className="space-y-3">
                {mcpServers.map((server, i) => (
                  <li
                    key={i}
                    className="flex justify-between items-center border border-primary-200 rounded p-4 bg-primary-50 dark:bg-neutral-800"
                  >
                    <label className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={server.enabled}
                        onChange={() => toggleMCPServer(server.url)}
                        className="form-checkbox h-4 w-4 text-tertiary-600"
                      />
                      <div className="flex flex-col">
                        <span className="text-primary-900 dark:text-primary-100 font-medium">
                          {server.name || "Unnamed Server"}
                        </span>
                        <span className="text-sm text-primary-700 dark:text-primary-300">
                          {server.url}
                        </span>
                        {server.description && (
                          <span className="text-xs text-primary-600 dark:text-primary-400 mt-1">
                            {server.description}
                          </span>
                        )}
                        {server.api_key && (
                          <span className="text-xs text-tertiary-600 dark:text-tertiary-400 mt-1">
                            🔑 API Key configured
                          </span>
                        )}
                        {server.headers && Object.keys(server.headers).length > 0 && (
                          <span className="text-xs text-tertiary-600 dark:text-tertiary-400 mt-1">
                            📋 {Object.keys(server.headers).length} custom header(s)
                          </span>
                        )}
                      </div>
                    </label>
                    <button
                      onClick={() => removeMCPServer(server.url)}
                      className="bg-red-500 hover:bg-red-600 text-white px-3 py-1 rounded text-sm font-medium"
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-primary-700 dark:text-primary-400 italic">
                No MCP servers configured. Add one above to extend the agent with additional tools.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
