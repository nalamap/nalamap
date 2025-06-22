// hooks/useGeoweaver.ts
"use client";

import { useState } from "react";
import { ChatMessage, GeoDataObject, GeoweaverRequest, GeoweaverResponse } from "../models/geodatamodel";
import { useSettingsStore } from '../stores/settingsStore'
import { useLayerStore } from '../stores/layerStore'
import { useChatInterfaceStore } from "../stores/chatInterfaceStore";

export function useGeoweaverAgent(apiUrl: string) {
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


  async function queryGeoweaverAgent(
    endpoint: "chat" | "search" | "geocode" | "geoprocess",
    layerUrls: string[] = [],
    options?: { portal?: string; bboxWkt?: string }
  ) {
    const params = new URLSearchParams({ query: chatInterfaceStore.input, endpoint }); // unused at the moment? -> Move to Settingsstore
    chatInterfaceStore.setLoading(true);
    chatInterfaceStore.setError("");

    const rawSettings = useSettingsStore.getState();
    const settingsMap = new Map<string, Set<any>>(
      Object.entries(rawSettings)
        // drop methods and any non-arrays
        .filter(([, value]) => Array.isArray(value))
        // for each key, convert its array into a Set
        .map(([key, value]) => [key, new Set(value as any[])] as const)
    )

    const settingsObj: Record<string, unknown[]> = Object.fromEntries(
      Array.from(settingsMap.entries()).map(([key, set]) => [
        key,
        Array.from(set),        // turn Set → Array
      ])
    );

    console.log(settingsObj)

    try {
      let response = null;
      let fullQuery = chatInterfaceStore.input
      if (endpoint === "geoprocess" || endpoint === "chat" || endpoint === "geocode" || endpoint === "search") {
        const selectedLayers = useLayerStore.getState().layers.filter((l) => l.selected);
        appendHumanMessage(chatInterfaceStore.input);
        const payload: GeoweaverRequest = {
          messages: chatInterfaceStore.messages,
          query: chatInterfaceStore.input,
          geodata_last_results: chatInterfaceStore.geoDataList,
          geodata_layers: layerStore.layers,
          // global_geodata: layerStore.globalGeodata,
          options: settingsObj
        }
        chatInterfaceStore.setInput("");
        console.log(payload)
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
      const data: GeoweaverResponse = await response.json();
      console.log(data)
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
      //if (data.global_geodata)
      //  layerStore.synchronizeGlobalGeodataFromBackend(data.global_geodata);
    } catch (e: any) {
      chatInterfaceStore.setError(e.message || "Something went wrong");
    } finally {
      chatInterfaceStore.setLoading(false);
    }
  }

  return { input: chatInterfaceStore.input, setInput: chatInterfaceStore.setInput, messages: chatInterfaceStore.messages, geoDataList: chatInterfaceStore.geoDataList, loading: chatInterfaceStore.loading, error: chatInterfaceStore.error, queryGeoweaverAgent };

}
