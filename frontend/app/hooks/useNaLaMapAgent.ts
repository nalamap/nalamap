// hooks/useNaLaMap.ts
"use client";

import {
  ChatMessage,
  GeoDataObject,
  NaLaMapRequest,
  NaLaMapResponse,
} from "../models/geodatamodel";
import { useLayerStore } from "../stores/layerStore";
import { useChatInterfaceStore } from "../stores/chatInterfaceStore";
import { useSettingsStore } from "../stores/settingsStore";
import Logger from "../utils/logger";

type Primitive = string | number | boolean | null | undefined;

/**
 * Recursively walk through any value and:
 * - Convert Maps → plain objects
 * - Convert Sets → arrays (deduped by identity)
 * - Deduplicate Arrays
 * - Recurse into plain Objects
 */
function dedupeDeep(value: any): any {
  // Handle Maps
  if (value instanceof Map) {
    const obj: Record<string, any> = {};
    for (const [k, v] of value.entries()) {
      obj[k] = dedupeDeep(v);
    }
    return obj;
  }

  // Handle Sets
  if (value instanceof Set) {
    return Array.from(value).map(dedupeDeep);
  }

  // Handle Arrays
  if (Array.isArray(value)) {
    // First, recurse into each element
    const inner = value.map(dedupeDeep);
    // Then dedupe by identity
    return Array.from(new Set(inner));
  }

  // Handle plain Objects
  if (value !== null && typeof value === "object") {
    const out: Record<string, any> = {};
    for (const [k, v] of Object.entries(value)) {
      out[k] = dedupeDeep(v);
    }
    return out;
  }

  // Primitives pass through
  return value as Primitive;
}

/**
 * Normalize a raw settings snapshot into JSON-serializable plain JS:
 * - Maps → Objects
 * - Sets/Arrays → deduped Arrays
 * - Objects → fully recursed
 */
function normalizeSettings(raw: Record<string, any>): Record<string, any> {
  const out: Record<string, any> = {};
  for (const [key, val] of Object.entries(raw)) {
    // only transform container types; primitives stay as-is
    if (
      val instanceof Map ||
      val instanceof Set ||
      Array.isArray(val) ||
      (val !== null && typeof val === "object")
    ) {
      out[key] = dedupeDeep(val);
    } else {
      out[key] = val;
    }
  }
  return out;
}

