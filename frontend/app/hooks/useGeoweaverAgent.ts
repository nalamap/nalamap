// hooks/useGeoweaver.ts
"use client";

import { useState } from "react";
import { ChatMessage, GeoDataObject, GeoweaverRequest, GeoweaverResponse } from "../models/geodatamodel";

export function useGeoweaverAgent(apiUrl: string) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [geoDataList, setGeoDataList] = useState<GeoDataObject[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function queryGeoweaverAgent(
    endpoint: "chat" | "search" | "geocode" | "geoprocess",
    layerUrls: string[] = [],
    options?: { portal?: string; bboxWkt?: string }
  ) {
    const params = new URLSearchParams({ query: input, endpoint });
    setLoading(true);
    setError("");
    try {
      let response = null;
      if (endpoint === "search") {
        const url = new URL(`${apiUrl}/search`);
        url.searchParams.set("query", input);
        if (options?.portal) url.searchParams.set("portals", options.portal);
        response = await fetch(url.toString(), {
          method: "GET",
        });
      }
      else if (endpoint == "geocode") {
        response = await fetch(`${apiUrl}/${endpoint}?query=${encodeURIComponent(input)}`);
      } else if (endpoint === "geoprocess" || endpoint === "chat") {
        const payload: GeoweaverRequest = {
          messages: messages.map(m => ({
            content: m.content,
            type: m.type
          })),
          query: input,
          geodata: geoDataList
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
      if (!data.geodata) {
        throw new Error("Response was missing GeoData");
      }
      if (!data.messages) {
        throw new Error("Response was missing Messages");
      }

      setGeoDataList(data.geodata);
      setMessages(data.messages);
    } catch (e: any) {
      setError(e.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return { input, setInput, messages, geoDataList, loading, error, queryGeoweaverAgent };

}
