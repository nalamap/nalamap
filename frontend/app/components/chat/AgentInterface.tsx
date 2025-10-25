"use client";

import { useState } from "react";
import wellknown from "wellknown";
import { useNaLaMapAgent } from "../../hooks/useNaLaMapAgent";
import { useLayerStore } from "../../stores/layerStore";
import { GeoDataObject } from "../../models/geodatamodel";
import { getApiBase } from "../../utils/apiBase";
import ChatMessages from "./ChatMessages";
import SearchResults from "./SearchResults";
import ChatInput from "./ChatInput";

export default function AgentInterface() {
  const API_BASE_URL = getApiBase();
  const [expandedToolMessage, setExpandedToolMessage] = useState<
    Record<number, boolean>
  >({});
  
  const {
    input,
    setInput,
    messages: conversation,
    geoDataList,
    loading,
    error,
    queryNaLaMapAgent,
  } = useNaLaMapAgent(API_BASE_URL);
  
  const addLayer = useLayerStore((s) => s.addLayer);
  const showToolMessages = false; // TODO: Move to settings

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    await queryNaLaMapAgent("chat");
  };

  const handleLayerSelect = (layer: GeoDataObject) => {
    useLayerStore.getState().addLayer(layer);
  };

  const handleToggleToolMessage = (idx: number) => {
    setExpandedToolMessage((prev) => ({
      ...prev,
      [idx]: !prev[idx],
    }));
  };

  return (
    <div className="h-full w-full bg-primary-50 p-4 flex flex-col overflow-hidden relative border-l border-primary-300">
      {/* Header */}
      <h2 className="text-xl font-bold mb-4 text-primary-900 text-center flex-shrink-0">
        Map Assistant
      </h2>

      {/* Scrollable content area */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden min-h-0">
        {/* Chat Messages */}
        <ChatMessages
          conversation={conversation}
          loading={loading}
          showToolMessages={showToolMessages}
          expandedToolMessage={expandedToolMessage}
          onToggleToolMessage={handleToggleToolMessage}
        />

        {/* Search Results */}
        <SearchResults
          results={geoDataList}
          loading={loading}
          onSelectLayer={handleLayerSelect}
        />
      </div>

      <hr className="my-4 flex-shrink-0" />

      {/* Chat Input */}
      <div className="flex-shrink-0">
        <ChatInput
          value={input}
          onChange={setInput}
          onSubmit={handleSubmit}
          placeholder="Ask about maps, search for data, or request analysis..."
          disabled={loading}
        />
      </div>
    </div>
  );
}
