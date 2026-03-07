"use client";

import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, WMSTileLayer } from "react-leaflet";

// Fix leaflet's default icon path issue
import "leaflet/dist/leaflet.css";

import { useMapStore } from "../../stores/mapStore";
import { useLayerStore } from "../../stores/layerStore";
import { ZoomToSelected } from "./ZoomToLayer";
import Logger from "../../utils/logger";

import { LeafletGeoJSONLayer } from "./leaflet/LeafletGeoJSONLayer";
import { Legend } from "./leaflet/Legend";
import { geoJSONCache } from "./leaflet/geojsonCache";
import { isGeoJsonLikeLayer } from "./leaflet/layerDetection";
import {
  buildWMTSKvpTemplate,
  isWebMercatorMatrixSet,
  parseWCSUrl,
  parseWMSUrl,
  parseWMTSUrl,
  pickWebMercatorMatrixSet,
} from "./leaflet/layerParsers";
import { CustomScaleControl, InvalidateMapOnResize } from "./leaflet/MapControls";

export default function LeafletMapComponent() {
  const basemap = useMapStore((state) => state.basemap);
  const layers = useLayerStore((state) => state.layers);

  // Memoize visible layers to avoid recalculating on every render
  const visibleLayers = useMemo(
    () => layers.filter((l) => l.visible),
    [layers],
  );

  // Use a stable key derived from the VISIBLE layer order so React knows when to recreate
  // the layer list. This ensures proper cleanup and reinitialization of layers
  // when their order changes. Only include visible layers since those are the only ones rendered.
  const layerOrderKey = useMemo(
    () => visibleLayers.map((l) => l.id).join("-"),
    [visibleLayers],
  );

  // Get all visible layers that can show legends (WMS, WMTS, and WCS)
  const visibleLayersWithLegends = useMemo(
    () =>
      layers.filter(
        (layer) =>
          layer.visible &&
          (layer.layer_type?.toUpperCase() === "WMS" ||
            layer.layer_type?.toUpperCase() === "WMTS" ||
            layer.layer_type?.toUpperCase() === "WCS"),
      ),
    [layers],
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
        }

        if (layer.layer_type?.toUpperCase() === "WCS") {
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
        }

        if (layer.layer_type?.toUpperCase() === "WMTS") {
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
        `[GeoJSONCache] Stats - Entries: ${stats.entries}, Size: ${(stats.size / 1024 / 1024).toFixed(2)}MB / ${(stats.maxSize / 1024 / 1024).toFixed(2)}MB`,
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
                const { baseUrl, layers: wmsLayers, format, transparent } = parseWMSUrl(
                  layer.data_link,
                );
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

              if (layer.layer_type?.toUpperCase() === "WCS") {
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
              }

              if (layer.layer_type?.toUpperCase() === "WMTS") {
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

                const tileUrlTemplate = buildWMTSKvpTemplate(
                  parsed.wmtsKvpBase || "",
                  parsed.fullLayerName || parsed.layerName,
                  chosenSet,
                  "image/png",
                  parsed.version || "1.0.0",
                );
                return (
                  <TileLayer
                    key={layer.id}
                    url={tileUrlTemplate}
                    attribution={layer.title}
                  />
                );
              }

              if (isGeoJsonLikeLayer(layer)) {
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
