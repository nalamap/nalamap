"use client";

import { useState, useEffect, useRef } from "react";
import dynamic from "next/dynamic";

import MapLibreMap  from "./MapLibreMap";

// Dynamically import the Leaflet component with SSR disabled.
const LeafletMapComponent = dynamic(
  () => import("./LeafletMap"),
  { ssr: false }
);

export interface LayerData {
  resource_id: number | string;
  source_type: string;
  name: string;
  title: string;
  description: string;
  access_url: string;
  format: string;
  llm_description: string;
  bounding_box: any; // You can further type this if you know its structure, e.g. number[] or a specific object type.
  score: number;
}


interface MapComponentProps {
  layers: LayerData[];
}

/* ------------------- Parent Component to Switch Map Frameworks ------------------- */
export default function MapSwitcher({ layers }: MapComponentProps) {
  // State to choose the map framework.
  const [framework, setFramework] = useState<"maplibre" | "leaflet">("leaflet");

  return (
    <div className="relative w-full h-full">
      <div className="absolute top-2 left-13 z-20">
        <button
          onClick={() =>
            setFramework((prev) => (prev === "maplibre" ? "leaflet" : "maplibre"))
          }
          className="bg-blue-500 text-white p-2 rounded shadow"
        >
          Switch to {framework === "maplibre" ? "Leaflet" : "MapLibre"}
        </button>
      </div>
      {framework === "maplibre" ? (
        <MapLibreMap layers={layers} />
      ) : (
        <LeafletMapComponent layers={layers} />
      )}
    </div>
  );
}
