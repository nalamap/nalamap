"use client";

import { useRef, useEffect, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

// Define the interface for each layer's data.
interface LayerData {
  id: number | string;
  access_url: string;
  bounding_box: any; // You can type this more strictly if you know the structure (e.g. number[])
  llm_description: string;
  score: number;
  source_type: string;
}

// Define the component props.
interface MapLibreMapProps {
  layers: LayerData[];
}

export default function MapLibreMap({ layers }: MapLibreMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  // State to manage the current basemap style.
  const [basemapStyle, setBasemapStyle] = useState<string>(
    "https://demotiles.maplibre.org/style.json"
  );

  // Helper function to add custom layers.
  const addCustomLayers = () => {
    if (mapRef.current && layers.length > 0) {
      layers.forEach((layer) => {
        // Determine if this layer should be added as a GeoJSON layer.
        if (
          layer.source_type.toUpperCase() === "WFS" ||
          layer.access_url.toLowerCase().includes("json")
        ) {
          // Use the layer id as a string for the source.
          const sourceId = layer.id.toString();
          // Only add the source if it doesn't already exist.
          if(mapRef.current) {
            if (!mapRef.current.getSource(sourceId)) {
                mapRef.current.addSource(sourceId, {
                type: "geojson",
                data: layer.access_url, // Assumes this URL returns valid GeoJSON.
                });
                mapRef.current.addLayer({
                id: sourceId,
                type: "fill", // You can change the layer type if needed.
                source: sourceId,
                layout: {},
                paint: {
                    "fill-color": "#888888",
                    "fill-opacity": 0.4,
                },
                });
            }
          }
            } else {
            // For layers that do not meet the GeoJSON criteria, you could implement alternative handling.
            console.log(`Layer ${layer.id} does not qualify as a GeoJSON layer.`);
            }
      });
    }
  };

  // Initialize the map on mount.
  useEffect(() => {
    if (mapContainer.current && !mapRef.current) {
      mapRef.current = new maplibregl.Map({
        container: mapContainer.current,
        style: basemapStyle,
        center: [0, 0],
        zoom: 2,
      });
      // After the map style loads, add custom layers.
      mapRef.current.on("style.load", () => {
        addCustomLayers();
      });
    }
  }, []);

  // When the basemap style changes, update the map and re-add custom layers.
  useEffect(() => {
    if (mapRef.current) {
      mapRef.current.setStyle(basemapStyle);
      mapRef.current.on("style.load", () => {
        addCustomLayers();
      });
    }
  }, [basemapStyle]);

  // When the layers prop changes, add or update custom layers.
  useEffect(() => {
    addCustomLayers();
  }, [layers]);

  // Toggle between two basemap styles.
  const toggleBasemap = () => {
    const style1 = "https://demotiles.maplibre.org/style.json";
    const style2 = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";
    setBasemapStyle((prev) => (prev === style1 ? style2 : style1));
  };

  return (
    <div className="relative w-full h-full">
      {/* The map container */}
      <div ref={mapContainer} className="w-full h-full" />
      {/* Basemap switch button at the top left corner */}
      <button
        onClick={toggleBasemap}
        className="absolute top-2 left-2 z-10 bg-white p-2 rounded shadow"
      >
        Switch Basemap
      </button>
    </div>
  );
}
