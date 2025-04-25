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
    layerUrls: string[] = []
  ) {
    setLoading(true);
    setError("");
    try {
      let response = null;
      if (endpoint === "search" || endpoint == "geocode") {
        response = await fetch(`${apiUrl}/${endpoint}?query=${encodeURIComponent(input)}`);
      } else if (endpoint === "geoprocess") {
        // POST a JSON body for geoprocess // TODO: Use standard geodata model
        response = await fetch(`${apiUrl}/geoprocess`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: input,
            layer_urls: layerUrls,
          }),
        });
      } else {
        const payload: GeoweaverRequest = {
          messages,
          query: input,
          geodata: geoDataList
        }
        response = await fetch(`${apiUrl}/${endpoint}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
        });
      }
      if (!response.ok) {
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

      // Convert any raw_geo_data into a KML file blob URL
      /*
      const processed: GeoDataObject[] = data.results.map((item: GeoDataObject) => {
      
        if (!item.data_link && item.raw_geo_data) {
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
              id: item.id,
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
            id: item.id,
            name: `${item.name}_${item.id}.geojson`,            // set file-like name
            data_origin: 'uploaded',
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
      setGeoDataList(processed);
      */
    } catch (e: any) {
      setError(e.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return { input, setInput, messages, geoDataList, loading, error, queryGeoweaverAgent };

}
