"use client";

import { useState } from "react";
import wellknown from "wellknown";
import { useNaLaMapAgent } from "../../hooks/useNaLaMapAgent";
import { useLayerStore } from "../../stores/layerStore";
import { useChatInterfaceStore } from "../../stores/chatInterfaceStore";
import { GeoDataObject } from "../../models/geodatamodel";
import { getApiBase } from "../../utils/apiBase";
import ChatMessages from "./ChatMessages";
import SearchResults from "./SearchResults";
import ChatInput from "./ChatInput";
import ToolProgressIndicator from "../ToolProgressIndicator";

export default function AgentInterface() {
  const API_BASE_URL = getApiBase();
  const [expandedToolMessage, setExpandedToolMessage] = useState<
    Record<number, boolean>
  >({});
  
  // Use hook for functions only
  const {
    queryNaLaMapAgent,
    queryNaLaMapAgentStream,
  } = useNaLaMapAgent(API_BASE_URL);

  // Subscribe to store values directly for reactivity
  const input = useChatInterfaceStore((s) => s.input);
  const setInput = useChatInterfaceStore((s) => s.setInput);
  const conversation = useChatInterfaceStore((s) => s.messages);
  const geoDataList = useChatInterfaceStore((s) => s.geoDataList);
  const loading = useChatInterfaceStore((s) => s.loading);
  const error = useChatInterfaceStore((s) => s.error);

  // Get streaming state from store
  const toolUpdates = useChatInterfaceStore((s) => s.toolUpdates);
  const streamingMessage = useChatInterfaceStore((s) => s.streamingMessage);
  const isStreaming = useChatInterfaceStore((s) => s.isStreaming);
  
  const addLayer = useLayerStore((s) => s.addLayer);
  const showToolMessages = false; // TODO: Move to settings

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    
    // Use streaming version for better UX
    await queryNaLaMapAgentStream("chat");
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

        {/* Tool Progress Indicator - shows during streaming, BELOW user message */}
        {isStreaming && toolUpdates.length > 0 && (
          <ToolProgressIndicator toolUpdates={toolUpdates} />
        )}

        {/* Streaming Message Preview - shows tokens as they arrive */}
        {isStreaming && streamingMessage && (
          <div className="mb-4 p-3 bg-primary-100 border border-primary-300 rounded-lg">
            <div className="text-xs text-primary-600 font-semibold mb-1 uppercase">
              AI Response (streaming...)
            </div>
            <div className="text-sm text-primary-900 streaming-message">
              {streamingMessage}
            </div>
          </div>
        )}

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
