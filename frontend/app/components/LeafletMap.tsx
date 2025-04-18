"use client";

import { MapContainer, LayersControl, TileLayer, WMSTileLayer, GeoJSON, useMap } from "react-leaflet";
import { useState, useEffect, useRef } from "react";
import "leaflet/dist/leaflet.css";
//import { LayerData } from "./MapLibreMap"; // Assuming the same type definition
import L from "leaflet";
import "leaflet-fullscreen/dist/leaflet.fullscreen.css";
import "leaflet-fullscreen";

import { useMapStore } from "../stores/mapStore"; // Adjust path accordingly
import { useLayerStore, LayerData } from "../stores/layerStore";
import { ZoomToLayer } from "./ZoomToLayer"; // adjust path

// Fix leaflet's default icon path issue
import "leaflet/dist/leaflet.css";

const defaultIcon = new L.Icon({
  iconUrl: "/marker-icon.png", // Make sure this is in /public folder
  iconRetinaUrl: "/marker-icon-2x.png",
  shadowUrl: "/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  tooltipAnchor: [16, -28],
  shadowSize: [41, 41],
});

// Extend the global L object to include fullscreen functionality
declare global {
  interface FullscreenOptions {
    position?: L.ControlPosition;
    title?: {
      'false': string;
      'true': string;
    };
  }

  namespace L {
    namespace control {
      function fullscreen(options?: FullscreenOptions): Control;
    }

    interface Map {
      fullscreenControl?: Control;
    }
  }
}


function useZoomToLayer(layers: LayerData[]) {
  const map = useMap();
  const zoomedLayers = useRef<Set<string | number>>(new Set());

  useEffect(() => {
    layers.forEach(async (layer) => {
      if (!layer.visible || zoomedLayers.current.has(layer.resource_id)) return;

      if (layer.source_type.toUpperCase() === "WMS") {
        // Option 1: Use bounding box from layerStore
        if (layer.bounding_box) {
          const [minX, minY, maxX, maxY] = layer.bounding_box;
          const bounds = L.latLngBounds(
            [minY, minX], // southwest
            [maxY, maxX]  // northeast
          );
          map.fitBounds(bounds);
          zoomedLayers.current.add(layer.resource_id);
        }
      }
    }
    );
  }, [layers, map]);
}


// Helper: Parse a full WMS access_url into its base URL and WMS parameters.
function parseWMSUrl(access_url: string) {
  try {
    const urlObj = new URL(access_url);
    const baseUrl = `${urlObj.origin}${urlObj.pathname}`;
    const params = urlObj.searchParams;
    return {
      baseUrl,
      layers: params.get("layers") || "",
      format: params.get("format") || "image/png",
      transparent: params.get("transparent")
        ? params.get("transparent") === "true"
        : true,
    };
  } catch (err) {
    console.error("Error parsing WMS URL:", err);
    return { baseUrl: access_url, layers: "", format: "image/png", transparent: true };
  }
}


function LeafletGeoJSONLayer({ url }: { url: string }) {
  const [data, setData] = useState<any>(null);
  const map = useMap();

  useEffect(() => {
    fetch(url)
      .then((res) => res.json())
      .then((json) => setData(json))
      .catch((err) => console.error("Error fetching GeoJSON:", err));
  }, [url]);

  const onEachFeature = (feature: any, layer: L.Layer) => {
    const props = feature.properties;
    if (!props) return;

    const firstValue = Object.values(props)[0];
    const tooltip = layer.bindTooltip(`${firstValue}`, { sticky: true });

    // HTML popup content with minimal table styling
    const popupContent = `
      <div style="padding: 4px; font-family: sans-serif;">
        <table style="border-collapse: collapse; width: 100%;">
          <tbody>
            ${Object.entries(props)
        .map(
          ([key, value]) => `
                <tr>
                  <th style="text-align: left; padding: 4px; border-bottom: 1px solid #ccc;">${key}</th>
                  <td style="padding: 4px; border-bottom: 1px solid #ccc;">${value}</td>
                </tr>
              `
        )
        .join("")}
          </tbody>
        </table>
      </div>
    `;

    layer.bindPopup(popupContent);

    // Remove tooltip while popup is open
    layer.on("popupopen", () => {
      tooltip?.unbindTooltip();
    });

    // Restore tooltip after closing popup
    layer.on("popupclose", () => {
      tooltip?.bindTooltip(`${firstValue}`, { sticky: true });
    });

    // Highlight on hover, only for non-marker layers
    layer.on({
      mouseover: (e) => {
        if ("setStyle" in e.target) {
          e.target.setStyle({
            weight: 3,
            color: "#666",
            fillOpacity: 0.7,
          });
        }
      },
      mouseout: (e) => {
        if ("setStyle" in e.target && geojsonRef) {
          geojsonRef.resetStyle(e.target);
        }
      },
    });
  };

  let geojsonRef: L.GeoJSON | null = null;

  const handleGeoJsonRef = (layer: L.GeoJSON) => {
    if (!layer) return;
    geojsonRef = layer;
    map.fitBounds(layer.getBounds());
  };

  const pointToLayer = (feature: any, latlng: L.LatLng) => {
    return L.marker(latlng, { icon: defaultIcon });
  };

  return data ? (
    <GeoJSON
      data={data}
      onEachFeature={onEachFeature}
      pointToLayer={pointToLayer}
      ref={handleGeoJsonRef}
      style={() => ({
        color: "#3388ff",
        weight: 2,
        fillOpacity: 0.3,
      })}
    />
  ) : null;
}

