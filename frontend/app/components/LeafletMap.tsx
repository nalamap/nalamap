"use client";

import { MapContainer, LayersControl, TileLayer, WMSTileLayer, GeoJSON, useMap } from "react-leaflet";
import { useState, useEffect, useRef } from "react";
import "leaflet/dist/leaflet.css";
//import { LayerData } from "./MapLibreMap"; // Assuming the same type definition
import L from "leaflet";
import "leaflet-fullscreen/dist/leaflet.fullscreen.css";
import "leaflet-fullscreen";

import { useMapStore } from "../stores/mapStore"; // Adjust path accordingly
import { useLayerStore } from "../stores/layerStore";
import { ZoomToSelected } from "./ZoomToLayer"; // adjust path

// Fix leaflet's default icon path issue
import "leaflet/dist/leaflet.css";
import { GeoDataObject } from "../models/geodatamodel";

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

// Function to parse WMTS URLs and extract layer and service information for legend generation
function parseWMTSUrl(access_url: string) {
  try {
    const urlObj = new URL(access_url);
    const baseUrl = `${urlObj.origin}${urlObj.pathname}`;
    
    // Extract parameters from URL
    const params = urlObj.searchParams;
    
    // For WMTS, we need to extract the layer name
    // WMTS URLs typically have a LAYER parameter or the layer is in the path
    let layerName = params.get("layer") || params.get("LAYER");
    
    // If no layer parameter, try to extract from the path
    // WMTS URLs often follow patterns like: 
    // /geoserver/gwc/service/wmts/rest/{workspace}:{layer}/{style}/{tileMatrixSet}/{z}/{x}/{y}.{format}
    // /geoserver/{workspace}/wmts?layer={workspace}:{layer}&...
    if (!layerName) {
      const pathParts = urlObj.pathname.split('/');
      const restIndex = pathParts.indexOf('rest');
      if (restIndex !== -1 && restIndex + 1 < pathParts.length) {
        layerName = pathParts[restIndex + 1];
      } else {
        // Try to find workspace in path for other patterns
        const geoserverIndex = pathParts.indexOf('geoserver');
        if (geoserverIndex !== -1 && geoserverIndex + 1 < pathParts.length) {
          const workspaceName = pathParts[geoserverIndex + 1];
          if (workspaceName !== 'gwc' && workspaceName !== 'wmts') {
            // This might be a workspace-specific WMTS endpoint
            // Check if layer parameter exists in query
            const layerParam = params.get("layer") || params.get("LAYER");
            if (layerParam) {
              layerName = layerParam;
            }
          }
        }
      }
    }
    
    // Extract workspace and layer name if in format "workspace:layer"
    let workspace = "";
    let finalLayerName = layerName || "";
    if (layerName && layerName.includes(':')) {
      [workspace, finalLayerName] = layerName.split(':');
    }
    
    // Construct WMS endpoint for legend from WMTS URL
    // Assuming GeoServer structure: replace /gwc/service/wmts with /wms
    let wmsBaseUrl = baseUrl;
    if (baseUrl.includes('/gwc/service/wmts')) {
      wmsBaseUrl = baseUrl.replace('/gwc/service/wmts', '/wms');
    } else if (baseUrl.includes('/wmts')) {
      wmsBaseUrl = baseUrl.replace('/wmts', '/wms');
    } else if (workspace && baseUrl.includes(`/${workspace}/wmts`)) {
      // Handle workspace-specific WMTS endpoints
      wmsBaseUrl = baseUrl.replace(`/${workspace}/wmts`, `/${workspace}/wms`);
    }
    
    const result = {
      baseUrl: wmsBaseUrl,
      layerName: finalLayerName,
      workspace,
      fullLayerName: workspace ? `${workspace}:${finalLayerName}` : finalLayerName
    };
    
    console.log('WMTS URL parsing result:', {
      originalUrl: access_url,
      parsed: result
    });
    
    return result;
  } catch (err) {
    console.error("Error parsing WMTS URL:", err);
    return { baseUrl: access_url, layerName: "", workspace: "", fullLayerName: "" };
  }
}

