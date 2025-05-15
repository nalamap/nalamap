// hooks/useGeoweaver.ts
"use client";

import { useState } from "react";
import { ChatMessage, GeoDataObject, GeoweaverRequest, GeoweaverResponse } from "../models/geodatamodel";
import { useSettingsStore } from '../stores/settingsStore'
import { useLayerStore } from '../stores/layerStore'

export function useGeoweaverAgent(apiUrl: string) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [geoDataList, setGeoDataList] = useState<GeoDataObject[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const layerStore = useLayerStore();

  async function queryGeoweaverAgent(
    endpoint: "chat" | "search" | "geocode" | "geoprocess",
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
      /*
      if (endpoint === "search") {
        const url = new URL(`${apiUrl}/search`);
        url.searchParams.set("query", input);
        if (options?.portal) url.searchParams.set("portals", options.portal);
        response = await fetch(url.toString(), {
          method: "GET",
        });
      }
      else if (endpoint === "geocode") {
        response = await fetch(`${apiUrl}/${endpoint}?query=${encodeURIComponent(input)}`);
      } else */
      if (endpoint === "geoprocess" || endpoint === "chat" || endpoint === "geocode" || endpoint === "search") {
        const payload: GeoweaverRequest = {
          messages: messages.map(m => ({
            content: m.content,
            type: m.type
          })),
          query: input,
          geodata_last_results: geoDataList,
          geodata_layers: layerStore.layers,
          global_geodata: geoDataList,
          options: settingsMap
        }
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

      setGeoDataList(data.geodata_results);
      setMessages(data.messages);
      // TODO: Sync Layers & global geodata
    } catch (e: any) {
      setError(e.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return { input, setInput, messages, geoDataList, loading, error, queryGeoweaverAgent };

}
