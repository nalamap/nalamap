import { GeoDataObject } from "../models/geodatamodel";

export type OGCVectorRenderMode = "auto" | "items" | "tiles";

const FALLBACK_TILE_FEATURE_THRESHOLD = 5000;

function getLayerProperties(layer: GeoDataObject): Record<string, any> {
  return layer.properties && typeof layer.properties === "object"
    ? layer.properties
    : {};
}

function normalizeRenderMode(value: unknown): OGCVectorRenderMode {
  if (value === "items" || value === "tiles" || value === "auto") {
    return value;
  }
  return "auto";
}

function extractCollectionIdFromUrl(candidate: unknown): string | null {
  if (typeof candidate !== "string" || !candidate.trim()) {
    return null;
  }

  const match = candidate
    .trim()
    .match(/\/collections\/([^/?#]+)\/(?:items|tiles)(?:[/?#].*)?$/i);
  if (!match?.[1]) {
    return null;
  }

  try {
    const decoded = decodeURIComponent(match[1]).trim();
    return decoded || null;
  } catch {
    return match[1].trim() || null;
  }
}

function isCollectionItemsUrl(candidate: unknown): boolean {
  return (
    typeof candidate === "string" &&
    /\/collections\/[^/?#]+\/items(?:[/?#]|$)/i.test(candidate.trim())
  );
}

export function getOgcCollectionId(layer: GeoDataObject): string | null {
  const properties = getLayerProperties(layer);
  const collectionId = properties.ogc_collection_id || properties.collection_id;
  if (typeof collectionId === "string" && collectionId.trim()) {
    return collectionId.trim();
  }

  return (
    extractCollectionIdFromUrl(properties.ogc_items_url) ||
    extractCollectionIdFromUrl(properties.ogc_tiles_url) ||
    extractCollectionIdFromUrl(properties.ogc_tiles_metadata_url) ||
    extractCollectionIdFromUrl(layer.data_link)
  );
}

export function getLayerFeatureUrl(layer: GeoDataObject): string {
  const properties = getLayerProperties(layer);
  if (
    typeof properties.ogc_items_url === "string" &&
    properties.ogc_items_url.trim()
  ) {
    return properties.ogc_items_url.trim();
  }
  return layer.data_link;
}

function deriveCollectionBaseUrl(itemsUrl: string): string | null {
  const match = itemsUrl.match(/^(.*)\/collections\/[^/]+\/items(?:[/?#].*)?$/i);
  if (!match?.[1]) {
    return null;
  }
  return match[1].replace(/\/$/, "");
}

function hasOwnProperty(object: Record<string, any>, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(object, key);
}

export function getOgcTilesMetadataUrl(layer: GeoDataObject): string | null {
  const properties = getLayerProperties(layer);
  if (
    typeof properties.ogc_tiles_metadata_url === "string" &&
    properties.ogc_tiles_metadata_url.trim()
  ) {
    return properties.ogc_tiles_metadata_url.trim();
  }

  const collectionId = getOgcCollectionId(layer);
  const baseUrl = deriveCollectionBaseUrl(getLayerFeatureUrl(layer));
  if (!collectionId || !baseUrl) {
    return null;
  }

  return `${baseUrl}/collections/${encodeURIComponent(collectionId)}/tiles`;
}

export function getOgcVectorTileUrlTemplate(
  layer: GeoDataObject,
): string | null {
  const properties = getLayerProperties(layer);
  if (
    typeof properties.ogc_tiles_url === "string" &&
    properties.ogc_tiles_url.trim()
  ) {
    return properties.ogc_tiles_url.trim();
  }

  const collectionId = getOgcCollectionId(layer);
  const baseUrl = deriveCollectionBaseUrl(getLayerFeatureUrl(layer));
  if (!collectionId || !baseUrl) {
    return null;
  }

  return `${baseUrl}/collections/${encodeURIComponent(collectionId)}/tiles/{z}/{x}/{y}.mvt`;
}

export function deriveOgcLayerProperties(
  layer: GeoDataObject,
): Record<string, any> {
  const properties = getLayerProperties(layer);
  const collectionId = getOgcCollectionId(layer);
  if (!collectionId) {
    return {};
  }

  const derived: Record<string, any> = {
    ogc_collection_id: collectionId,
  };
  const featureUrl = getLayerFeatureUrl(layer);
  if (isCollectionItemsUrl(featureUrl)) {
    derived.ogc_items_url = featureUrl;
  }

  const tilesUrl = getOgcVectorTileUrlTemplate(layer);
  if (tilesUrl) {
    derived.ogc_tiles_url = tilesUrl;
  }

  const tilesMetadataUrl = getOgcTilesMetadataUrl(layer);
  if (tilesMetadataUrl) {
    derived.ogc_tiles_metadata_url = tilesMetadataUrl;
  }

  if (
    !hasOwnProperty(properties, "ogc_render_mode") &&
    !hasOwnProperty(properties, "render_mode")
  ) {
    derived.ogc_render_mode = "auto";
  }

  return derived;
}

export function hydrateOgcLayer(layer: GeoDataObject): GeoDataObject {
  const properties = getLayerProperties(layer);
  const derived = deriveOgcLayerProperties(layer);

  if (Object.keys(derived).length === 0) {
    return layer;
  }

  return {
    ...layer,
    properties: {
      ...derived,
      ...properties,
    },
  };
}

export function supportsOgcVectorTiles(layer: GeoDataObject): boolean {
  return Boolean(getOgcCollectionId(layer) && getOgcVectorTileUrlTemplate(layer));
}

export function getConfiguredOgcRenderMode(
  layer: GeoDataObject,
): OGCVectorRenderMode {
  const properties = getLayerProperties(layer);
  return normalizeRenderMode(
    properties.ogc_render_mode || properties.render_mode,
  );
}

export function getRecommendedOgcRenderMode(
  layer: GeoDataObject,
): Exclude<OGCVectorRenderMode, "auto"> {
  if (!supportsOgcVectorTiles(layer)) {
    return "items";
  }

  const properties = getLayerProperties(layer);
  const explicitMode = normalizeRenderMode(properties.ogc_recommended_render_mode);
  if (explicitMode !== "auto") {
    return explicitMode;
  }

  const rawFeatureCount = properties.ogc_feature_count;
  const numericFeatureCount =
    typeof rawFeatureCount === "number"
      ? rawFeatureCount
      : typeof rawFeatureCount === "string"
        ? Number(rawFeatureCount)
        : NaN;

  if (
    Number.isFinite(numericFeatureCount) &&
    numericFeatureCount >= FALLBACK_TILE_FEATURE_THRESHOLD
  ) {
    return "tiles";
  }

  return "items";
}

export function getEffectiveOgcRenderMode(
  layer: GeoDataObject,
): Exclude<OGCVectorRenderMode, "auto"> {
  const configuredMode = getConfiguredOgcRenderMode(layer);
  if (configuredMode === "items") {
    return "items";
  }
  if (configuredMode === "tiles") {
    return supportsOgcVectorTiles(layer) ? "tiles" : "items";
  }
  return getRecommendedOgcRenderMode(layer);
}

export function shouldRenderLayerAsVectorTiles(
  layer: GeoDataObject,
): boolean {
  return (
    supportsOgcVectorTiles(layer) && getEffectiveOgcRenderMode(layer) === "tiles"
  );
}
