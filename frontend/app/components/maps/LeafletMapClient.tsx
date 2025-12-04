"use client";

import {
  MapContainer,
  LayersControl,
  TileLayer,
  WMSTileLayer,
  GeoJSON,
  useMap,
} from "react-leaflet";
import { useState, useEffect, useRef, useMemo, useCallback, memo } from "react";
// Fix leaflet's default icon path issue
import "leaflet/dist/leaflet.css";
import L from "leaflet";

import { useMapStore } from "../../stores/mapStore";
import { useLayerStore } from "../../stores/layerStore";
import { useUIStore } from "../../stores/uiStore";
import { ZoomToSelected } from "./ZoomToLayer";
import Logger from "../../utils/logger";

import { GeoDataObject, LayerStyle } from "../../models/geodatamodel";

// ============================================
// GeoJSON CACHE IMPLEMENTATION
// ============================================

interface CacheEntry {
  data: any;
  timestamp: number;
  size: number;
}

class GeoJSONCache {
  private cache = new Map<string, CacheEntry>();
  private maxSize = 50 * 1024 * 1024; // 50MB cache limit
  private maxAge = 30 * 60 * 1000; // 30 minutes
  private currentSize = 0;

  set(url: string, data: any): void {
    // Estimate size (rough approximation)
    const size = JSON.stringify(data).length;
    
    // Evict old entries if cache is full
    while (this.currentSize + size > this.maxSize && this.cache.size > 0) {
      this.evictOldest();
    }

    const entry: CacheEntry = {
      data,
      timestamp: Date.now(),
      size,
    };
    
    this.cache.set(url, entry);
    this.currentSize += size;
    
    Logger.log(`[GeoJSONCache] Cached ${url} (${(size / 1024).toFixed(2)} KB). Cache size: ${(this.currentSize / 1024 / 1024).toFixed(2)} MB`);
  }

  get(url: string): any | null {
    const entry = this.cache.get(url);
    if (!entry) return null;

    // Check if entry is expired
    if (Date.now() - entry.timestamp > this.maxAge) {
      this.delete(url);
      return null;
    }

    Logger.log(`[GeoJSONCache] Cache HIT for ${url}`);
    return entry.data;
  }

  delete(url: string): void {
    const entry = this.cache.get(url);
    if (entry) {
      this.cache.delete(url);
      this.currentSize -= entry.size;
      Logger.log(`[GeoJSONCache] Deleted ${url}. Cache size: ${(this.currentSize / 1024 / 1024).toFixed(2)} MB`);
    }
  }

  private evictOldest(): void {
    let oldest: [string, CacheEntry] | null = null;
    
    for (const [url, entry] of this.cache.entries()) {
      if (!oldest || entry.timestamp < oldest[1].timestamp) {
        oldest = [url, entry];
      }
    }
    
    if (oldest) {
      this.delete(oldest[0]);
      Logger.log(`[GeoJSONCache] Evicted oldest entry: ${oldest[0]}`);
    }
  }

  clear(): void {
    this.cache.clear();
    this.currentSize = 0;
    Logger.log('[GeoJSONCache] Cache cleared');
  }

  getCacheStats(): { entries: number; size: number; maxSize: number } {
    return {
      entries: this.cache.size,
      size: this.currentSize,
      maxSize: this.maxSize,
    };
  }
}

// Global cache instance
const geoJSONCache = new GeoJSONCache();

// Expose cache to window for debugging in development
if (typeof window !== "undefined") {
  (window as any).geoJSONCache = geoJSONCache;
  Logger.log("[GeoJSONCache] Cache exposed to window.geoJSONCache for debugging");
}


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

