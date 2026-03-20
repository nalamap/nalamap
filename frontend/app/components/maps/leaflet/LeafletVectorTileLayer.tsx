"use client";

import { useEffect } from "react";
import L from "leaflet";
import "leaflet.vectorgrid";
import { useMap } from "react-leaflet";

import { LayerStyle } from "../../../models/geodatamodel";
import Logger from "../../../utils/logger";

type LeafletVectorGridLayer = L.Layer & {
  setUrl?: (url: string, noRedraw?: boolean) => void;
};

type LeafletWithVectorGrid = typeof L & {
  vectorGrid?: {
    protobuf: (
      urlTemplate: string,
      options?: Record<string, any>,
    ) => LeafletVectorGridLayer;
  };
  canvas: typeof L.canvas & {
    tile?: (coords: L.Coords, tileSize: L.Point, options?: any) => any;
  };
};

function toVectorTileStyle(layerStyle?: LayerStyle) {
  return {
    color: layerStyle?.stroke_color || "#3388ff",
    weight: layerStyle?.stroke_weight || 2,
    opacity: layerStyle?.stroke_opacity ?? 1,
    dashArray: layerStyle?.stroke_dash_array,
    dashOffset:
      layerStyle?.stroke_dash_offset !== undefined
        ? String(layerStyle.stroke_dash_offset)
        : undefined,
    lineCap:
      layerStyle?.line_cap === "square" || layerStyle?.line_cap === "butt"
        ? layerStyle.line_cap
        : "round",
    lineJoin:
      layerStyle?.line_join === "bevel" || layerStyle?.line_join === "miter"
        ? layerStyle.line_join
        : "round",
    fill: true,
    fillColor: layerStyle?.fill_color || layerStyle?.stroke_color || "#3388ff",
    fillOpacity: layerStyle?.fill_opacity ?? 0.3,
    radius: layerStyle?.radius || 6,
  };
}

export function LeafletVectorTileLayer({
  urlTemplate,
  collectionId,
  layerStyle,
}: {
  urlTemplate: string;
  collectionId: string;
  layerStyle?: LayerStyle;
}) {
  const map = useMap();

  useEffect(() => {
    let cancelled = false;
    let layer: LeafletVectorGridLayer | null = null;

    try {
      const vectorGridLeaflet = L as LeafletWithVectorGrid;
      const createVectorGrid = vectorGridLeaflet.vectorGrid?.protobuf;
      const rendererFactory = vectorGridLeaflet.canvas?.tile;

      if (!createVectorGrid || !rendererFactory) {
        throw new Error(
          "leaflet.vectorgrid did not register protobuf/canvas factories on Leaflet",
        );
      }

      const vectorTileStyle = toVectorTileStyle(layerStyle);
      layer = createVectorGrid(urlTemplate, {
        pane: "overlayPane",
        updateWhenIdle: false,
        updateWhenZooming: true,
        keepBuffer: 2,
        opacity: 1,
        zIndex: 450,
        rendererFactory,
        fetchOptions: {
          credentials: "include",
        },
        vectorTileLayerStyles: {
          [collectionId]: vectorTileStyle,
          "*": vectorTileStyle,
        },
      });

      if (!cancelled) {
        layer.addTo(map);
      }
    } catch (error) {
      Logger.error(
        `[LeafletVectorTileLayer] Failed to initialize vector tiles for ${collectionId}:`,
        error,
      );
    }

    return () => {
      cancelled = true;
      if (layer && map.hasLayer(layer)) {
        map.removeLayer(layer);
      }
    };
  }, [collectionId, layerStyle, map, urlTemplate]);

  return null;
}
