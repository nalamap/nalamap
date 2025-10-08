/**
 * Custom React Hook for fetching and processing GeoJSON layer data
 *
 * Handles:
 * - Fetching GeoJSON from URLs
 * - Normalizing various GeoJSON formats
 * - Auto-detecting and reprojecting coordinate systems
 * - WFS parameter handling
 * - Loading states and error handling
 */

import { useState, useEffect } from "react";
import Logger from "../utils/logger";
import { GeoJSONNormalizer } from "../utils/geojson-normalizer";
import { CoordinateProjection } from "../utils/coordinate-projection";

export interface UseLayerDataOptions {
  url: string;
  preferEPSG4326?: boolean; // For WFS, prefer EPSG:4326 if no srsName specified
}

export interface UseLayerDataResult {
  data: any | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useLayerData({
  url,
  preferEPSG4326 = true,
}: UseLayerDataOptions): UseLayerDataResult {
  const [data, setData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [refetchTrigger, setRefetchTrigger] = useState(0);

  const refetch = () => setRefetchTrigger((prev) => prev + 1);

  useEffect(() => {
    let cancelled = false;
    let timeoutId: NodeJS.Timeout | null = null;

    const fetchAndProcess = async () => {
      setIsLoading(true);
      setError(null);
      setData(null);

      try {
        // Prepare request URL (add EPSG:4326 for WFS if needed)
        let requestUrl = url;
        if (preferEPSG4326) {
          try {
            const urlObj = new URL(url);
            const isWFS =
              /wfs/i.test(urlObj.search) ||
              urlObj.searchParams.get("service")?.toUpperCase() === "WFS";
            const hasSrsName = urlObj.searchParams.has("srsName");

            if (isWFS && !hasSrsName) {
              urlObj.searchParams.set("srsName", "EPSG:4326");
              requestUrl = urlObj.toString();
            }
          } catch (e) {
            // Invalid URL, use as-is
          }
        }

        // Fetch data
        let response = await fetch(requestUrl, {
          headers: {
            Accept: "application/json, application/geo+json, */*;q=0.1",
          },
        });

        // Fallback to original URL if modified URL failed
        if (!response.ok && requestUrl !== url) {
          response = await fetch(url, {
            headers: {
              Accept: "application/json, application/geo+json, */*;q=0.1",
            },
          });
        }

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        // Parse response
        const contentType = response.headers.get("content-type") || "";
        let json: any;

        if (
          contentType.includes("application/json") ||
          contentType.includes("geo+json")
        ) {
          json = await response.json();
        } else {
          // Try to parse as JSON anyway
          const text = await response.text();
          try {
            json = JSON.parse(text);
          } catch (parseError) {
            throw new Error(
              `Response is not valid JSON: ${text.slice(0, 200)}`,
            );
          }
        }

        if (cancelled) return;

        // Normalize to FeatureCollection
        let normalized = GeoJSONNormalizer.normalize(json);

        if (!normalized) {
          throw new Error("Could not normalize GeoJSON data");
        }

        // Extract declared CRS
        const declaredCrs =
          GeoJSONNormalizer.extractCRS(json) ||
          GeoJSONNormalizer.extractCRS(normalized) ||
          undefined;

        // Auto-detect and reproject if needed
        normalized = CoordinateProjection.autoReproject(
          normalized,
          declaredCrs,
        );

        // Final validation
        if (!GeoJSONNormalizer.validateLatLonCoordinates(normalized)) {
          Logger.warn(
            "Coordinates validation failed, attempting fallback fetch",
          );

          // Fallback: refetch original without modifications
          timeoutId = setTimeout(() => {
            fetch(url)
              .then((res) => res.json())
              .then((originalJson) => {
                const fallbackNormalized =
                  GeoJSONNormalizer.normalize(originalJson);
                if (fallbackNormalized) {
                  setData(fallbackNormalized);
                  setIsLoading(false);
                }
              })
              .catch(() => {
                setError(new Error("Fallback fetch failed"));
                setIsLoading(false);
              });
          }, 0);
          return;
        }

        setData(normalized);
      } catch (err) {
        if (!cancelled) {
          Logger.error("Error fetching layer data:", err);
          setError(err instanceof Error ? err : new Error(String(err)));
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    fetchAndProcess();

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
      setIsLoading(false);
    };
  }, [url, preferEPSG4326, refetchTrigger]);

  return { data, isLoading, error, refetch };
}