function useZoomToLayer(layers: GeoDataObject[]) {
  const map = useMap();
  const zoomedLayers = useRef<Set<string | number>>(new Set());

  useEffect(() => {
    layers.forEach(async (layer) => {
      if (!layer.visible || zoomedLayers.current.has(layer.id)) return;

      if (
        layer.layer_type?.toUpperCase() === "WMS" ||
        layer.layer_type?.toUpperCase() === "WFS"
      ) {
        // Handle bounding box from layer store
        if (layer.bounding_box) {
          let bounds = null;

          // Handle WKT polygon format
          if (
            typeof layer.bounding_box === "string" &&
            layer.bounding_box.includes("POLYGON")
          ) {
            const match = layer.bounding_box.match(/POLYGON\(\((.+?)\)\)/);
            if (match) {
              const coords = match[1]
                .split(",")
                .map((pair) => pair.trim().split(" ").map(Number))
                .filter(([lng, lat]) => !isNaN(lng) && !isNaN(lat));

              if (coords.length > 0) {
                const lats = coords.map(([lng, lat]) => lat);
                const lngs = coords.map(([lng, lat]) => lng);

                const southWest = L.latLng(
                  Math.min(...lats),
                  Math.min(...lngs),
                );
                const northEast = L.latLng(
                  Math.max(...lats),
                  Math.max(...lngs),
                );
                bounds = L.latLngBounds(southWest, northEast);
              }
            }
          }
          // Handle array format [minX, minY, maxX, maxY]
          else if (
            Array.isArray(layer.bounding_box) &&
            layer.bounding_box.length >= 4
          ) {
            const [minX, minY, maxX, maxY] = layer.bounding_box;
            bounds = L.latLngBounds(
              [minY, minX], // southwest
              [maxY, maxX], // northeast
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

/**
 * When the map container element is resized (e.g., panels collapse/expand),
 * invalidate the Leaflet map size so tiles redraw correctly.
 */
function InvalidateMapOnResize() {
  const map = useMap();
  useEffect(() => {
    const container = map.getContainer();
    const ro = new ResizeObserver(() => {
      map.invalidateSize();
    });
    ro.observe(container);
    return () => {
      ro.disconnect();
    };
  }, [map]);
  return null;
}

/**
 * Custom Scale Control with dynamic positioning based on layer panel state
 * 
 * Note: Leaflet's scale control calculates distances based on the Web Mercator projection (EPSG:3857)
 * at the center latitude of the current view. The scale is most accurate near the equator and becomes
 * less accurate towards the poles due to projection distortion.
 */
function CustomScaleControl() {
  const map = useMap();
  const layerPanelCollapsed = useUIStore((s) => s.layerPanelCollapsed);
  const scaleRef = useRef<L.Control.Scale | null>(null);
  
  // Create scale control once when component mounts
  useEffect(() => {
    const scale = L.control.scale({
      position: 'bottomleft',
      imperial: true,
      metric: true,
      maxWidth: 100, // Maximum width of the scale control in pixels
      updateWhenIdle: false, // Update scale continuously during map movements
    });
    
    scale.addTo(map);
    scaleRef.current = scale;
    
    // Log scale info for debugging
    Logger.debug("[CustomScaleControl] Scale control added to map");
    
    return () => {
      if (scaleRef.current) {
        scaleRef.current.remove();
        scaleRef.current = null;
        Logger.debug("[CustomScaleControl] Scale control removed from map");
      }
    };
  }, [map]);
  
  // Update positioning when layer panel collapse state changes
  useEffect(() => {
    if (scaleRef.current) {
      const scaleContainer = scaleRef.current.getContainer();
      if (scaleContainer) {
        // When collapsed: larger margin to clear the floating icon
        // When expanded: minimal margin since panel is open
        scaleContainer.style.marginLeft = layerPanelCollapsed ? '90px' : '10px';
      }
    }
  }, [layerPanelCollapsed]);
  
  return null;
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
    Logger.error("Error parsing WMS URL:", err);
    return {
      baseUrl: access_url,
      layers: "",
      format: "image/png",
      transparent: true,
    };
  }
}

// Function to parse WMTS URLs and extract layer information for legend generation
function parseWMTSUrl(access_url: string) {
  try {
    const urlObj = new URL(access_url);
    const baseUrl = `${urlObj.origin}${urlObj.pathname}`;

    // Extract all parameters from the original WMTS URL
    const originalParams = urlObj.searchParams;

    // Detect version if provided (common param names: version / VERSION)
    const versionParam =
      originalParams.get("version") || originalParams.get("VERSION") || "";
    let version = versionParam; // may be empty; we'll fallback later

    // Get layer name from parameters
    let layerName = originalParams.get("layer") || originalParams.get("LAYER");

    // If no layer parameter, try to extract from REST-style path
    if (!layerName) {
      const pathParts = urlObj.pathname.split("/");
      const restIndex = pathParts.indexOf("rest");
      if (restIndex !== -1 && restIndex + 1 < pathParts.length) {
        layerName = pathParts[restIndex + 1];
      }
    }
    // Extra heuristic: scan any path segment containing a ':' (workspace:layer)
    if (!layerName) {
      const colonSegment = urlObj.pathname
        .split("/")
        .find((p) => p.includes(":"));
      if (colonSegment) layerName = colonSegment;
    }
    // Remove potential style or tile matrix set segments erroneously picked up
    if (
      layerName &&
      (layerName.toLowerCase() === "default" || layerName.includes("{"))
    ) {
      layerName = "";
    }

    if (!layerName) {
      Logger.warn("Could not extract layer name from WMTS URL:", access_url);
      return {
        wmtsLegendUrl: "",
        wmsLegendUrl: "",
        layerName: "",
        originalUrl: access_url,
        version: version || undefined,
      };
    }

    // Extract workspace and final layer name if in format "workspace:layer"
    let workspace = "";
    let finalLayerName = layerName;
    if (layerName.includes(":")) {
      [workspace, finalLayerName] = layerName.split(":");
    }

    // Derive GeoServer base (up to /geoserver)
    const pathParts = urlObj.pathname.split("/").filter(Boolean);
    const geoserverIdx = pathParts.indexOf("geoserver");
    const geoserverBase =
      geoserverIdx !== -1
        ? `${urlObj.origin}/${pathParts.slice(0, geoserverIdx + 1).join("/")}`
        : `${urlObj.origin}`;
    // Standard WMTS KVP endpoint
    const wmtsKvpBase = `${geoserverBase}/gwc/service/wmts`;
    // Build WMS legend base for same layer
    const wmsBaseUrl = `${geoserverBase}/wms`;
    const wmsLegendParams = new URLSearchParams({
      service: "WMS",
      version: "1.1.0",
      request: "GetLegendGraphic",
      format: "image/png",
      layer: layerName,
    });
    const wmsLegendUrl = `${wmsBaseUrl}?${wmsLegendParams.toString()}`;

    const result = {
      wmtsLegendUrl: "", // not using non-standard WMTS legend
      wmsLegendUrl,
      layerName: finalLayerName,
      workspace,
      fullLayerName: workspace
        ? `${workspace}:${finalLayerName}`
        : finalLayerName,
      originalUrl: access_url,
      wmtsKvpBase,
      version: version || undefined,
    };

    Logger.log("WMTS URL parsing result:", {
      originalUrl: access_url,
      parsed: result,
    });

    return result;
  } catch (err) {
    Logger.error("Error parsing WMTS URL:", err);
    return {
      wmtsLegendUrl: "",
      wmsLegendUrl: "",
      layerName: "",
      originalUrl: access_url,
    };
  }
}

// Build a WMTS KVP tile URL template mapping Leaflet z/x/y to WMTS parameters
function buildWMTSKvpTemplate(
  base: string,
  fullLayerName: string,
  tileMatrixSet: string,
  format: string = "image/png",
  version: string = "1.0.0",
) {
  // GeoServer expects tilematrix like EPSG:3857:Z
  return `${base}?service=WMTS&version=${encodeURIComponent(version)}&request=GetTile&layer=${encodeURIComponent(fullLayerName)}&style=&tilematrixset=${encodeURIComponent(tileMatrixSet)}&format=${encodeURIComponent(format)}&tilematrix=${encodeURIComponent(tileMatrixSet)}:{z}&tilerow={y}&tilecol={x}`;
}

// Accept only WebMercator variants for WMTS (EPSG:3857 family)
function isWebMercatorMatrixSet(name: string | undefined | null): boolean {
  if (!name) return false;
  return /3857|900913|googlemapscompatible|google|web ?mercator|mercatorquad/i.test(
    name,
  );
}

function pickWebMercatorMatrixSet(candidateSets: string[]): string | undefined {
  if (!candidateSets || !candidateSets.length) return undefined;
  // First pass: direct EPSG:3857 style codes
  let chosen = candidateSets.find((s) => /3857/.test(s));
  if (chosen) return chosen;
  // Second: common aliases
  chosen = candidateSets.find((s) => /900913|google|mercator/i.test(s));
  return chosen;
}

// Parse a WCS GetCoverage URL and derive a WMS GetMap base (Leaflet-friendly) + legend params
function parseWCSUrl(access_url: string) {
  try {
    const urlObj = new URL(access_url);
    const baseUrl = `${urlObj.origin}${urlObj.pathname}`; // e.g. https://server/geoserver/wcs
    const params = urlObj.searchParams;
    // coverageId may appear as coverageId or coverage
    const coverageId = params.get("coverageId") || params.get("coverage") || "";
    if (!coverageId) {
      Logger.warn("Could not extract coverageId from WCS URL:", access_url);
    }
    // Derive WMS base by swapping trailing /wcs or /ows with /wms
    let wmsBaseUrl = baseUrl;
    if (wmsBaseUrl.endsWith("/wcs")) {
      wmsBaseUrl = wmsBaseUrl.slice(0, -4) + "/wms";
    } else if (wmsBaseUrl.endsWith("/ows")) {
      wmsBaseUrl = wmsBaseUrl.replace(/\/ows$/, "/wms");
    } else if (!wmsBaseUrl.endsWith("/wms")) {
      // Best-effort: append /wms if neither present
      wmsBaseUrl = wmsBaseUrl + "/wms";
    }
    // Build legend URL (standard WMS GetLegendGraphic)
    const legendParams = new URLSearchParams({
      service: "WMS",
      request: "GetLegendGraphic",
      version: "1.1.0",
      format: "image/png",
      layer: coverageId,
    });
    const legendUrl = `${wmsBaseUrl}?${legendParams.toString()}`;
    return {
      baseUrl: wmsBaseUrl,
      layers: coverageId,
      format: "image/png",
      transparent: true,
      legendUrl,
      originalUrl: access_url,
    };
  } catch (err) {
    Logger.error("Error parsing WCS URL:", err);
    return {
      baseUrl: access_url,
      layers: "",
      format: "image/png",
      transparent: true,
      legendUrl: "",
      originalUrl: access_url,
    };
  }
}

// Memoized component to prevent unnecessary re-renders
const LeafletGeoJSONLayer = memo(function LeafletGeoJSONLayer({
  url,
  layerStyle,
}: {
  url: string;
  layerStyle?: LayerStyle;
}) {
  const [data, setData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const map = useMap();

  // Debug: Check if map is available
  useEffect(() => {
    if (map) {
      Logger.log(
        `[LeafletGeoJSONLayer] Map context available for ${url}, map center:`,
        map.getCenter(),
      );
    } else {
      Logger.error(`[LeafletGeoJSONLayer] NO MAP CONTEXT for ${url}`);
    }
  }, [map, url]);

  // Create stable key from style to trigger re-mount only when style actually changes
  const styleKey = useMemo(() => {
    if (!layerStyle) return "default";
    // Create a stable key from style properties that affect rendering
    return `${layerStyle.stroke_color || "default"}-${layerStyle.fill_color || "default"}-${layerStyle.stroke_weight || 2}`;
  }, [layerStyle]);

  useEffect(() => {
    let cancelled = false;
    
    // Check cache first
    const cachedData = geoJSONCache.get(url);
    if (cachedData) {
      Logger.log(`[LeafletGeoJSONLayer] Using cached data for ${url}`);
      setData(cachedData);
      setIsLoading(false);
      return;
    }
    
    setIsLoading(true);
    Logger.log(`[LeafletGeoJSONLayer] Starting fetch for ${url}`);

    const geometryTypes = new Set([
      "Point",
      "MultiPoint",
      "LineString",
      "MultiLineString",
      "Polygon",
      "MultiPolygon",
    ]);

    const normalizeToFeatureCollection = (input: any): any | null => {
      if (!input) return null;

      if (Array.isArray(input)) {
        const features = input
          .map((item: any, idx: number) => {
            if (!item) return null;
            if (item.type === "Feature" && item.geometry) return item;
            if (geometryTypes.has(item.type) && item.coordinates) {
              const props =
                item.properties && typeof item.properties === "object"
                  ? { ...item.properties }
                  : {};
              if (!Object.keys(props).length) {
                if (item.id !== undefined) props.id = item.id;
                else props.id = idx + 1;
              }
              return {
                type: "Feature",
                properties: props,
                geometry: { type: item.type, coordinates: item.coordinates },
              };
            }
            return null;
          })
          .filter(Boolean);
        if (!features.length) return null;
        return { type: "FeatureCollection", features };
      }

      if (typeof input !== "object") return null;

      if (input.type === "FeatureCollection" && Array.isArray(input.features)) {
        return input;
      }

      if (input.type === "Feature" && input.geometry) {
        const fc: any = {
          type: "FeatureCollection",
          features: [input],
        };
        if (input.crs) fc.crs = input.crs;
        if (input.bbox) fc.bbox = input.bbox;
        return fc;
      }

      if (
        input.type === "GeometryCollection" &&
        Array.isArray(input.geometries)
      ) {
        const features = input.geometries
          .map((geom: any, idx: number) => {
            if (!geom?.type) return null;
            return {
              type: "Feature",
              properties: { id: idx, ...(input.properties || {}) },
              geometry: geom,
            };
          })
          .filter(Boolean);
        if (!features.length) return null;
        const fc: any = { type: "FeatureCollection", features };
        if (input.crs) fc.crs = input.crs;
        if (input.bbox) fc.bbox = input.bbox;
        return fc;
      }

      if (geometryTypes.has(input.type) && input.coordinates) {
        const props =
          input.properties && typeof input.properties === "object"
            ? { ...input.properties }
            : {};
        if (!Object.keys(props).length) {
          if (input.id !== undefined) props.id = input.id;
          else props.id = 1;
        }
        const fc: any = {
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              properties: props,
              geometry: { type: input.type, coordinates: input.coordinates },
            },
          ],
        };
        if (input.crs) fc.crs = input.crs;
        if (input.bbox) fc.bbox = input.bbox;
        return fc;
      }

      if (Array.isArray(input.features)) {
        return { ...input, type: input.type || "FeatureCollection" };
      }

      return null;
    };

    const extractDeclaredCrs = (candidate: any): string | null => {
      if (!candidate || typeof candidate !== "object") return null;
      try {
        return (
          candidate.crs?.properties?.name ||
          candidate.crs?.name ||
          candidate.features?.[0]?.crs?.properties?.name ||
          candidate.features?.[0]?.crs?.name ||
          null
        );
      } catch {
        return null;
      }
    };

    (async () => {
      try {
        Logger.log("Fetching GeoJSON/WFS layer:", url);
        // If this is a WFS request and lacks srsName, prefer EPSG:4326 for Leaflet
        let requestUrl = url;
        try {
          const testU = new URL(url);
          if (
            (/wfs/i.test(testU.search) ||
              testU.searchParams.get("service")?.toUpperCase() === "WFS") &&
            !testU.searchParams.get("srsName")
          ) {
            testU.searchParams.set("srsName", "EPSG:4326");
            requestUrl = testU.toString();
          }
        } catch (e) {
          /* ignore */
        }

        let res = await fetch(requestUrl, {
          headers: {
            Accept: "application/json, application/geo+json, */*;q=0.1",
          },
        });
        if (!res.ok && requestUrl !== url) {
          // fallback to original URL if srsName caused failure
          res = await fetch(url, {
            headers: {
              Accept: "application/json, application/geo+json, */*;q=0.1",
            },
          });
        }
        const contentType = res.headers.get("content-type") || "";
        const contentLengthHeader = res.headers.get("content-length");
        let json: any = null;
        if (
          contentType.includes("application/json") ||
          contentType.includes("geo+json")
        ) {
          json = await res.json();
        } else {
          // Fallback: try to parse text if server mislabels
          const text = await res.text();
          const expectedBytes = contentLengthHeader
            ? parseInt(contentLengthHeader, 10)
            : null;
          const receivedBytes =
            typeof TextEncoder !== "undefined"
              ? new TextEncoder().encode(text).length
              : text.length;
          try {
            json = JSON.parse(text);
          } catch (e) {
            Logger.warn("Non-JSON WFS response, cannot render", {
              url,
              snippet: text.slice(0, 200),
              expectedBytes,
              receivedBytes,
            });
            if (expectedBytes !== null && receivedBytes < expectedBytes) {
              throw new Error(
                `GeoJSON response truncated (${receivedBytes}/${expectedBytes} bytes)`,
              );
            }
          }
        }
        if (!cancelled) {
          const featureCollection = normalizeToFeatureCollection(json);
          if (featureCollection) {
            // Detect CRS from GeoJSON 'crs' if present
            const declaredCrs =
              extractDeclaredCrs(json) || extractDeclaredCrs(featureCollection);
            // Extract first numeric coordinate pair recursively
            const extractFirstXY = (geom: any): [number, number] | null => {
              if (!geom) return null;
              const coords = geom.coordinates;
              if (!coords) return null;
              const dive = (c: any): any =>
                Array.isArray(c) && typeof c[0] !== "number" ? dive(c[0]) : c;
              const first = dive(coords);
              if (
                Array.isArray(first) &&
                typeof first[0] === "number" &&
                typeof first[1] === "number"
              )
                return [first[0], first[1]];
              return null;
            };
            const firstFeature = featureCollection.features?.[0];
            const firstXY = firstFeature
              ? extractFirstXY(firstFeature.geometry)
              : null;
            const looksLike3857 = (() => {
              if (!firstXY) return false;
              const [x, y] = firstXY;
              // WebMercator world bounds (slightly padded)
              const max = 20050000;
              const plausibleMerc =
                Math.abs(x) <= max &&
                Math.abs(y) <= max &&
                (Math.abs(x) > 180 || Math.abs(y) > 90);
              if (declaredCrs) {
                if (/3857|900913/i.test(declaredCrs)) return true;
                if (/4326/i.test(declaredCrs)) return false;
              }
              return plausibleMerc;
            })();

            const toLonLat = (x: number, y: number) => {
              const R = 6378137;
              const lon = ((x / R) * 180) / Math.PI;
              const lat =
                ((2 * Math.atan(Math.exp(y / R)) - Math.PI / 2) * 180) /
                Math.PI;
              return [lon, lat];
            };
            const reprojectGeometry = (geom: any): any => {
              if (!geom || !geom.type) return geom;
              const mapCoords = (arr: any): any =>
                Array.isArray(arr[0])
                  ? arr.map(mapCoords)
                  : (() => {
                      const [x, y] = arr;
                      const [lon, lat] = toLonLat(x, y);
                      return [lon, lat];
                    })();
              switch (geom.type) {
                case "Point":
                  return {
                    type: "Point",
                    coordinates: toLonLat(
                      geom.coordinates[0],
                      geom.coordinates[1],
                    ),
                  };
                case "MultiPoint":
                  return {
                    type: "MultiPoint",
                    coordinates: geom.coordinates.map((c: any) =>
                      toLonLat(c[0], c[1]),
                    ),
                  };
                case "LineString":
                  return {
                    type: "LineString",
                    coordinates: geom.coordinates.map((c: any) =>
                      toLonLat(c[0], c[1]),
                    ),
                  };
                case "MultiLineString":
                  return {
                    type: "MultiLineString",
                    coordinates: geom.coordinates.map((l: any) =>
                      l.map((c: any) => toLonLat(c[0], c[1])),
                    ),
                  };
                case "Polygon":
                  return {
                    type: "Polygon",
                    coordinates: geom.coordinates.map((r: any) =>
                      r.map((c: any) => toLonLat(c[0], c[1])),
                    ),
                  };
                case "MultiPolygon":
                  return {
                    type: "MultiPolygon",
                    coordinates: geom.coordinates.map((p: any) =>
                      p.map((r: any) =>
                        r.map((c: any) => toLonLat(c[0], c[1])),
                      ),
                    ),
                  };
                default:
                  return geom;
              }
            };
            let processedCollection = featureCollection;

            if (looksLike3857) {
              Logger.log(
                "Reprojecting WFS geometry from EPSG:3857 -> EPSG:4326",
              );
              processedCollection = {
                ...featureCollection,
                features: featureCollection.features.map((f: any) => ({
                  ...f,
                  geometry: reprojectGeometry(f.geometry),
                })),
                crs: { type: "name", properties: { name: "EPSG:4326" } },
              };
            }
            // Validate resulting coords fall within lat/lon plausible ranges; if not, revert to original
            const validateLatLon = (fc: any) => {
              try {
                for (const f of fc.features.slice(0, 5)) {
                  const flat: number[] = [];
                  const walk = (arr: any) => {
                    if (typeof arr[0] === "number") {
                      flat.push(arr[0], arr[1]);
                      return;
                    }
                    for (const c of arr) walk(c);
                  };
                  walk(f.geometry.coordinates);
                  for (let i = 0; i < flat.length; i += 2) {
                    const lon = flat[i],
                      lat = flat[i + 1];
                    if (Math.abs(lon) > 180 || Math.abs(lat) > 90) return false;
                  }
                }
                return true;
              } catch {
                return true;
              }
            };
            if (!validateLatLon(processedCollection) && looksLike3857) {
              Logger.warn(
                "Reprojected coordinates invalid for lat/lon; falling back to original geometry.",
              );
              // refetch original without reprojection
              setData(null);
              const timeoutId = setTimeout(() => {
                if (!cancelled) {
                  fetch(url)
                    .then((r) => r.json())
                    .then((orig) => {
                      if (!cancelled) {
                        const normalized = normalizeToFeatureCollection(orig);
                        if (normalized) {
                          setData(normalized);
                          setIsLoading(false);
                        } else {
                          setIsLoading(false);
                        }
                      }
                    })
                    .catch(() => {
                      if (!cancelled) {
                        setIsLoading(false);
                      }
                    });
                }
              }, 0);
              // Store timeout ID for cleanup
              (window as any).__leafletTimeoutId = timeoutId;
              return;
            }
            setData(processedCollection);
            // Cache the processed data
            geoJSONCache.set(url, processedCollection);
            setIsLoading(false);
            Logger.log(
              `[LeafletGeoJSONLayer] Successfully loaded data for ${url}, features:`,
              processedCollection.features?.length,
            );
          } else {
            Logger.warn("Fetched data is not valid GeoJSON FeatureCollection", {
              url,
              json,
            });
            setData(null);
            setIsLoading(false);
          }
        }
      } catch (err) {
        if (!cancelled) {
          Logger.error("Error fetching GeoJSON/WFS:", url, err);
          setIsLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
      setIsLoading(false);
      // Clear any pending setTimeout to prevent memory leak
      if ((window as any).__leafletTimeoutId) {
        clearTimeout((window as any).__leafletTimeoutId);
        delete (window as any).__leafletTimeoutId;
      }
    };
  }, [url]); // Only re-fetch when URL changes

  const onEachFeature = useCallback((feature: any, layer: L.Layer) => {
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
              `,
              )
              .join("")}
          </tbody>
        </table>
      </div>
    `;

    // Bind popup with size constraints to prevent clipping
    layer.bindPopup(popupContent, {
      maxWidth: 600,  // Maximum popup width (will be further constrained by CSS)
      maxHeight: 400, // Maximum popup height (will be further constrained by CSS)
      autoPan: true,  // Automatically pan map to fit popup
      autoPanPadding: [50, 50], // Padding from map edges
      keepInView: true, // Keep popup in view when map is panned
    });

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
  }, []); // Empty deps - this function doesn't depend on external state

  let geojsonRef: L.GeoJSON | null = null;

  const handleGeoJsonRef = useCallback((layer: L.GeoJSON | null) => {
    if (!layer) return;
    geojsonRef = layer;

    // Always fit bounds for newly added layers
    try {
      const bounds = layer.getBounds();
      if (bounds && bounds.isValid && bounds.isValid()) {
        map.fitBounds(bounds.pad(0.05));
      }
    } catch (error) {
      Logger.warn("Error fitting bounds for layer:", url, error);
    }
  }, [map, url]);

  const pointToLayer = useCallback((feature: any, latlng: L.LatLng) => {
    // Check for marker-color and marker-symbol from feature properties (e.g., from AIS/OpenSky data)
    const featureMarkerColor = feature?.properties?.["marker-color"];
    const featureMarkerSymbol = feature?.properties?.["marker-symbol"];
    
    // Debug logging for marker properties
    if (featureMarkerColor || featureMarkerSymbol) {
      Logger.log(`[pointToLayer] Feature with marker props:`, {
        color: featureMarkerColor,
        symbol: featureMarkerSymbol,
        name: feature?.properties?.name || feature?.properties?.callsign,
        heading: feature?.properties?.heading,
      });
    }
    
    // Use feature marker-color if available, otherwise fall back to layer style
    const markerColor = featureMarkerColor || layerStyle?.stroke_color || "#3388ff";
    const fillColor = featureMarkerColor || layerStyle?.fill_color || "#3388ff";
    
    // Use custom radius if provided in style, default to 4
    // Adjust radius based on symbol type for better visibility
    let radius = layerStyle?.radius || 4;
    if (featureMarkerSymbol === "airport" || featureMarkerSymbol === "ferry") {
      radius = 6; // Larger for aircraft/vessels
    } else if (featureMarkerSymbol === "triangle" || featureMarkerSymbol === "triangle-down") {
      radius = 5; // Medium for ascending/descending aircraft
    }
    
    // For symbols like triangle, triangle-down, create SVG-based DivIcon markers
    if (featureMarkerSymbol === "triangle" || featureMarkerSymbol === "triangle-down") {
      const heading = feature?.properties?.heading || 0;
      const svgIcon = L.divIcon({
        className: 'custom-marker-icon',
        html: `<svg width="20" height="20" viewBox="0 0 20 20" style="transform: rotate(${heading}deg);">
          <polygon points="10,2 18,18 10,14 2,18" fill="${markerColor}" stroke="#fff" stroke-width="1" opacity="0.9"/>
        </svg>`,
        iconSize: [20, 20],
        iconAnchor: [10, 10],
      });
      return L.marker(latlng, { icon: svgIcon });
    }
    
    // For airport/ferry symbols, use plane/ship SVG icons
    if (featureMarkerSymbol === "airport") {
      const heading = feature?.properties?.heading || 0;
      const svgIcon = L.divIcon({
        className: 'custom-marker-icon',
        html: `<svg width="24" height="24" viewBox="0 0 24 24" style="transform: rotate(${heading}deg);">
          <path d="M21,16v-2l-8-5V3.5C13,2.67,12.33,2,11.5,2S10,2.67,10,3.5V9l-8,5v2l8-2.5V19l-2,1.5V22l3.5-1l3.5,1v-1.5L13,19v-5.5L21,16z" fill="${markerColor}" stroke="#fff" stroke-width="0.5"/>
        </svg>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      });
      return L.marker(latlng, { icon: svgIcon });
    }
    
    if (featureMarkerSymbol === "ferry") {
      const heading = feature?.properties?.heading || feature?.properties?.course || 0;
      const svgIcon = L.divIcon({
        className: 'custom-marker-icon',
        html: `<svg width="20" height="20" viewBox="0 0 24 24" style="transform: rotate(${heading}deg);">
          <path d="M12,2L4,12l8,10l8-10L12,2z" fill="${markerColor}" stroke="#fff" stroke-width="1"/>
        </svg>`,
        iconSize: [20, 20],
        iconAnchor: [10, 10],
      });
      return L.marker(latlng, { icon: svgIcon });
    }
    
    // Default: circle marker with feature color support
    return L.circleMarker(latlng, {
      radius: radius,
      // Apply style properties for circle markers
      color: markerColor,
      weight: layerStyle?.stroke_weight || 2,
      opacity: layerStyle?.stroke_opacity || 0.85,
      fillColor: fillColor,
      fillOpacity: featureMarkerColor ? 0.7 : (layerStyle?.fill_opacity || 0.15), // Higher opacity for colored markers
      dashArray: layerStyle?.stroke_dash_array || undefined,
      dashOffset: layerStyle?.stroke_dash_offset?.toString() || undefined,
      // Apply advanced line properties
      lineCap: (layerStyle?.line_cap as any) || "round",
      lineJoin: (layerStyle?.line_join as any) || "round",
    });
  }, [layerStyle]);

  // Create enhanced style function that uses layer style properties
  const getFeatureStyle = useCallback((feature?: any) => {
    // Check for marker-color from feature properties (e.g., from AIS/OpenSky data)
    const featureMarkerColor = feature?.properties?.["marker-color"];
    
    const baseStyle = {
      color: featureMarkerColor || layerStyle?.stroke_color || "#3388ff",
      weight: layerStyle?.stroke_weight || 2,
      opacity: layerStyle?.stroke_opacity || 0.85,
      fillColor: featureMarkerColor || layerStyle?.fill_color || "#3388ff",
      fillOpacity: featureMarkerColor ? 0.5 : (layerStyle?.fill_opacity || 0.15), // Higher opacity for colored features
      dashArray: layerStyle?.stroke_dash_array || undefined,
      dashOffset: layerStyle?.stroke_dash_offset?.toString() || undefined,
      // Apply advanced line properties
      lineCap: (layerStyle?.line_cap as any) || "round",
      lineJoin: (layerStyle?.line_join as any) || "round",
    };

    // Apply conditional styling if available
    if (layerStyle?.style_conditions && feature?.properties) {
      // Simple example: different colors based on property values
      const conditions = layerStyle.style_conditions;
      for (const [property, conditionConfig] of Object.entries(conditions)) {
        if (
          feature.properties[property] &&
          typeof conditionConfig === "object"
        ) {
          const value = feature.properties[property];
          if (conditionConfig.color_map && conditionConfig.color_map[value]) {
            baseStyle.color = conditionConfig.color_map[value];
            baseStyle.fillColor = conditionConfig.color_map[value];
          }
        }
      }
    }

    return baseStyle;
  }, [layerStyle]);

  Logger.log(
    `[LeafletGeoJSONLayer] Render: url=${url}, hasData=${!!data}, isLoading=${isLoading}, features=${data?.features?.length || 0}`,
  );

  if (data && !isLoading) {
    Logger.log(
      `[LeafletGeoJSONLayer] Returning <GeoJSON> component for ${url} with ${data.features?.length} features`,
    );
    return (
      <GeoJSON
        key={`${url}-${styleKey}`}
        data={data}
        onEachFeature={onEachFeature}
        pointToLayer={pointToLayer}
        ref={handleGeoJsonRef}
        style={getFeatureStyle}
      />
    );
  } else {
    if (isLoading) Logger.log(`[LeafletGeoJSONLayer] Still loading ${url}`);
    if (!data && !isLoading)
      Logger.log(`[LeafletGeoJSONLayer] No data for ${url}`);
    return null;
  }
});

// Custom component to handle GetFeatureInfo requests for WMS layers.
function GetFeatureInfo({
  wmsLayer,
}: {
  wmsLayer: {
    baseUrl: string;
    layers: string;
    format: string;
    transparent: boolean;
  };
}) {
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
        request: "GetFeatureInfo",
        service: "WMS",
        srs: "EPSG:3857", // or use CRS for version 1.3.0
        version: "1.1.1",
        layers: wmsLayer.layers,
        query_layers: wmsLayer.layers,
        info_format: "text/html", // or application/json
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
          L.popup().setLatLng(e.latlng).setContent(html).openOn(map);
        })
        .catch((err) => Logger.error("GetFeatureInfo error:", err));
    };

    map.on("click", onClick);
    return () => {
      map.off("click", onClick);
    };
  }, [map, wmsLayer]);

  return null;
}

// Legend component that displays a title above the legend image.
const Legend = memo(function Legend({
  wmsLayer,
  wmtsLayer,
  title,
  standalone = false,
}: {
  wmsLayer?: {
    baseUrl: string;
    layers: string;
    format: string;
    transparent: boolean;
  };
  wmtsLayer?: {
    wmtsLegendUrl: string;
    wmsLegendUrl: string;
    layerName: string;
    originalUrl: string;
  };
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
    return "unknown";
  }, [wmsLayer?.baseUrl, wmsLayer?.layers, wmtsLayer?.originalUrl]);

  const [legendUrl, setLegendUrl] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [hasError, setHasError] = useState<boolean>(false);
  const [hasFallbackAttempted, setHasFallbackAttempted] =
    useState<boolean>(false);
  const [lastUniqueId, setLastUniqueId] = useState<string>("");
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);
  const [isImageMaximized, setIsImageMaximized] = useState<boolean>(false);

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
  const positionClasses = standalone
    ? "absolute bottom-2 right-2 z-[9999]"
    : "";
  // Fixed width of 15% of screen width
  const sizeClasses = "w-[15vw] min-w-[200px]";

  return (
    <div className={`${baseClasses} ${positionClasses} ${sizeClasses}`.trim()}>
      {/* Header with title and toggle button */}
      <div className="flex items-center justify-between mb-2">
        {title && (
          <h4
            className={`font-bold text-sm flex-1 mr-2 ${
              isCollapsed
                ? "truncate" // Truncate with ellipsis when collapsed
                : "break-words" // Allow line breaks when expanded
            }`}
          >
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
            className={`w-4 h-4 transition-transform ${isCollapsed ? "rotate-0" : "rotate-180"}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
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
          <div className="relative group cursor-pointer">
            <img
              src={legendUrl}
              alt="Layer Legend"
              className={`w-full object-contain transition-all duration-300 ease-in-out ${
                isImageMaximized ? "max-h-none" : "max-h-50"
              }`}
              style={{ display: isLoading ? "none" : "block" }}
              onClick={() => setIsImageMaximized(!isImageMaximized)}
              title={
                isImageMaximized ? "Click to minimize" : "Click to maximize"
              }
              onLoad={() => {
                setIsLoading(false);
                Logger.log("Legend loaded successfully:", legendUrl);
              }}
              onError={(e) => {
                Logger.warn("Legend image failed to load:", legendUrl);

                // If this was a WMTS legend that failed and we haven't tried fallback yet
                if (
                  wmtsLayer &&
                  legendUrl === wmtsLayer.wmtsLegendUrl &&
                  wmtsLayer.wmsLegendUrl &&
                  !hasFallbackAttempted
                ) {
                  Logger.log("Trying WMS fallback for WMTS legend");
                  setHasFallbackAttempted(true);
                  setLegendUrl(wmtsLayer.wmsLegendUrl);
                  setIsLoading(true); // Reset loading state for fallback attempt
                } else {
                  // Final failure - hide the legend
                  Logger.log("Legend loading failed permanently");
                  setHasError(true);
                  setIsLoading(false);
                }
              }}
            />
            {/* Hover indicator */}
            <div className="absolute bottom-1 right-1 bg-black bg-opacity-70 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              {isImageMaximized ? "Click to minimize" : "Click to maximize"}
            </div>
          </div>
        </>
      )}
    </div>
  );
});

export default function LeafletMapComponent() {
  const basemap = useMapStore((state) => state.basemap);
  const layers = useLayerStore((state) => state.layers);

  // Memoize visible layers to avoid recalculating on every render
  const visibleLayers = useMemo(() => 
    layers.filter((l) => l.visible),
    [layers]
  );

  // Use a stable key derived from the VISIBLE layer order so React knows when to recreate
  // the layer list. This ensures proper cleanup and reinitialization of layers
  // when their order changes. Only include visible layers since those are the only ones rendered.
  const layerOrderKey = useMemo(() => 
    visibleLayers.map((l) => l.id).join("-"),
    [visibleLayers]
  );

  // Get the first WMS layer from the layers array (if any) for GetFeatureInfo.
  const wmsLayerData = useMemo(() => 
    layers.find((layer) => layer.layer_type?.toUpperCase() === "WMS" && layer.visible),
    [layers]
  );
  const wmsLayer = useMemo(() => 
    wmsLayerData ? parseWMSUrl(wmsLayerData.data_link) : null,
    [wmsLayerData]
  );

  // Get all visible layers that can show legends (WMS, WMTS, and WCS)
  const visibleLayersWithLegends = useMemo(() =>
    layers.filter(
      (layer) =>
        layer.visible &&
        (layer.layer_type?.toUpperCase() === "WMS" ||
          layer.layer_type?.toUpperCase() === "WMTS" ||
          layer.layer_type?.toUpperCase() === "WCS"),
    ),
    [layers]
  );

  // Memoize legend components to prevent unnecessary re-renders
  const legendComponents = useMemo(() => {
    return visibleLayersWithLegends
      .map((layer) => {
        if (layer.layer_type?.toUpperCase() === "WMS") {
          const wmsLayerParsed = parseWMSUrl(layer.data_link);
          return (
            <Legend
              key={`wms-${layer.id}`}
              wmsLayer={wmsLayerParsed}
              title={layer.title || layer.name}
            />
          );
        } else if (layer.layer_type?.toUpperCase() === "WCS") {
          const wcsParsed = parseWCSUrl(layer.data_link);
          return (
            <Legend
              key={`wcs-${layer.id}`}
              wmsLayer={{
                baseUrl: wcsParsed.baseUrl,
                layers: wcsParsed.layers,
                format: wcsParsed.format,
                transparent: wcsParsed.transparent,
              }}
              title={layer.title || layer.name}
            />
          );
        } else if (layer.layer_type?.toUpperCase() === "WMTS") {
          const wmtsLayerParsed = parseWMTSUrl(layer.data_link);
          // Determine acceptable matrix sets before adding legend
          const propMatrixSets = (layer as any).properties?.tile_matrix_sets as
            | string[]
            | undefined;
          const candidateSetsRaw =
            propMatrixSets && propMatrixSets.length
              ? propMatrixSets
              : ["EPSG:3857", "GoogleMapsCompatible", "WebMercatorQuad"];
          const candidateSets = candidateSetsRaw.filter((s) =>
            isWebMercatorMatrixSet(s),
          );
          const chosen =
            pickWebMercatorMatrixSet(candidateSets) ||
            pickWebMercatorMatrixSet(candidateSetsRaw) ||
            candidateSetsRaw[0];
          if (!chosen || !isWebMercatorMatrixSet(chosen)) {
            Logger.warn(
              "Skipping WMTS legend (no WebMercator matrix set):",
              layer.id,
              candidateSetsRaw,
            );
            return null;
          }
          return (
            <Legend
              key={`wmts-${layer.id}`}
              wmtsLayer={wmtsLayerParsed}
              title={layer.title || layer.name}
            />
          );
        }
        return null;
      })
      .filter(Boolean);
  }, [visibleLayersWithLegends]);

  // Log cache statistics periodically for debugging
  useEffect(() => {
    const logCacheStats = () => {
      const stats = geoJSONCache.getCacheStats();
      Logger.log(
        `[GeoJSONCache] Stats - Entries: ${stats.entries}, Size: ${(stats.size / 1024 / 1024).toFixed(2)}MB / ${(stats.maxSize / 1024 / 1024).toFixed(2)}MB`
      );
    };

    // Log stats every 30 seconds
    const intervalId = setInterval(logCacheStats, 30000);
    
    return () => {
      clearInterval(intervalId);
    };
  }, []);

  return (
    <div className="relative w-full h-full">
      <div className="absolute inset-0 z-0">
        <MapContainer
          center={[0, 0]}
          zoom={2}
          style={{ height: "100%", width: "100%" }}
          preferCanvas={false}
        >
          {/* Ensure map tiles redraw after panel resize */}
          <InvalidateMapOnResize />
          <ZoomToSelected />
          <CustomScaleControl />
          <TileLayer url={basemap.url} attribution={basemap.attribution} />
          <div key={layerOrderKey}>
            {[...layers].map((layer) => {
              if (!layer.visible) return null;

              if (layer.layer_type?.toUpperCase() === "WMS") {
                // 💡 Automatically zoom to bounding boxes
                const {
                  baseUrl,
                  layers: wmsLayers,
                  format,
                  transparent,
                } = parseWMSUrl(layer.data_link);
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
              } else if (layer.layer_type?.toUpperCase() === "WCS") {
                const parsed = parseWCSUrl(layer.data_link);
                return (
                  <WMSTileLayer
                    key={layer.id}
                    url={parsed.baseUrl}
                    layers={parsed.layers}
                    format={parsed.format}
                    transparent={parsed.transparent}
                    zIndex={10}
                  />
                );
              } else if (layer.layer_type?.toUpperCase() === "WMTS") {
                const parsed = parseWMTSUrl(layer.data_link);
                // Prefer tile matrix sets from backend properties if present
                const propMatrixSets = (layer as any).properties
                  ?.tile_matrix_sets as string[] | undefined;
                const candidateSetsRaw =
                  propMatrixSets && propMatrixSets.length
                    ? propMatrixSets
                    : ["EPSG:3857", "GoogleMapsCompatible", "WebMercatorQuad"];
                const candidateSets = candidateSetsRaw.filter((s) =>
                  isWebMercatorMatrixSet(s),
                );
                const chosenSet =
                  pickWebMercatorMatrixSet(candidateSets) ||
                  pickWebMercatorMatrixSet(candidateSetsRaw) ||
                  candidateSetsRaw[0];
                if (!chosenSet || !isWebMercatorMatrixSet(chosenSet)) {
                  Logger.warn(
                    "Skipping WMTS layer without WebMercator matrix set (only EPSG:3857 supported currently):",
                    layer.id,
                    candidateSetsRaw,
                  );
                  return null; // do not render layer
                }
                const anyParsed: any = parsed as any;

                // Lightweight capability version probe (sync effect via stateful wrapper)
                // We'll build an initial template with parsed or default version (1.0.0), then attempt a silent fetch
                // of GetCapabilities to parse the ServiceIdentification->ServiceTypeVersion list for a newer version.
                const desiredBase = anyParsed.wmtsKvpBase || "";
                const initialVersion = anyParsed.version || "1.0.0";
                const [finalUrl, setFinalUrl] = (function () {
                  // local hook-like pattern not allowed here; fallback to simple memo-less runtime composition
                  return [
                    null as string | null,
                    (v: string) => {
                      /* noop in map render context */
                    },
                  ];
                })();
                // Since we cannot use hooks inside this map callback, we skip live probing here to avoid React rule violations.
                // If deeper negotiation is needed, refactor into a WMTSLayer React component with useEffect.
                const tileUrlTemplate = buildWMTSKvpTemplate(
                  desiredBase,
                  anyParsed.fullLayerName || anyParsed.layerName,
                  chosenSet,
                  "image/png",
                  initialVersion,
                );
                return (
                  <TileLayer
                    key={layer.id}
                    url={tileUrlTemplate}
                    attribution={layer.title}
                  />
                );
              } else if (
                layer.layer_type?.toUpperCase() === "WFS" ||
                layer.layer_type?.toUpperCase() === "UPLOADED" ||
                layer.data_link.toLowerCase().includes("json")
              ) {
                // Create a stable style hash for the key to force re-render when style changes
                const styleHash = layer.style
                  ? `${layer.style.stroke_color}-${layer.style.fill_color}-${layer.style.stroke_weight}-${layer.style.fill_opacity}-${layer.style.radius}-${layer.style.stroke_opacity}-${layer.style.stroke_dash_array}`
                  : "default";
                return (
                  <LeafletGeoJSONLayer
                    key={`${layer.id}-${styleHash}`}
                    url={layer.data_link}
                    layerStyle={layer.style}
                  />
                );
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
