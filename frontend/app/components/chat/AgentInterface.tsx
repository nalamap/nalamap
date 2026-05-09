"use client";

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { useNaLaMapAgent } from "../../hooks/useNaLaMapAgent";
import { useLayerStore } from "../../stores/layerStore";
import { useChatInterfaceStore } from "../../stores/chatInterfaceStore";
import type { GeoDataObject } from "../../models/geodatamodel";
import { getApiBase } from "../../utils/apiBase";
import ChatMessages from "./ChatMessages";
import SearchResults from "./SearchResults";
import ChatInput from "./ChatInput";
import ToolProgressIndicator from "../ToolProgressIndicator";
import PlanDisplay from "../PlanDisplay";
import ReactMarkdown from "react-markdown";

export default function AgentInterface() {
  const API_BASE_URL = getApiBase();
  const [expandedToolMessage, setExpandedToolMessage] = useState<
    Record<number, boolean>
  >({});
  
  // Refs for smart scrolling
  const agentActivityRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const scrollEndRef = useRef<HTMLDivElement>(null);
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
  const executionPlan = useChatInterfaceStore((s) => s.executionPlan);
  
  const showToolMessages = false; // TODO: Move to settings

  // When a plan exists and streaming is done, separate the final AI result
  // message so it renders BELOW the plan instead of above it.
  const { mainConversation, resultMessage } = useMemo(() => {
    if (executionPlan && !isStreaming && conversation.length > 0) {
      const lastMsg = conversation[conversation.length - 1];
      if (
        lastMsg.type === "ai" &&
        !lastMsg.additional_kwargs?.tool_calls?.length
      ) {
        return {
          mainConversation: conversation.slice(0, -1),
          resultMessage: lastMsg,
        };
      }
    }
    return { mainConversation: conversation, resultMessage: null };
  }, [conversation, executionPlan, isStreaming]);

  // Scroll-to-bottom callback for ChatMessages and post-streaming
  const doScrollToBottom = useCallback(() => {
    scrollEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  // Smart scrolling: Lock view on Agent Activity when streaming starts
  useEffect(() => {
    if (isStreaming && (toolUpdates.length > 0 || executionPlan) && agentActivityRef.current) {
      // Lock scroll on Agent Activity / Plan
      setScrollLocked(true);
      agentActivityRef.current.scrollIntoView({ 
        behavior: "smooth", 
        block: "start" 
      });
    } else if (!isStreaming && scrollLocked) {
      // Unlock after streaming completes and scroll to final result
      const timer = setTimeout(() => {
        setScrollLocked(false);
        doScrollToBottom();
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [isStreaming, toolUpdates.length, executionPlan, scrollLocked, doScrollToBottom]);

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

  const handleReset = useCallback(() => {
    if (!window.confirm(
      "Reset the Map Assistant? This will clear all chat messages and remove all layers from the map."
    )) return;
    if (isStreaming) cancelRequest();
    const store = useChatInterfaceStore.getState();
    store.clearMessages();
    store.setGeoDataList([]);
    store.clearError();
    store.clearStreamingMessage();
    store.clearToolUpdates();
    store.setIsStreaming(false);
    store.setLoading(false);
    store.clearExecutionPlan();
    store.setInput("");
    useLayerStore.getState().resetLayers();
  }, [isStreaming, cancelRequest]);

  return (
    <div className="h-full w-full bg-primary-50 p-4 flex flex-col overflow-hidden relative border-l border-primary-300">
      {/* Header */}
      <div className="flex items-center mb-4 flex-shrink-0">
        <h2 className="flex-1 text-xl font-bold text-primary-900 text-center">
          Map Assistant
        </h2>
        <button
          onClick={handleReset}
          disabled={false}
          title="Reset — clear chat and all layers"
          className="ml-2 p-1.5 rounded text-primary-500 hover:text-red-600 hover:bg-red-50 transition-colors"
          aria-label="Reset application"
        >
          {/* Trash / reset icon */}
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
            <path fillRule="evenodd" d="M8.75 1A2.75 2.75 0 0 0 6 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 1 0 .23 1.482l.149-.022.841 10.518A2.75 2.75 0 0 0 7.596 19h4.807a2.75 2.75 0 0 0 2.742-2.53l.841-10.52.149.023a.75.75 0 0 0 .23-1.482A41.03 41.03 0 0 0 14 4.193V3.75A2.75 2.75 0 0 0 11.25 1h-2.5ZM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4ZM8.58 7.72a.75.75 0 0 0-1.5.06l.3 7.5a.75.75 0 1 0 1.5-.06l-.3-7.5Zm4.34.06a.75.75 0 1 0-1.5-.06l-.3 7.5a.75.75 0 1 0 1.5.06l.3-7.5Z" clipRule="evenodd" />
          </svg>
        </button>
      </div>

      {/* Scrollable content area */}
      <div 
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto overflow-x-hidden min-h-0"
      >
        {/* Chat Messages (excludes final AI result when plan exists) */}
        <ChatMessages
          conversation={mainConversation}
          loading={loading}
          showToolMessages={showToolMessages}
          expandedToolMessage={expandedToolMessage}
          onToggleToolMessage={handleToggleToolMessage}
          disableAutoScroll={scrollLocked}
          scrollToBottom={doScrollToBottom}
        />

        {/* Execution Plan - shows the agent's multi-step plan with integrated tool details */}
        {executionPlan && (
          <div ref={agentActivityRef} className="scroll-mt-4">
            <PlanDisplay plan={executionPlan} toolUpdates={toolUpdates} />
          </div>
        )}

        {/* Standalone Tool Progress - only when there is NO execution plan */}
        {isStreaming && toolUpdates.length > 0 && !executionPlan && (
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

        {/* Final AI result - rendered BELOW plan when plan execution completed */}
        {resultMessage && (
          <div className="mb-3">
            <div className="flex justify-start">
              <div className="max-w-[80%] px-4 py-2 rounded-lg bg-neutral-50 rounded-tl-none border border-primary-200">
                <div className="text-sm break-words chat-markdown text-primary-900">
                  <ReactMarkdown>
                    {typeof resultMessage.content === "string"
                      ? resultMessage.content
                      : String(resultMessage.content)}
                  </ReactMarkdown>
                </div>
                <div className="text-xs text-primary-500 mt-1">Agent</div>
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

        {/* Scroll target at very bottom of all content */}
        <div ref={scrollEndRef} />
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
