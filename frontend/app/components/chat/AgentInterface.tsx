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
  const executionPlan = useChatInterfaceStore((s) => s.executionPlan);
  const streamingMessage = useChatInterfaceStore((s) => s.streamingMessage);
  const isStreaming = useChatInterfaceStore((s) => s.isStreaming);
  const includeSelectedLayersInPrompt = useChatInterfaceStore(
    (s) => s.includeSelectedLayersInPrompt,
  );
  const setIncludeSelectedLayersInPrompt = useChatInterfaceStore(
    (s) => s.setIncludeSelectedLayersInPrompt,
  );
  const layers = useLayerStore((s) => s.layers);
  const toggleLayerSelection = useLayerStore((s) => s.toggleLayerSelection);
  const setSelectedLayerIds = useLayerStore((s) => s.setSelectedLayerIds);
  const selectedLayerCount = useLayerStore(
    (s) => s.layers.filter((layer) => layer.selected).length,
  );
  
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
        <div className="mb-2 flex items-center justify-between text-xs text-primary-700">
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={includeSelectedLayersInPrompt}
              onChange={(e) =>
                setIncludeSelectedLayersInPrompt(e.target.checked)
              }
              className="h-4 w-4 rounded border-primary-300 text-secondary-600 focus:ring-secondary-300"
            />
            Include selected layers explicitly
          </label>
          <span>{selectedLayerCount} selected</span>
        </div>
        {includeSelectedLayersInPrompt && (
          <div className="mb-2 rounded border border-primary-200 bg-white p-2">
            <div className="mb-2 flex items-center justify-between text-xs text-primary-700">
              <span className="font-medium">Layers to include</span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedLayerIds(layers.map((layer) => layer.id))}
                  className="rounded border border-primary-200 px-2 py-0.5 hover:bg-primary-50"
                >
                  Select all
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedLayerIds([])}
                  className="rounded border border-primary-200 px-2 py-0.5 hover:bg-primary-50"
                >
                  Clear
                </button>
              </div>
            </div>
            {layers.length === 0 ? (
              <p className="text-xs text-primary-500">No layers available.</p>
            ) : (
              <div className="max-h-28 space-y-1 overflow-y-auto pr-1">
                {layers.map((layer) => (
                  <label
                    key={layer.id}
                    className="flex cursor-pointer items-center gap-2 text-xs text-primary-800"
                  >
                    <input
                      type="checkbox"
                      checked={Boolean(layer.selected)}
                      onChange={() => toggleLayerSelection(layer.id)}
                      className="h-4 w-4 rounded border-primary-300 text-secondary-600 focus:ring-secondary-300"
                    />
                    <span className="truncate">
                      {layer.title || layer.name || String(layer.id)}
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}
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
