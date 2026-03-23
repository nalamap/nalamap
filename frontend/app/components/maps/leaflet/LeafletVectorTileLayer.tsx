"use client";

import { useEffect } from "react";
import L from "leaflet";
import "leaflet.vectorgrid";
import { useMap } from "react-leaflet";

import { LayerStyle } from "../../../models/geodatamodel";
import Logger from "../../../utils/logger";
import {
  buildFeaturePropertiesPopupContent,
  FEATURE_PROPERTIES_POPUP_OPTIONS,
  getFeatureTooltipValue,
} from "./featurePropertiesPopup";

type LeafletVectorGridLayer = L.Layer & {
  setUrl?: (url: string, noRedraw?: boolean) => void;
};

type VectorTileFeatureEvent = L.LeafletMouseEvent & {
  layer?: {
    properties?: Record<string, unknown>;
  };
};

type LeafletDomEventWithFakeStop = typeof L.DomEvent & {
  fakeStop?: (event: Event | L.LeafletEvent) => typeof L.DomEvent;
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

const domEventWithFakeStop = L.DomEvent as LeafletDomEventWithFakeStop;

if (typeof domEventWithFakeStop.fakeStop !== "function") {
  domEventWithFakeStop.fakeStop = (event: Event | L.LeafletEvent) => {
    const originalEvent =
      event && "originalEvent" in event && event.originalEvent
        ? event.originalEvent
        : event;

    if (originalEvent && typeof originalEvent === "object") {
      (originalEvent as Event & { _stopped?: boolean })._stopped = true;
    }

    return L.DomEvent.stopPropagation(event as any);
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
    let clickPopup: L.Popup | null = null;
    let hoverTooltip: L.Tooltip | null = null;

    const closeHoverTooltip = () => {
      if (hoverTooltip) {
        map.removeLayer(hoverTooltip);
        hoverTooltip = null;
      }
    };

    const handlePopupClose = (event: L.PopupEvent) => {
      if (event.popup === clickPopup) {
        clickPopup = null;
      }
    };

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
        interactive: true,
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

      layer.on("click", (event: VectorTileFeatureEvent) => {
        const popupContent = buildFeaturePropertiesPopupContent(
          event.layer?.properties,
        );
        if (!popupContent) {
          return;
        }

        closeHoverTooltip();
        clickPopup = L.popup(FEATURE_PROPERTIES_POPUP_OPTIONS)
          .setLatLng(event.latlng)
          .setContent(popupContent);
        clickPopup.openOn(map);
      });

      layer.on("mouseover", (event: VectorTileFeatureEvent) => {
        map.getContainer().style.cursor = "pointer";

        const tooltipValue = getFeatureTooltipValue(event.layer?.properties);
        if (!tooltipValue || clickPopup?.isOpen()) {
          return;
        }

        closeHoverTooltip();
        hoverTooltip = L.tooltip({
          sticky: true,
          direction: "top",
          opacity: 0.9,
        })
          .setLatLng(event.latlng)
          .setContent(tooltipValue);
        hoverTooltip.addTo(map);
      });

      layer.on("mousemove", (event: VectorTileFeatureEvent) => {
        if (hoverTooltip && !clickPopup?.isOpen()) {
          hoverTooltip.setLatLng(event.latlng);
        }
      });

      layer.on("mouseout", () => {
        map.getContainer().style.cursor = "";
        closeHoverTooltip();
      });

      map.on("popupclose", handlePopupClose);

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
      map.off("popupclose", handlePopupClose);
      map.getContainer().style.cursor = "";
      closeHoverTooltip();
      if (clickPopup) {
        map.closePopup(clickPopup);
        clickPopup = null;
      }
      if (layer && map.hasLayer(layer)) {
        map.removeLayer(layer);
      }
    };
  }, [collectionId, layerStyle, map, urlTemplate]);

  return null;
}
