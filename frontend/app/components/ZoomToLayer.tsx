import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import { GeoDataObject } from "../models/geodatamodel";

function parseBoundingBoxWKT(wkt: string): L.LatLngBounds | null {
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

export function ZoomToLayer({ layers }: { layers: GeoDataObject[] }) {
  const map = useMap();
  const zoomedLayers = useRef<Set<string | number>>(new Set());

  useEffect(() => {
    layers.forEach(async (layer) => {
      if (!layer.visible || zoomedLayers.current.has(layer.id)) return;

      if (layer.layer_type?.toUpperCase() === "WMS") {
        if (layer.bounding_box) {
          const bounds = parseBoundingBoxWKT(layer.bounding_box);
          if (bounds) {
            map.fitBounds(bounds);
            zoomedLayers.current.add(layer.id);
          }
          zoomedLayers.current.add(layer.id);
        }
      }
    }
    );
  }, [layers, map]);

  return null;
}
