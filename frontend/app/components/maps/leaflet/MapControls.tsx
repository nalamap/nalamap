"use client";

import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";

import { useUIStore } from "../../../stores/uiStore";
import Logger from "../../../utils/logger";

/**
 * When the map container element is resized (e.g., panels collapse/expand),
 * invalidate the Leaflet map size so tiles redraw correctly.
 */
export function InvalidateMapOnResize() {
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
export function CustomScaleControl() {
  const map = useMap();
  const layerPanelCollapsed = useUIStore((s) => s.layerPanelCollapsed);
  const scaleRef = useRef<L.Control.Scale | null>(null);

  // Create scale control once when component mounts
  useEffect(() => {
    const scale = L.control.scale({
      position: "bottomleft",
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
        scaleContainer.style.marginLeft = layerPanelCollapsed ? "90px" : "10px";
      }
    }
  }, [layerPanelCollapsed]);

  return null;
}