// Component to add the fullscreen control to the map
function FullscreenControl() {
  const map = useMap();

  useEffect(() => {
    if (!map.fullscreenControl) {
      // Add fullscreen control below the zoom control
      const fullscreenControl = L.control.fullscreen({
        position: 'topleft',
        title: {
          'false': 'View Fullscreen',
          'true': 'Exit Fullscreen'
        }
      });

      map.addControl(fullscreenControl);

      // Store a reference to the control
      map.fullscreenControl = fullscreenControl;
    }

    return () => {
      if (map.fullscreenControl) {
        map.removeControl(map.fullscreenControl);
        map.fullscreenControl = undefined;
      }
    };
  }, [map]);

  return null;
}

// Custom component to handle GetFeatureInfo requests for WMS layers.
function GetFeatureInfo({ wmsLayer }: { wmsLayer: { baseUrl: string; layers: string; format: string; transparent: boolean; } }) {
  const map = useMap();

  useEffect(() => {
    const onClick = (e: L.LeafletMouseEvent) => {
      // Convert the clicked latlng to a container point.
      const point = map.latLngToContainerPoint(e.latlng);
      // Get map size.
      const size = map.getSize();

      // Build GetFeatureInfo request parameters.
      // This example uses WMS version 1.1.1. For version 1.3.0, the parameters (e.g. CRS vs SRS, x/y vs i/j) may differ.
      const params = {
        request: 'GetFeatureInfo',
        service: 'WMS',
        srs: 'EPSG:3857', // or use CRS for version 1.3.0
        version: '1.1.1',
        layers: wmsLayer.layers,
        query_layers: wmsLayer.layers,
        info_format: 'text/html', // or application/json
        x: Math.floor(point.x).toString(),
        y: Math.floor(point.y).toString(),
      };

      // Construct the full URL.
      const url = `${wmsLayer.baseUrl}?${new URLSearchParams(params).toString()}`;

      // Fetch the GetFeatureInfo data.
      fetch(url)
        .then((res) => res.text())
        .then((html) => {
          // Display the result in a popup.
          L.popup()
            .setLatLng(e.latlng)
            .setContent(html)
            .openOn(map);
        })
        .catch((err) => console.error("GetFeatureInfo error:", err));
    };

    map.on("click", onClick);
    return () => {
      map.off("click", onClick);
    };
  }, [map, wmsLayer]);

  return null;
}

// Legend component that displays a title above the legend image.
function Legend({
  wmsLayer,
  title,
}: {
  wmsLayer: { baseUrl: string; layers: string; format: string; transparent: boolean };
  title?: string;
}) {
  const legendUrl = `${wmsLayer.baseUrl}?service=WMS&request=GetLegendGraphic&layer=${wmsLayer.layers}&format=image/png`;
  return (
    <div className="absolute bottom-2 right-2 z-[9999] bg-white p-2 rounded shadow">
      {title && <h4 className="font-bold mb-2">{title}</h4>}
      <img src={legendUrl} alt="Layer Legend" className="max-h-32" />
    </div>
  );
}

export default function LeafletMapComponent() {
  const basemap = useMapStore((state) => state.basemap);
  const layers = useLayerStore((state) => state.layers);

  // Get the first WMS layer from the layers array (if any) for GetFeatureInfo.
  const wmsLayerData = layers.find(
    (layer) => layer.source_type.toUpperCase() === "WMS"
  );
  const wmsLayer = wmsLayerData ? parseWMSUrl(wmsLayerData.access_url) : null;
  return (
    <div className="relative w-full h-full">
      <div className="absolute inset-0 z-0">
        <MapContainer center={[0, 0]} zoom={2} style={{ height: "100%", width: "100%" }} fullscreenControl={true}>
          {/* Add the fullscreen control */}
          <FullscreenControl />
          {/* LayersControl renders a nice base layer switching control */}
          {/*
                <LayersControl position="topright">
                <LayersControl.BaseLayer checked name="CartoDB Positron">
                    <TileLayer url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" />
                </LayersControl.BaseLayer>
                <LayersControl.BaseLayer name="CartoDB Dark Matter">
                    <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
                </LayersControl.BaseLayer>
                <LayersControl.BaseLayer name="OpenStreetMap">
                    <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                </LayersControl.BaseLayer>
                <LayersControl.BaseLayer name="Google Satellite">
                    <TileLayer url="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}" />
                </LayersControl.BaseLayer>
                <LayersControl.BaseLayer name="Google Hybrid">
                    <TileLayer url="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}" />
                </LayersControl.BaseLayer>
                <LayersControl.BaseLayer name="Google Terrain">
                    <TileLayer url="https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}" />
                </LayersControl.BaseLayer>
                </LayersControl> */}
          <ZoomToLayer layers={layers} />
          <TileLayer url={basemap} />
          {layers.map((layer) => {
            if (!layer.visible) return null;

            if (layer.source_type.toUpperCase() === "WMS") {
              // 💡 Automatically zoom to bounding boxes
              const { baseUrl, layers: wmsLayers, format, transparent } = parseWMSUrl(layer.access_url);
              return (
                <WMSTileLayer
                  key={layer.resource_id}
                  url={baseUrl}
                  layers={wmsLayers}
                  format={format}
                  transparent={transparent}
                  zIndex={10}
                />
              );
            } else if (
              layer.source_type.toUpperCase() === "WFS" || layer.source_type.toUpperCase() === "UPLOADED" ||
              layer.access_url.toLowerCase().includes("json")
            ) {
              return <LeafletGeoJSONLayer key={layer.resource_id} url={layer.access_url} />;
            }
            return null;
          })}
          {/* Render legend if a WMS layer exists */}
          {wmsLayer && wmsLayerData && (
            <Legend wmsLayer={wmsLayer} title={wmsLayerData.title || wmsLayerData.name} />
          )}
        </MapContainer>
      </div>
    </div>
  );
}
