// hooks/useGeoweaver.ts
"use client";

import { useState } from "react";

interface GeoweaverMapData {
  resource_id: string;
  source_type: string | null;
  name: string | null;
  title?: string | null;
  description?: string | null;
  access_url: string | null;
  format?: string | null;
  llm_description?: string;
  bounding_box?: string | null;
  raw_geo_data?: string | null;
  score?: number | null;
  visible?: boolean | null;
}

export function useGeoweaverAgent(apiUrl: string) {
  const [input, setInput] = useState("");
  const [results, setResults] = useState<GeoweaverMapData[]>([]);
  const [processedUrls, setProcessedUrls] = useState<string[]>([]);
  const [toolsUsed, setToolsUsed] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function query(
    endpoint: "search" | "geocode" | "geoprocess",
    layerUrls: string[] = []
  ) {
    setLoading(true);
    setError("");
    try {
      let res: Response;
      if (endpoint === "geoprocess") {
        // POST a JSON body for geoprocess
        res = await fetch(`${apiUrl}/geoprocess`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: input,
            layer_urls: layerUrls,
          }),
        });
      } else {
        // GET for search / geocode
        res = await fetch(
          `${apiUrl}/${endpoint}?query=${encodeURIComponent(input)}`
        );
      }

      if (!res.ok) throw new Error(await res.text());

      const data = await res.json();
      if (endpoint === "search" || endpoint === "geocode") {
        // we expect { results: GeoweaverMapData[] }
        setResults(data.results);
      } else {
        // geoprocess => { layer_urls: string[], tools_used: string[] }
        setProcessedUrls(data.layer_urls);
        setToolsUsed(data.tools_used || []);
      }
    } catch (e: any) {
      setError(e.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return {
    input,
    setInput,
    results,
    processedUrls,
    toolsUsed,
    loading,
    error,
    query,
  };
}