function LeafletGeoJSONLayer({ url }: { url: string }) {
  const [data, setData] = useState<any>(null);
  const map = useMap();

  // Create a canvas renderer instance
  const canvasRenderer = L.canvas();

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
  wmtsLayer,
  title,
  standalone = false,
}: {
  wmsLayer?: { baseUrl: string; layers: string; format: string; transparent: boolean };
  wmtsLayer?: { baseUrl: string; layerName: string; workspace: string; fullLayerName: string };
  title?: string;
  standalone?: boolean;
}) {
  let legendUrl = "";
  
  if (wmsLayer) {
    // Original WMS legend URL
    legendUrl = `${wmsLayer.baseUrl}?service=WMS&request=GetLegendGraphic&layer=${wmsLayer.layers}&format=image/png`;
  } else if (wmtsLayer && wmtsLayer.fullLayerName) {
    // WMTS legend URL using WMS GetLegendGraphic with the layer name from WMTS
    legendUrl = `${wmtsLayer.baseUrl}?service=WMS&request=GetLegendGraphic&layer=${wmtsLayer.fullLayerName}&format=image/png`;
  }
  
  // Don't render if no valid legend URL
  if (!legendUrl) {
    return null;
  }
  
  const baseClasses = "bg-white p-2 rounded shadow";
  const positionClasses = standalone ? "absolute bottom-2 right-2 z-[9999]" : "";
  
  return (
    <div className={`${baseClasses} ${positionClasses}`.trim()}>
      {title && <h4 className="font-bold mb-2 text-sm">{title}</h4>}
      <img 
        src={legendUrl} 
        alt="Layer Legend" 
        className="max-h-32"
        onError={(e) => {
          // Hide the legend if the image fails to load
          (e.target as HTMLImageElement).style.display = 'none';
          console.warn('Legend image failed to load:', legendUrl);
        }}
      />
    </div>
  );
}

export default function LeafletMapComponent() {
  const basemap = useMapStore((state) => state.basemap);
  const layers = useLayerStore((state) => state.layers);

  const layerOrderKey = layers.map(l => l.id).join("-");

  // Get the first WMS layer from the layers array (if any) for GetFeatureInfo.
  const wmsLayerData = layers.find(
    (layer) => layer.layer_type?.toUpperCase() === "WMS" && layer.visible
  );
  const wmsLayer = wmsLayerData ? parseWMSUrl(wmsLayerData.data_link) : null;
  
  // Get all visible layers that can show legends (WMS and WMTS)
  const visibleLayersWithLegends = layers.filter(
    (layer) => layer.visible && (
      layer.layer_type?.toUpperCase() === "WMS" || 
      layer.layer_type?.toUpperCase() === "WMTS"
    )
  );
  
  return (
    <div className="relative w-full h-full">
      <div className="absolute inset-0 z-0">
        <MapContainer 
          center={[0, 0]} 
          zoom={2} 
          style={{ height: "100%", width: "100%" }} 
          fullscreenControl={true}
          preferCanvas={true}
        >
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
              } 
              else if (
                layer.layer_type?.toUpperCase() === "WMTS" 
              ) {
                return (
                  <TileLayer
                    key={layer.id}
                    url={layer.data_link}
                    attribution={layer.title}
                  />
                );
              }
              else if (
                layer.layer_type?.toUpperCase() === "WFS" || layer.layer_type?.toUpperCase() === "UPLOADED" ||
                layer.data_link.toLowerCase().includes("json")
              ) {
                return <LeafletGeoJSONLayer key={layer.id} url={layer.data_link} />;
              }
              return null;
            })}
          </div>
          {/* Render legends for all visible WMS and WMTS layers */}
          {visibleLayersWithLegends.length > 0 && (
            <div className="absolute bottom-2 right-2 z-[9999] space-y-2">
              {visibleLayersWithLegends.map((layer, index) => {
                if (layer.layer_type?.toUpperCase() === "WMS") {
                  const wmsLayerParsed = parseWMSUrl(layer.data_link);
                  return (
                    <Legend 
                      key={`wms-${layer.id}`}
                      wmsLayer={wmsLayerParsed} 
                      title={layer.title || layer.name} 
                    />
                  );
                } else if (layer.layer_type?.toUpperCase() === "WMTS") {
                  const wmtsLayerParsed = parseWMTSUrl(layer.data_link);
                  return (
                    <Legend 
                      key={`wmts-${layer.id}`}
                      wmtsLayer={wmtsLayerParsed} 
                      title={layer.title || layer.name} 
                    />
                  );
                }
                return null;
              })}
            </div>
          )}
        </MapContainer>
      </div>
    </div>
  );
}
