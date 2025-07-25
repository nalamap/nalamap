"use client";
import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import { GeoDataObject } from "../../models/geodatamodel";
import { useLayerStore } from "../../stores/layerStore";

function parseBoundingBoxWKT(wkt: string): L.LatLngBounds | null {
  if (!wkt) return null;
  
  console.log("Parsing WKT bbox:", wkt);
  
  const match = wkt.match(/POLYGON\(\((.+?)\)\)/);
  if (!match) return null;

  const coords = match[1]
    .split(",")
    .map(pair => pair.trim().split(" ").map(Number))
    .filter(([lng, lat]) => !isNaN(lng) && !isNaN(lat));

  if (coords.length === 0) return null;

  const lats = coords.map(([lng, lat]) => lat);
  const lngs = coords.map(([lng, lat]) => lng);

  const southWest = L.latLng(Math.min(...lats), Math.min(...lngs));
  const northEast = L.latLng(Math.max(...lats), Math.max(...lngs));

  return L.latLngBounds(southWest, northEast);
}

// Handle array format bounding box [minX, minY, maxX, maxY]
function parseBoundingBoxArray(bbox: any): L.LatLngBounds | null {
  if (!Array.isArray(bbox) || bbox.length < 4) return null;
  
  console.log("Parsing Array bbox:", bbox);
  
  try {
    // Handle both [minX, minY, maxX, maxY] format
    if (bbox.length === 4) {
      const [minX, minY, maxX, maxY] = bbox;
      const southWest = L.latLng(minY, minX);
      const northEast = L.latLng(maxY, maxX);
      return L.latLngBounds(southWest, northEast);
    }
    return null;
  } catch (err) {
    console.error("Error parsing bounding box array:", err);
    return null;
  }
}

export function ZoomToLayer({ layers }: { layers: GeoDataObject[] }) {
  const map = useMap();
  const zoomedLayers = useRef<Set<string | number>>(new Set());

  useEffect(() => {
    layers.forEach(async (layer) => {
      if (!layer.visible || zoomedLayers.current.has(layer.id)) return;

      if (layer.layer_type?.toUpperCase() === "WMS") {
        if (layer.bounding_box) {
          if (typeof layer.bounding_box === 'string') {
            const bounds = parseBoundingBoxWKT(layer.bounding_box);
            if (bounds) {
              map.fitBounds(bounds);
              zoomedLayers.current.add(layer.id);
            }
          }
          zoomedLayers.current.add(layer.id);
        }
      }
    });
  }, [layers, map]);

  return null;
}

export function ZoomToSelected() {
  const map = useMap();
  const zoomTo = useLayerStore((s) => s.zoomTo);
  const layers = useLayerStore((s) => s.layers);
  const setZoomTo = useLayerStore((s) => s.setZoomTo);

  useEffect(() => {
    if (zoomTo == null) return;
    console.log("Zooming to layer ID:", zoomTo);
    
    const layer = layers.find((l) => l.id === zoomTo);
    if (!layer) {
      console.warn("Layer not found with ID:", zoomTo);
      setZoomTo(null);
      return;
    }
    
    console.log("Found layer:", layer.name, "with bounding box:", layer.bounding_box);
    
    if (layer.bounding_box) {
      let bounds = null;
      
      // Try parsing as WKT POLYGON format
      if (typeof layer.bounding_box === 'string' && layer.bounding_box.includes('POLYGON')) {
        bounds = parseBoundingBoxWKT(layer.bounding_box);
      } 
      // Try parsing as array format [minX, minY, maxX, maxY]
      else if (Array.isArray(layer.bounding_box)) {
        bounds = parseBoundingBoxArray(layer.bounding_box);
      }
      
      if (bounds) {
        console.log("Zooming to bounds:", bounds.toString());
        map.fitBounds(bounds);
      } else {
        console.warn("Could not parse bounding box:", layer.bounding_box);
      }
    } else if (layer.layer_type?.toUpperCase() === "WFS" || 
              layer.layer_type?.toUpperCase() === "UPLOADED" ||
              layer.data_link.toLowerCase().includes("json")) {
      // For GeoJSON layers, fetch the data to get the bounds
      console.log("Attempting to fetch GeoJSON data to get bounds");
      fetch(layer.data_link)
        .then(res => res.json())
        .then(data => {
          try {
            const geoJsonLayer = L.geoJSON(data);
            const bounds = geoJsonLayer.getBounds();
            // Check if bounds are valid (not empty/invalid)
            if (bounds && bounds.isValid && bounds.isValid()) {
              console.log("Got bounds from GeoJSON:", bounds.toString());
              map.fitBounds(bounds);
            } else {
              console.warn("GeoJSON layer has no valid bounds (likely empty):", layer.name);
            }
          } catch (err) {
            console.error("Error creating bounds from GeoJSON:", err);
          }
        })
        .catch(err => {
          console.error("Error fetching GeoJSON data:", err);
        });
    } else {
      console.warn("No bounding box information available for layer:", layer.name);
    }
    
    setZoomTo(null);
  }, [zoomTo, layers, map, setZoomTo]);

  return null;
}
