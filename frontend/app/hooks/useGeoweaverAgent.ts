// hooks/useGeoweaver.ts
"use client";

import { useState } from "react";
import { kml } from "@tmcw/togeojson";

interface GeoweaverMapData {
  resource_id: string | null;
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
  const [geoweaverAgentResults, setGeoweaverAgentResults] = useState<GeoweaverMapData[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function queryGeoweaverAgent(endpoint: string = "search") {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiUrl}/${endpoint}?query=${encodeURIComponent(input)}`);
      if (!response.ok) {
        throw new Error("Network response was not ok");
      }
      // Expecting the response to be a JSON array of search objects.
      const data = await response.json();
      console.log(data);

      // Convert any raw_geo_data into a KML file blob URL
      const processed: GeoweaverMapData[] = data.results.map((item: GeoweaverMapData) => {
        if (!item.access_url && item.raw_geo_data) {
          // 1) Parse KML string to XML DOM
          const parser = new DOMParser();
          const kmlDoc = parser.parseFromString(item.raw_geo_data, 'application/xml');
          // 2) Convert to GeoJSON
          const geojson = kml(kmlDoc);

          // Create a Blob URL for the GeoJSON
          const geojsonBlob = new Blob([
            JSON.stringify(geojson)
          ], { type: 'application/geo+json' });
          const geojsonUrl = URL.createObjectURL(geojsonBlob);
          return {
            ...item,
            name: `${item.resource_id}.kml`,            // set file-like name
            source_type: 'uploaded',
            access_url: geojsonUrl,
            visible: true,
          };
        }
        // otherwise leave as-is
        return item;
      });

      setGeoweaverAgentResults(processed);
    } catch (err: any) {
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return { input, setInput, geoweaverAgentResults, loading, error, queryGeoweaverAgent };
}
