"use client";

import { MapContainer, LayersControl, TileLayer, WMSTileLayer, GeoJSON, useMap } from "react-leaflet";
import { useState, useEffect, useRef, useMemo } from "react";
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

// Function to parse WMTS URLs and extract layer information for legend generation
function parseWMTSUrl(access_url: string) {
  try {
    const urlObj = new URL(access_url);
    const baseUrl = `${urlObj.origin}${urlObj.pathname}`;
    
    // Extract all parameters from the original WMTS URL
    const originalParams = urlObj.searchParams;
    
    // Get layer name from parameters
    let layerName = originalParams.get("layer") || originalParams.get("LAYER");
    
    // If no layer parameter, try to extract from REST-style path
    if (!layerName) {
      const pathParts = urlObj.pathname.split('/');
      const restIndex = pathParts.indexOf('rest');
      if (restIndex !== -1 && restIndex + 1 < pathParts.length) {
        layerName = pathParts[restIndex + 1];
      }
    }
    
    if (!layerName) {
      console.warn('Could not extract layer name from WMTS URL:', access_url);
      return { 
        wmtsLegendUrl: "", 
        wmsLegendUrl: "", 
        layerName: "", 
        originalUrl: access_url 
      };
    }
    
    // Extract workspace and final layer name if in format "workspace:layer"
    let workspace = "";
    let finalLayerName = layerName;
    if (layerName.includes(':')) {
      [workspace, finalLayerName] = layerName.split(':');
    }
    
    // Method 1: Try WMTS GetLegendGraphic (for providers like FAO that support this non-standard extension)
    const wmtsLegendParams = new URLSearchParams();
    
    // Set basic WMTS GetLegendGraphic parameters
    wmtsLegendParams.set('service', 'WMTS');
    wmtsLegendParams.set('version', '1.1.0'); // Use 1.1.0 as in FAO examples
    wmtsLegendParams.set('request', 'GetLegendGraphic');
    wmtsLegendParams.set('format', 'image/png'); // Let URLSearchParams handle the encoding
    wmtsLegendParams.set('transparent', 'True');
    wmtsLegendParams.set('layer', layerName); // Let URLSearchParams handle the encoding
    
    // Preserve dimension parameters and other custom parameters from original request
    originalParams.forEach((value, key) => {
      const lowerKey = key.toLowerCase();
      // Keep dimension parameters (dim_*) and other relevant parameters
      if (lowerKey.startsWith('dim_') || 
          lowerKey === 'time' || 
          lowerKey === 'elevation' ||
          lowerKey === 'style') {
        wmtsLegendParams.set(key, value);
      }
    });
    
    const wmtsLegendUrl = `${baseUrl}?${wmtsLegendParams.toString()}`;
    
    // Method 2: Fallback WMS GetLegendGraphic (standard approach for GeoServer)
    let wmsBaseUrl = baseUrl;
    
    // Convert WMTS endpoint to WMS endpoint
    if (baseUrl.includes('/gwc/service/wmts')) {
      wmsBaseUrl = baseUrl.replace('/gwc/service/wmts', '/wms');
    } else if (baseUrl.includes('/wmts')) {
      wmsBaseUrl = baseUrl.replace('/wmts', '/wms');
    } else if (workspace && baseUrl.includes(`/${workspace}/wmts`)) {
      wmsBaseUrl = baseUrl.replace(`/${workspace}/wmts`, `/${workspace}/wms`);
    }
    
    const wmsLegendParams = new URLSearchParams();
    wmsLegendParams.set('service', 'WMS');
    wmsLegendParams.set('version', '1.1.0');
    wmsLegendParams.set('request', 'GetLegendGraphic');
    wmsLegendParams.set('format', 'image/png');
    wmsLegendParams.set('layer', layerName); // Don't URL encode for WMS
    
    // Preserve dimension parameters for WMS as well
    originalParams.forEach((value, key) => {
      const lowerKey = key.toLowerCase();
      if (lowerKey.startsWith('dim_') || 
          lowerKey === 'time' || 
          lowerKey === 'elevation') {
        wmsLegendParams.set(key, value);
      }
    });
    
    const wmsLegendUrl = `${wmsBaseUrl}?${wmsLegendParams.toString()}`;
    
    const result = {
      wmtsLegendUrl,
      wmsLegendUrl,
      layerName: finalLayerName,
      workspace,
      fullLayerName: workspace ? `${workspace}:${finalLayerName}` : finalLayerName,
      originalUrl: access_url
    };
    
    console.log('WMTS URL parsing result:', {
      originalUrl: access_url,
      parsed: result
    });
    
    return result;
  } catch (err) {
    console.error("Error parsing WMTS URL:", err);
    return { 
      wmtsLegendUrl: "", 
      wmsLegendUrl: "", 
      layerName: "", 
      originalUrl: access_url 
    };
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
  wmtsLayer?: { wmtsLegendUrl: string; wmsLegendUrl: string; layerName: string; originalUrl: string };
  title?: string;
  standalone?: boolean;
}) {
  // Create a stable unique identifier for this legend
  const uniqueId = useMemo(() => {
    if (wmsLayer) {
      return `wms-${wmsLayer.baseUrl}-${wmsLayer.layers}`;
    } else if (wmtsLayer) {
      return `wmts-${wmtsLayer.originalUrl}`;
    }
    return 'unknown';
  }, [wmsLayer?.baseUrl, wmsLayer?.layers, wmtsLayer?.originalUrl]);
  
  const [legendUrl, setLegendUrl] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [hasError, setHasError] = useState<boolean>(false);
  const [hasFallbackAttempted, setHasFallbackAttempted] = useState<boolean>(false);
  const [lastUniqueId, setLastUniqueId] = useState<string>("");
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);
  
  useEffect(() => {
    // Only reset states if this is actually a different layer
    if (lastUniqueId !== uniqueId) {
      setIsLoading(true);
      setHasError(false);
      setHasFallbackAttempted(false);
      setLastUniqueId(uniqueId);
      
      if (wmsLayer) {
        // Original WMS legend URL
        const wmsLegendUrl = `${wmsLayer.baseUrl}?service=WMS&request=GetLegendGraphic&layer=${wmsLayer.layers}&format=image/png`;
        setLegendUrl(wmsLegendUrl);
      } else if (wmtsLayer) {
        // For WMTS, start with WMTS GetLegendGraphic (for non-standard providers like FAO)
        if (wmtsLayer.wmtsLegendUrl) {
          setLegendUrl(wmtsLayer.wmtsLegendUrl);
        } else if (wmtsLayer.wmsLegendUrl) {
          // Direct WMS fallback if no WMTS URL available
          setLegendUrl(wmtsLayer.wmsLegendUrl);
          setHasFallbackAttempted(true); // Mark as already using fallback
        } else {
          setHasError(true);
          setIsLoading(false);
        }
      } else {
        setHasError(true);
        setIsLoading(false);
      }
    }
  }, [uniqueId, wmsLayer, wmtsLayer, lastUniqueId]);
  
  // Don't render if no valid legend URL or has error
  if (!legendUrl || hasError) {
    return null;
  }
  
  const baseClasses = "bg-white p-2 rounded shadow";
  const positionClasses = standalone ? "absolute bottom-2 right-2 z-[9999]" : "";
  // Fixed width of 15% of screen width
  const sizeClasses = "w-[15vw] min-w-[200px]";
  
  return (
    <div className={`${baseClasses} ${positionClasses} ${sizeClasses}`.trim()}>
      {/* Header with title and toggle button */}
      <div className="flex items-center justify-between mb-2">
        {title && (
          <h4 className={`font-bold text-sm flex-1 mr-2 ${
            isCollapsed 
              ? 'truncate' // Truncate with ellipsis when collapsed
              : 'break-words' // Allow line breaks when expanded
          }`}>
            {title}
          </h4>
        )}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded hover:bg-gray-100 transition-colors"
          title={isCollapsed ? "Expand legend" : "Collapse legend"}
          aria-label={isCollapsed ? "Expand legend" : "Collapse legend"}
        >
          <svg 
            className={`w-4 h-4 transition-transform ${isCollapsed ? 'rotate-0' : 'rotate-180'}`} 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>
      
      {/* Legend content - only show when not collapsed */}
      {!isCollapsed && (
        <>
          {isLoading && (
            <div className="flex items-center justify-center h-16 text-xs text-gray-500">
              Loading legend...
            </div>
          )}
          <img 
            src={legendUrl} 
            alt="Layer Legend" 
            className="max-h-32 w-full object-contain"
            style={{ display: isLoading ? 'none' : 'block' }}
            onLoad={() => {
              setIsLoading(false);
              console.log('Legend loaded successfully:', legendUrl);
            }}
            onError={(e) => {
              console.warn('Legend image failed to load:', legendUrl);
              
              // If this was a WMTS legend that failed and we haven't tried fallback yet
              if (wmtsLayer && 
                  legendUrl === wmtsLayer.wmtsLegendUrl && 
                  wmtsLayer.wmsLegendUrl && 
                  !hasFallbackAttempted) {
                console.log('Trying WMS fallback for WMTS legend');
                setHasFallbackAttempted(true);
                setLegendUrl(wmtsLayer.wmsLegendUrl);
                setIsLoading(true); // Reset loading state for fallback attempt
              } else {
                // Final failure - hide the legend
                console.log('Legend loading failed permanently');
                setHasError(true);
                setIsLoading(false);
              }
            }}
          />
        </>
      )}
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
  
  // Memoize legend components to prevent unnecessary re-renders
  const legendComponents = useMemo(() => {
    return visibleLayersWithLegends.map((layer) => {
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
    }).filter(Boolean);
  }, [visibleLayersWithLegends.map(l => `${l.id}-${l.data_link}`).join(',')]);
  
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
          {legendComponents.length > 0 && (
            <div className="absolute bottom-2 right-2 z-[9999] space-y-2">
              {legendComponents}
            </div>
          )}
        </MapContainer>
      </div>
    </div>
  );
}
