import { GeoDataObject } from "../../../models/geodatamodel";
import { shouldRenderLayerAsVectorTiles } from "../../../utils/ogcVectorTiles";

export function isGeoJsonLikeLayer(layer: GeoDataObject): boolean {
  if (shouldRenderLayerAsVectorTiles(layer)) {
    return false;
  }

  const layerType = (layer.layer_type || "").toUpperCase();
  const dataType = (layer.data_type || "").toUpperCase();
  const link = (layer.data_link || "").toLowerCase();

  if (layerType === "WFS" || layerType === "UPLOADED" || layerType === "GEOJSON") {
    return true;
  }
  if (dataType === "GEOJSON" || dataType === "GEOJSONLAYER") {
    return true;
  }
  if (link.includes("json")) {
    return true;
  }
  if (/\/processes\/[^/]+\/jobs\/[^/]+\/results(?:[/?#]|$)/i.test(link)) {
    return true;
  }
  return false;
}
