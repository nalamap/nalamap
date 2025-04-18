// hooks/useGeoweaver.ts
"use client";

import { useState } from "react";
import { kml } from "@tmcw/togeojson";
import { BBox } from "geojson";

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

      // Convert any raw_geo_data into a KML file blob URL
      const processed: GeoweaverMapData[] = data.results.map((item: GeoweaverMapData) => {
        if (!item.access_url && item.raw_geo_data) {
          // 1) Parse KML string to XML DOM (and add surrounding KML structure)
          const parser = new DOMParser();
          const fullKml = `<?xml version="1.0" encoding="UTF-8"?>
            <kml xmlns="http://www.opengis.net/kml/2.2">
              <Document>
                <Placemark>
                  ${item.raw_geo_data}
                </Placemark>
              </Document>
            </kml>`;

          const kmlDoc = parser.parseFromString(fullKml, 'application/xml');
          console.log(kmlDoc);
          // 2) Convert to GeoJSON
          const collection = kml(kmlDoc);
          // Add original bounds to GeoJSON
          // Parse WKT bounding_box string into numeric bbox array [minLon, minLat, maxLon, maxLat]
          let bboxArray: BBox | number[] | undefined;
          if (item.bounding_box && typeof item.bounding_box === 'string') {
            const wkt = item.bounding_box
              .replace('POLYGON((', '')
              .replace('))', '');
            const coords = wkt.split(',').map(pair => {
              const [lon, lat] = pair.trim().split(' ').map(Number);
              return { lon, lat };
            });
            const lons = coords.map(c => c.lon);
            const lats = coords.map(c => c.lat);
            bboxArray = [
              Math.min(...lons),
              Math.min(...lats),
              Math.max(...lons),
              Math.max(...lats)
            ];
          }
          // 4) Build a GeoJSON Feature wrapping the first feature (or entire collection)
          const feature = {
            type: 'Feature',
            geometry: collection.type === 'FeatureCollection' && collection.features.length
              ? collection.features[0].geometry
              : collection,
            properties: {
              resource_id: item.resource_id,
              name: item.name,
              description: item.description,
              score: item.score
            },
            bbox: bboxArray
          };
          // 5) Create a Blob URL for the GeoJSON
          const geojsonBlob = new Blob([JSON.stringify(feature)], { type: 'application/geo+json' });
          const geojsonUrl = URL.createObjectURL(geojsonBlob);

          const newLayer = {
            resource_id: item.resource_id,
            name: `${item.name}_${item.resource_id}.geojson`,            // set file-like name
            source_type: 'uploaded',
            access_url: geojsonUrl,
            visible: true,
          };
          // addLayer(newLayer);
          return {
            ...item, ...newLayer
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