export function useNaLaMapAgent(apiUrl: string) {
  const layerStore = useLayerStore();
  const chatInterfaceStore = useChatInterfaceStore();

  const appendHumanMessage = (query: string) => {
    /* // Don't normalize for now to keep all arguments
    const normalized: ChatMessage[] = messages.map(m => ({
      content: m.content,
      type: m.type,
    }));*/

    const humanMsg: ChatMessage = {
      content: query,
      type: "human",
    };

    chatInterfaceStore.setMessages([...chatInterfaceStore.messages, humanMsg]);
  };

  async function queryNaLaMapAgent(
    endpoint: "chat" | "search" | "geocode" | "geoprocess" | "ai-style",
    layerUrls: string[] = [],
    options?: { portal?: string; bboxWkt?: string },
  ) {
    const params = new URLSearchParams({
      query: chatInterfaceStore.input,
      endpoint,
    }); // unused at the moment? -> Move to Settingsstore
    chatInterfaceStore.setLoading(true);
    chatInterfaceStore.setError("");

    await useSettingsStore.getState().initializeIfNeeded();
    const rawSettings = useSettingsStore.getState().getSettings();
    //Logger.log(rawSettings);
    const settingsMap = new Map<string, Set<any>>(
      Object.entries(rawSettings)
        // drop methods and any non-arrays
        .filter(([, value]) => Array.isArray(value))
        // for each key, convert its array into a Set
        .map(([key, value]) => [key, new Set(value as any[])] as const),
    );
    //Logger.log(settingsMap)
    const settingsObjOld: Record<string, unknown[]> = Object.fromEntries(
      Array.from(settingsMap.entries()).map(([key, set]) => [
        key,
        Array.from(set), // turn Set → Array
      ]),
    );
    const settingsObj = normalizeSettings(rawSettings);
    Logger.log("SettingsObject:");
    Logger.log(settingsObj);

    try {
      let response = null;
      let fullQuery = chatInterfaceStore.input;
      if (
        endpoint === "geoprocess" ||
        endpoint === "chat" ||
        endpoint === "geocode" ||
        endpoint === "search"
      ) {
        const selectedLayers = useLayerStore
          .getState()
          .layers.filter((l) => l.selected);
        appendHumanMessage(chatInterfaceStore.input);
        const payload: NaLaMapRequest = {
          messages: chatInterfaceStore.messages,
          query: chatInterfaceStore.input,
          geodata_last_results: chatInterfaceStore.geoDataList,
          geodata_layers: layerStore.layers,
          // global_geodata: layerStore.globalGeodata,
          options: settingsObj,
        };
        chatInterfaceStore.setInput("");
        Logger.log("payload");
        Logger.log(payload);
        response = await fetch(`${apiUrl}/${endpoint}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "include",
          body: JSON.stringify(payload),
        });
      } else if (endpoint === "ai-style") {
        // Handle AI styling endpoint
        appendHumanMessage(chatInterfaceStore.input);
        const payload = {
          query: chatInterfaceStore.input,
          messages: chatInterfaceStore.messages,
          geodata_layers: layerStore.layers,
          geodata_last_results: chatInterfaceStore.geoDataList,
        };
        chatInterfaceStore.setInput("");
        Logger.log("AI Style payload:", payload);
        response = await fetch(`${apiUrl}/${endpoint}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "include",
          body: JSON.stringify(payload),
        });
      } else {
        throw new Error("Unknown Tool");
      }
      if (!response.ok) {
        Logger.log(response);
        throw new Error("Network response was not ok");
      }

      if (endpoint === "ai-style") {
        // Handle AI styling response differently
        const data = await response.json();
        Logger.log("AI Style response:", data);
        Logger.log("Current layers before update:", layerStore.layers);

        // Update layers with styling changes
        if (data.updated_layers) {
          Logger.log("Updating layers with:", data.updated_layers);
          layerStore.updateLayersFromBackend(data.updated_layers);
          Logger.log("Current layers after update:", layerStore.layers);
        }

        // Add AI message to conversation
        if (data.response) {
          chatInterfaceStore.setMessages([
            ...chatInterfaceStore.messages,
            { type: "ai", content: data.response },
          ]);
        }

        // Don't update geoDataList for styling operations
        return;
      }

      const data: NaLaMapResponse = await response.json();
      Logger.log(data);
      if (!data.geodata_results) {
        throw new Error("Response was missing GeoData");
      }
      if (!data.messages) {
        throw new Error("Response was missing Messages");
      }

      chatInterfaceStore.setGeoDataList(data.geodata_results);
      chatInterfaceStore.setMessages(data.messages);
      if (data.geodata_layers)
        layerStore.synchronizeLayersFromBackend(data.geodata_layers);

      // Check if this was a styling operation by looking for style_map_layers in messages
      const isStyleOperation = data.messages.some(
        (msg) =>
          msg.type === "tool" &&
          msg.content?.includes("Successfully applied styling"),
      );

      if (data.geodata_layers) {
        if (isStyleOperation) {
          // For styling operations, use updateLayersFromBackend to preserve existing layers
          Logger.log(
            "Detected styling operation, using updateLayersFromBackend",
          );
          Logger.log("Styling data.geodata_layers:", data.geodata_layers);
          layerStore.updateLayersFromBackend(data.geodata_layers);
        } else {
          // For other operations, use synchronizeLayersFromBackend
          Logger.log("Regular operation, using synchronizeLayersFromBackend");
          layerStore.synchronizeLayersFromBackend(data.geodata_layers);
        }
      }
      //if (data.global_geodata)
      //  layerStore.synchronizeGlobalGeodataFromBackend(data.global_geodata);
    } catch (e: any) {
      chatInterfaceStore.setError(e.message || "Something went wrong");
    } finally {
      chatInterfaceStore.setLoading(false);
    }
  }

  /**
   * Streaming version of queryNaLaMapAgent using Server-Sent Events (SSE).
   * Provides real-time updates for tool execution and LLM token streaming.
   */
  async function queryNaLaMapAgentStream(
    endpoint: "chat" = "chat",
    options?: { portal?: string; bboxWkt?: string },
  ) {
    chatInterfaceStore.setLoading(true);
    chatInterfaceStore.setIsStreaming(true);
    chatInterfaceStore.setError("");
    chatInterfaceStore.clearStreamingMessage();
    chatInterfaceStore.clearToolUpdates();

    await useSettingsStore.getState().initializeIfNeeded();
    const rawSettings = useSettingsStore.getState().getSettings();
    const settingsObj = normalizeSettings(rawSettings);

    try {
      const selectedLayers = useLayerStore
        .getState()
        .layers.filter((l) => l.selected);
      appendHumanMessage(chatInterfaceStore.input);

      const payload: NaLaMapRequest = {
        messages: chatInterfaceStore.messages,
        query: chatInterfaceStore.input,
        geodata_last_results: chatInterfaceStore.geoDataList,
        geodata_layers: layerStore.layers,
        options: settingsObj,
      };

      chatInterfaceStore.setInput("");
      Logger.log("Streaming payload:", payload);

      const response = await fetch(`${apiUrl}/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        credentials: "include",
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      if (!response.body) {
        throw new Error("Response body is null");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          Logger.log("Stream complete");
          break;
        }

        // Decode chunk and add to buffer
        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE messages (event: ...\ndata: ...\n\n)
        const messages = buffer.split("\n\n");
        buffer = messages.pop() || ""; // Keep incomplete message in buffer

        for (const message of messages) {
          if (!message.trim()) continue;

          const lines = message.split("\n");
          let eventType = "";
          let eventData = "";

          for (const line of lines) {
            if (line.startsWith("event: ")) {
              eventType = line.substring(7).trim();
            } else if (line.startsWith("data: ")) {
              eventData = line.substring(6).trim();
            }
          }

          if (!eventType || !eventData) continue;

          try {
            const data = JSON.parse(eventData);

            switch (eventType) {
              case "tool_start":
                Logger.log(`Tool started: ${data.tool}`);
                chatInterfaceStore.addToolUpdate({
                  name: data.tool,
                  status: "running",
                });
                break;

              case "tool_end":
                Logger.log(`Tool completed: ${data.tool}`);
                chatInterfaceStore.updateToolStatus(data.tool, "complete");
                break;

              case "llm_token":
                // Append token to streaming message
                chatInterfaceStore.appendStreamingToken(data.token);
                break;

              case "result":
                Logger.log("Final result received:", data);
                Logger.log("Messages BEFORE setting:", chatInterfaceStore.getMessages());
                Logger.log("GeoData BEFORE setting:", chatInterfaceStore.getGeoDataList());

                // Convert serialized messages back to ChatMessage format
                const messages: ChatMessage[] = data.messages.map(
                  (msg: any) => ({
                    type: msg.type,
                    content: msg.content,
                  }),
                );

                Logger.log("Setting messages to:", messages);
                Logger.log("Setting geodata results to:", data.geodata_results);

                chatInterfaceStore.setGeoDataList(data.geodata_results);
                chatInterfaceStore.setMessages(messages);

                if (data.geodata_layers) {
                  layerStore.synchronizeLayersFromBackend(data.geodata_layers);
                }

                // Clear streaming UI state since we now have the final result
                chatInterfaceStore.clearStreamingMessage();
                chatInterfaceStore.clearToolUpdates();
                
                Logger.log("Messages AFTER setting:", chatInterfaceStore.getMessages());
                Logger.log("GeoData AFTER setting:", chatInterfaceStore.getGeoDataList());
                Logger.log("Loading state:", chatInterfaceStore.getLoading());
                Logger.log("IsStreaming state:", chatInterfaceStore.getIsStreaming());
                break;

              case "error":
                Logger.error("Streaming error:", data);
                chatInterfaceStore.setError(
                  data.message || "An error occurred during streaming",
                );
                break;

              case "done":
                Logger.log("Stream done:", data);
                break;

              default:
                Logger.warn("Unknown event type:", eventType);
            }
          } catch (parseError) {
            Logger.error("Failed to parse event data:", parseError);
          }
        }
      }
    } catch (e: any) {
      Logger.error("Streaming error:", e);
      chatInterfaceStore.setError(e.message || "Something went wrong");
    } finally {
      Logger.log("Stream finally block - setting loading and isStreaming to false");
      Logger.log("Messages before finally:", chatInterfaceStore.getMessages());
      Logger.log("GeoData before finally:", chatInterfaceStore.getGeoDataList());
      chatInterfaceStore.setLoading(false);
      chatInterfaceStore.setIsStreaming(false);
      Logger.log("Messages after finally:", chatInterfaceStore.getMessages());
      Logger.log("GeoData after finally:", chatInterfaceStore.getGeoDataList());
    }
  }

  return {
    // Only return functions, not state values
    // State should be accessed directly via useChatInterfaceStore selectors
    // for proper reactivity in components
    queryNaLaMapAgent,
    queryNaLaMapAgentStream, // Export new streaming function
    setInput: chatInterfaceStore.setInput,
  };
}
