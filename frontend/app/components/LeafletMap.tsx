"use client";

import { MapContainer, LayersControl, TileLayer, WMSTileLayer, GeoJSON, useMap } from "react-leaflet";
import { useState, useEffect, useRef } from "react";
import "leaflet/dist/leaflet.css";
//import { LayerData } from "./MapLibreMap"; // Assuming the same type definition
import L from "leaflet";
import "leaflet-fullscreen/dist/leaflet.fullscreen.css";
import "leaflet-fullscreen";

import { useMapStore } from "../stores/mapStore";
import { useLayerStore } from "../stores/layerStore";
import { ZoomToSelected } from "./ZoomToLayer";

// Fix leaflet's default icon path issue
import "leaflet/dist/leaflet.css";
import { GeoDataObject } from "../models/geodatamodel";
import { StyleOptions } from "../models/geodatamodel";

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


function useZoomToLayer(layers: GeoDataObject[]) {
  const map = useMap();
  const zoomedLayers = useRef<Set<string | number>>(new Set());

  useEffect(() => {
    layers.forEach(async (layer) => {
      if (!layer.visible || zoomedLayers.current.has(layer.id)) return;

      if (layer.layer_type?.toUpperCase() === "WMS") {
        // Handle bounding box from layer store
        if (layer.bounding_box) {
          let bounds = null;
          
          // Handle WKT polygon format
          if (typeof layer.bounding_box === 'string' && layer.bounding_box.includes('POLYGON')) {
            const match = layer.bounding_box.match(/POLYGON\(\((.+?)\)\)/);
            if (match) {
              const coords = match[1]
                .split(",")
                .map(pair => pair.trim().split(" ").map(Number))
                .filter(([lng, lat]) => !isNaN(lng) && !isNaN(lat));
            
              if (coords.length > 0) {
                const lats = coords.map(([lng, lat]) => lat);
                const lngs = coords.map(([lng, lat]) => lng);
            
                const southWest = L.latLng(Math.min(...lats), Math.min(...lngs));
                const northEast = L.latLng(Math.max(...lats), Math.max(...lngs));
                bounds = L.latLngBounds(southWest, northEast);
              }
            }
          } 
          // Handle array format [minX, minY, maxX, maxY]
          else if (Array.isArray(layer.bounding_box) && layer.bounding_box.length >= 4) {
            const [minX, minY, maxX, maxY] = layer.bounding_box;
            bounds = L.latLngBounds(
              [minY, minX], // southwest
              [maxY, maxX]  // northeast
            );
          }
          
          if (bounds) {
            map.fitBounds(bounds);
            zoomedLayers.current.add(layer.id);
          }
        }
      }
    });
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


// GeoJSON layer component with dynamic styling
function LeafletGeoJSONLayer({ url, style }: { url: string; style?: StyleOptions }) {
  const [data, setData] = useState<any>(null);
  const map = useMap();
  // ref to GeoJSON layer for style updates
  const geojsonRef = useRef<L.GeoJSON | null>(null);
  // Keep a ref of the latest style options so event handlers always see updates
  const styleRef = useRef<StyleOptions | undefined>(style);

  useEffect(() => {
    fetch(url)
      .then((res) => res.json())
      .then((json) => setData(json))
      .catch((err) => console.error("Error fetching GeoJSON:", err));
  }, [url]);

  useEffect(() => { styleRef.current = style; }, [style]);

  // When style prop changes, update existing layer styles
  useEffect(() => {
    if (geojsonRef.current) {
      // Apply the new style to all features immediately
      geojsonRef.current.setStyle(styleCallback);
    }
  }, [style]);

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

    // Highlight on hover, then restore to stored initial style on mouseout
    layer.on({
      mouseover: (e) => {
        if ("setStyle" in e.target) {
          (e.target as L.Path).setStyle({
            weight: 3,
            color: "#666",
            fillOpacity: 0.7,
          });
        }
      },
      mouseout: (e) => {
        if ("setStyle" in e.target) {
          // Compute fresh style from latest styleRef
          const curr = styleRef.current || {};
          (e.target as L.Path).setStyle({
            color: curr.strokeColor || "#3388ff",
            weight: curr.weight || 2,
            opacity: curr.opacity || 1,
            dashArray: curr.dashArray,
            dashOffset: curr.dashOffset,
            fillColor: curr.fillColor ?? curr.strokeColor || "#3388ff",
            fillOpacity: curr.fillOpacity,
          });
        }
      },
    });
  };

  // handle ref assignment from GeoJSON component
  const handleGeoJsonRef = (layer: L.GeoJSON) => {
    if (!layer) return;
    geojsonRef.current = layer;
    map.fitBounds(layer.getBounds());
  };

  // pointToLayer: always use circle markers with defaults
  const pointToLayer = (feature: any, latlng: L.LatLng) => {
    const curr = styleRef.current;
    const opts: L.CircleMarkerOptions = {
      radius: curr?.radius ?? 8,
      color: curr?.strokeColor || "#3388ff",
      weight: curr?.weight || 2,
      opacity: curr?.opacity || 1,
      dashArray: curr?.dashArray,
      dashOffset: curr?.dashOffset,
      fillColor: curr?.fillColor ?? curr?.strokeColor || "#3388ff",
      fillOpacity: curr?.fillOpacity,
    };
    return L.circleMarker(latlng, opts);
  };

  // style callback for GeoJSON and manual restoration
  const styleCallback = () => ({
    color: styleRef.current?.strokeColor || "#3388ff",
    weight: styleRef.current?.weight || 2,
    opacity: styleRef.current?.opacity || 1,
    dashArray: styleRef.current?.dashArray,
    dashOffset: styleRef.current?.dashOffset,
    // ensure fillColor matches strokeColor if not explicitly set
    fillColor: styleRef.current?.fillColor ?? styleRef.current?.strokeColor || "#3388ff",
    fillOpacity: styleRef.current?.fillOpacity,
  });
  return data ? (
    <GeoJSON
      data={data}
      onEachFeature={onEachFeature}
      pointToLayer={pointToLayer}
      ref={handleGeoJsonRef}
      style={styleCallback}
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

  const layerOrderKey = layers.map(l => l.id).join("-");

  // Get the first WMS layer from the layers array (if any) for GetFeatureInfo.
  const wmsLayerData = layers.find(
    (layer) => layer.layer_type?.toUpperCase() === "WMS"
  );
  const wmsLayer = wmsLayerData ? parseWMSUrl(wmsLayerData.data_link) : null;
  return (
    <div className="relative w-full h-full">
      <div className="absolute inset-0 z-0">
        <MapContainer center={[0, 0]} zoom={2} style={{ height: "100%", width: "100%" }} fullscreenControl={true}>
          {/* Add the fullscreen control */}
          <FullscreenControl />
          <ZoomToSelected />
          <TileLayer 
            url={basemap.url} 
            attribution={basemap.attribution}
          />
          <div key={layerOrderKey}>
            {[...layers].map((layer) => {
              if (!layer.visible) return null;

              if (layer.layer_type?.toUpperCase() === "WMS") {
                // 💡 Automatically zoom to bounding boxes
                const { baseUrl, layers: wmsLayers, format, transparent } = parseWMSUrl(layer.data_link);
                return (
                  <WMSTileLayer
                    key={layer.id}
                    url={baseUrl}
                    layers={wmsLayers}
                    format={format}
                    transparent={transparent}
                    zIndex={10}
                  />
                );
              } else if (
                layer.layer_type?.toUpperCase() === "WFS" || layer.layer_type?.toUpperCase() === "UPLOADED" ||
                layer.data_link.toLowerCase().includes("json")
              ) {
                return (
                  <LeafletGeoJSONLayer
                    key={layer.id}
                    url={layer.data_link}
                    style={layer.style}
                  />
                );
              }
              return null;
            })}
          </div>
          {/* Render legend if a WMS layer exists */}
          {wmsLayer && wmsLayerData && (
            <Legend wmsLayer={wmsLayer} title={wmsLayerData.title || wmsLayerData.name} />
          )}
        </MapContainer>
      </div>
    </div>
  );
}
