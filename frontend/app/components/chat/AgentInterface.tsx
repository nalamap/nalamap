"use client";

import { useState, useRef, useEffect } from "react";
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
  
  // Refs for smart scrolling
  const agentActivityRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [scrollLocked, setScrollLocked] = useState(false);
  
  // Use hook for functions only
  const {
    queryNaLaMapAgentStream,
    cancelRequest,
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

  // Smart scrolling: Lock view on Agent Activity when streaming starts
  useEffect(() => {
    if (isStreaming && toolUpdates.length > 0 && agentActivityRef.current) {
      // Lock scroll on Agent Activity
      setScrollLocked(true);
      agentActivityRef.current.scrollIntoView({ 
        behavior: "smooth", 
        block: "start" 
      });
    } else if (!isStreaming && scrollLocked) {
      // Unlock after streaming completes (after a short delay)
      const timer = setTimeout(() => {
        setScrollLocked(false);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [isStreaming, toolUpdates.length, scrollLocked]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    
    // Use streaming version for better UX
    await queryNaLaMapAgentStream("chat");
  };

  const handleCancel = async (e: React.FormEvent) => {
    e.preventDefault();
    await cancelRequest();
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
      <div 
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto overflow-x-hidden min-h-0"
      >
        {/* Chat Messages */}
        <ChatMessages
          conversation={conversation}
          loading={loading}
          showToolMessages={showToolMessages}
          expandedToolMessage={expandedToolMessage}
          onToggleToolMessage={handleToggleToolMessage}
          disableAutoScroll={scrollLocked}
        />

        {/* Tool Progress Indicator - shows during streaming, BELOW user message */}
        {/* This is the "Agent Activity" section that we lock the view on */}
        {isStreaming && toolUpdates.length > 0 && (
          <div ref={agentActivityRef} className="scroll-mt-4">
            <ToolProgressIndicator toolUpdates={toolUpdates} />
          </div>
        )}

        {/* Streaming Message Preview - shows tokens as they arrive */}
        {/* Styled like a regular AI message for seamless transition */}
        {isStreaming && streamingMessage && (
          <div className="mb-3">
            <div className="flex justify-start">
              <div className="max-w-[80%] px-4 py-2 rounded-lg bg-neutral-50 rounded-tl-none border border-primary-200">
                <div className="text-sm break-words chat-markdown text-primary-900 streaming-message">
                  {streamingMessage}
                  <span className="inline-block w-2 h-4 ml-1 bg-second-primary-600 animate-pulse"></span>
                </div>
                <div className="text-xs text-primary-500 mt-1">
                  Agent
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Search Results - visible below, but view stays locked on Agent Activity */}
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
          onCancel={handleCancel}
          isStreaming={isStreaming}
          placeholder="Ask about maps, search for data, or request analysis..."
          disabled={loading}
        />
      </div>
    </div>
  );
}
