"use client";

import { memo, useCallback, useEffect, useMemo, useState } from "react";
import { GeoJSON, useMap } from "react-leaflet";
import L from "leaflet";

import { LayerStyle } from "../../../models/geodatamodel";
import Logger from "../../../utils/logger";
import { geoJSONCache } from "./geojsonCache";
import { fetchWithCorsProxy } from "./proxy";

const JSON_ACCEPT_HEADER = "application/json, application/geo+json, */*;q=0.1";
const OGC_ITEMS_PAGE_LIMIT = 1000;
const OGC_ITEMS_MAX_PAGES = 250;

// Memoized component to prevent unnecessary re-renders
export const LeafletGeoJSONLayer = memo(function LeafletGeoJSONLayer({
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

    const parseJsonResponse = async (
      requestUrl: string,
      response: Response,
    ): Promise<any> => {
      if (!response.ok) {
        throw new Error(`Request failed (${response.status}) for ${requestUrl}`);
      }

      const contentType = response.headers.get("content-type") || "";
      const contentLengthHeader = response.headers.get("content-length");
      if (
        contentType.includes("application/json") ||
        contentType.includes("geo+json")
      ) {
        return response.json();
      }

      const text = await response.text();
      const expectedBytes = contentLengthHeader
        ? parseInt(contentLengthHeader, 10)
        : null;
      const receivedBytes =
        typeof TextEncoder !== "undefined"
          ? new TextEncoder().encode(text).length
          : text.length;

      try {
        return JSON.parse(text);
      } catch (error) {
        Logger.warn("Non-JSON WFS response, cannot render", {
          url: requestUrl,
          snippet: text.slice(0, 200),
          expectedBytes,
          receivedBytes,
        });
        if (expectedBytes !== null && receivedBytes < expectedBytes) {
          throw new Error(
            `GeoJSON response truncated (${receivedBytes}/${expectedBytes} bytes)`,
          );
        }
        throw error;
      }
    };

    const fetchJsonPayload = async (
      primaryUrl: string,
      fallbackUrl?: string,
    ): Promise<any> => {
      let response = await fetchWithCorsProxy(primaryUrl, {
        headers: { Accept: JSON_ACCEPT_HEADER },
      });

      if (!response.ok && fallbackUrl && fallbackUrl !== primaryUrl) {
        response = await fetchWithCorsProxy(fallbackUrl, {
          headers: { Accept: JSON_ACCEPT_HEADER },
        });
      }

      return parseJsonResponse(response.url || primaryUrl, response);
    };

    const isOgcItemsUrl = (candidate: string): boolean =>
      /\/collections\/[^/?#]+\/items(?:[/?#]|$)/i.test(candidate);

    const withOgcItemsPageLimit = (candidate: string): string => {
      try {
        const parsed = new URL(candidate);
        if (!parsed.searchParams.has("limit")) {
          parsed.searchParams.set("limit", String(OGC_ITEMS_PAGE_LIMIT));
        }
        return parsed.toString();
      } catch {
        return candidate;
      }
    };

    const resolveNextOgcItemsUrl = (
      currentUrl: string,
      payload: any,
    ): string | null => {
      const nextLink = Array.isArray(payload?.links)
        ? payload.links.find((link: any) => {
            const rel =
              typeof link?.rel === "string" ? link.rel.toLowerCase() : "";
            return rel === "next" || rel.endsWith("/next");
          })
        : null;

      if (typeof nextLink?.href !== "string" || !nextLink.href.trim()) {
        return null;
      }

      try {
        return new URL(nextLink.href, currentUrl).toString();
      } catch {
        return nextLink.href.trim();
      }
    };

    const fetchOgcItemsFeatureCollection = async (
      itemsUrl: string,
    ): Promise<any> => {
      const seenUrls = new Set<string>();
      const mergedFeatures: any[] = [];
      let mergedBbox: any;
      let mergedCrs: any;
      let nextUrl: string | null = withOgcItemsPageLimit(itemsUrl);

      for (let pageIndex = 0; nextUrl && pageIndex < OGC_ITEMS_MAX_PAGES; pageIndex += 1) {
        if (seenUrls.has(nextUrl)) {
          Logger.warn("[LeafletGeoJSONLayer] Stopping OGC items pagination loop", {
            url: nextUrl,
          });
          break;
        }
        seenUrls.add(nextUrl);

        const pagePayload = await fetchJsonPayload(nextUrl);
        const pageCollection = normalizeToFeatureCollection(pagePayload);
        if (!pageCollection) {
          return pagePayload;
        }

        if (!mergedBbox && pageCollection.bbox) {
          mergedBbox = pageCollection.bbox;
        }
        if (!mergedCrs && pageCollection.crs) {
          mergedCrs = pageCollection.crs;
        }
        if (Array.isArray(pageCollection.features)) {
          mergedFeatures.push(...pageCollection.features);
        }

        const candidateNextUrl = resolveNextOgcItemsUrl(nextUrl, pagePayload);
        nextUrl = candidateNextUrl ? withOgcItemsPageLimit(candidateNextUrl) : null;
      }

      const mergedCollection: any = {
        type: "FeatureCollection",
        features: mergedFeatures,
      };
      if (mergedBbox) {
        mergedCollection.bbox = mergedBbox;
      }
      if (mergedCrs) {
        mergedCollection.crs = mergedCrs;
      }
      return mergedCollection;
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

        const json = isOgcItemsUrl(url)
          ? await fetchOgcItemsFeatureCollection(url)
          : await fetchJsonPayload(requestUrl, url);

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
    // Only change the border (stroke) properties to keep the feature transparent
    layer.on({
      mouseover: (e) => {
        if ("setStyle" in e.target) {
          e.target.setStyle({
            weight: 4,           // Increase border width
            color: "#FF6B35",    // Use a vibrant highlight color
            opacity: 1.0,        // Full opacity for the border
            // fillOpacity unchanged - keeps the fill transparent so user can see through
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
