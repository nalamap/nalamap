// hooks/useNaLaMap.ts
"use client";

import { useState } from "react";
import { ChatMessage, GeoDataObject, NaLaMapRequest, NaLaMapResponse } from "../models/geodatamodel";
import { useSettingsStore } from '../stores/settingsStore'
import { useLayerStore } from '../stores/layerStore'

export function useNaLaMapAgent(apiUrl: string) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [geoDataList, setGeoDataList] = useState<GeoDataObject[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const layerStore = useLayerStore();


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

    setMessages([...messages, humanMsg]);
  };


  async function queryNaLaMapAgent(
    endpoint: "chat" | "search" | "geocode" | "geoprocess" | "ai-style",
    layerUrls: string[] = [],
    options?: { portal?: string; bboxWkt?: string }
  ) {
    const params = new URLSearchParams({ query: input, endpoint }); // unused at the moment? -> Move to Settingsstore
    setLoading(true);
    setError("");

    const rawSettings = useSettingsStore.getState();
    const settingsMap = new Map<string, Set<any>>(
      Object.entries(rawSettings)
        // drop methods and any non-arrays
        .filter(([, value]) => Array.isArray(value))
        // for each key, convert its array into a Set
        .map(([key, value]) => [key, new Set(value as any[])] as const)
    )
    console.log(settingsMap)

    try {
      let response = null;
      let fullQuery = input
      if (endpoint === "geoprocess" || endpoint === "chat" || endpoint === "geocode" || endpoint === "search") {
        const selectedLayers = useLayerStore.getState().layers.filter((l) => l.selected);
        appendHumanMessage(input);
        const payload: NaLaMapRequest = {
          messages: messages,
          query: input,
          geodata_last_results: geoDataList,
          geodata_layers: layerStore.layers,
          // global_geodata: layerStore.globalGeodata,
          options: settingsMap
        }
        setInput("");
        console.log(payload)
        response = await fetch(`${apiUrl}/${endpoint}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
        });
      } else if (endpoint === "ai-style") {
        // Handle AI styling endpoint
        appendHumanMessage(input);
        const payload = {
          query: input,
          messages: messages,
          geodata_layers: layerStore.layers,
          geodata_last_results: geoDataList,
        }
        setInput("");
        console.log("AI Style payload:", payload);
        response = await fetch(`${apiUrl}/${endpoint}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
        });
      } else {
        throw new Error("Unknown Tool");
      }
      if (!response.ok) {
        console.log(response)
        throw new Error("Network response was not ok");
      }
      
      if (endpoint === "ai-style") {
        // Handle AI styling response differently
        const data = await response.json();
        console.log("AI Style response:", data);
        console.log("Current layers before update:", layerStore.layers);
        
        // Update layers with styling changes
        if (data.updated_layers) {
          console.log("Updating layers with:", data.updated_layers);
          layerStore.updateLayersFromBackend(data.updated_layers);
          console.log("Current layers after update:", layerStore.layers);
        }
        
        // Add AI message to conversation
        if (data.response) {
          setMessages([...messages, { type: "ai", content: data.response }]);
        }
        
        // Don't update geoDataList for styling operations
        return;
      }
      
      const data: NaLaMapResponse = await response.json();
      console.log(data)
      if (!data.geodata_results) {
        throw new Error("Response was missing GeoData");
      }
      if (!data.messages) {
        throw new Error("Response was missing Messages");
      }

      setGeoDataList(data.geodata_results);
      setMessages(data.messages);
      
      // Check if this was a styling operation by looking for style_map_layers in messages
      const isStyleOperation = data.messages.some(msg => 
        msg.type === "tool" && msg.content?.includes("Successfully applied styling")
      );
      
      if (data.geodata_layers) {
        if (isStyleOperation) {
          // For styling operations, use updateLayersFromBackend to preserve existing layers
          console.log("Detected styling operation, using updateLayersFromBackend");
          console.log("Styling data.geodata_layers:", data.geodata_layers);
          layerStore.updateLayersFromBackend(data.geodata_layers);
        } else {
          // For other operations, use synchronizeLayersFromBackend
          console.log("Regular operation, using synchronizeLayersFromBackend");
          layerStore.synchronizeLayersFromBackend(data.geodata_layers);
        }
      }
      //if (data.global_geodata)
      //  layerStore.synchronizeGlobalGeodataFromBackend(data.global_geodata);
    } catch (e: any) {
      setError(e.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return { input, setInput, messages, geoDataList, loading, error, queryNaLaMapAgent };

}
