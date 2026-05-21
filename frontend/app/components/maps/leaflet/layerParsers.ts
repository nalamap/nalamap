import Logger from "../../../utils/logger";
import {
  ParsedWcsLayer,
  ParsedWmsLayer,
  ParsedWmtsLayer,
} from "./types";

// Helper: Parse a full WMS access_url into its base URL and WMS parameters.
export function parseWMSUrl(access_url: string): ParsedWmsLayer {
  try {
    const urlObj = new URL(access_url);
    const baseUrl = `${urlObj.origin}${urlObj.pathname}`;
    const params = urlObj.searchParams;
    return {
      baseUrl,
      layers: params.get("layers") || "",
      format: params.get("format") || "image/png",
      transparent: params.get("transparent")
        ? params.get("transparent") === "true"
        : true,
    };
  } catch (err) {
    Logger.error("Error parsing WMS URL:", err);
    return {
      baseUrl: access_url,
      layers: "",
      format: "image/png",
      transparent: true,
    };
  }
}

// Function to parse WMTS URLs and extract layer information for legend generation
export function parseWMTSUrl(access_url: string): ParsedWmtsLayer {
  try {
    const urlObj = new URL(access_url);

    // Extract all parameters from the original WMTS URL
    const originalParams = urlObj.searchParams;

    // Detect version if provided (common param names: version / VERSION)
    const versionParam =
      originalParams.get("version") || originalParams.get("VERSION") || "";
    const version = versionParam; // may be empty; we'll fallback later

    // Get layer name from parameters
    let layerName = originalParams.get("layer") || originalParams.get("LAYER");

    // If no layer parameter, try to extract from REST-style path
    if (!layerName) {
      const pathParts = urlObj.pathname.split("/");
      const restIndex = pathParts.indexOf("rest");
      if (restIndex !== -1 && restIndex + 1 < pathParts.length) {
        layerName = pathParts[restIndex + 1];
      }
    }
    // Extra heuristic: scan any path segment containing a ':' (workspace:layer)
    if (!layerName) {
      const colonSegment = urlObj.pathname.split("/").find((p) => p.includes(":"));
      if (colonSegment) layerName = colonSegment;
    }
    // Remove potential style or tile matrix set segments erroneously picked up
    if (
      layerName &&
      (layerName.toLowerCase() === "default" || layerName.includes("{"))
    ) {
      layerName = "";
    }

    if (!layerName) {
      Logger.warn("Could not extract layer name from WMTS URL:", access_url);
      return {
        wmtsLegendUrl: "",
        wmsLegendUrl: "",
        layerName: "",
        originalUrl: access_url,
        version: version || undefined,
      };
    }

    // Extract workspace and final layer name if in format "workspace:layer"
    let workspace = "";
    let finalLayerName = layerName;
    if (layerName.includes(":")) {
      [workspace, finalLayerName] = layerName.split(":");
    }

    // Derive GeoServer base (up to /geoserver)
    const pathParts = urlObj.pathname.split("/").filter(Boolean);
    const geoserverIdx = pathParts.indexOf("geoserver");
    const geoserverBase =
      geoserverIdx !== -1
        ? `${urlObj.origin}/${pathParts.slice(0, geoserverIdx + 1).join("/")}`
        : `${urlObj.origin}`;
    // Standard WMTS KVP endpoint
    const wmtsKvpBase = `${geoserverBase}/gwc/service/wmts`;
    // Build WMS legend base for same layer
    const wmsBaseUrl = `${geoserverBase}/wms`;
    const wmsLegendParams = new URLSearchParams({
      service: "WMS",
      version: "1.1.0",
      request: "GetLegendGraphic",
      format: "image/png",
      layer: layerName,
    });
    const wmsLegendUrl = `${wmsBaseUrl}?${wmsLegendParams.toString()}`;

    const result: ParsedWmtsLayer = {
      wmtsLegendUrl: "", // not using non-standard WMTS legend
      wmsLegendUrl,
      layerName: finalLayerName,
      workspace,
      fullLayerName: workspace
        ? `${workspace}:${finalLayerName}`
        : finalLayerName,
      originalUrl: access_url,
      wmtsKvpBase,
      version: version || undefined,
    };

    Logger.log("WMTS URL parsing result:", {
      originalUrl: access_url,
      parsed: result,
    });

    return result;
  } catch (err) {
    Logger.error("Error parsing WMTS URL:", err);
    return {
      wmtsLegendUrl: "",
      wmsLegendUrl: "",
      layerName: "",
      originalUrl: access_url,
    };
  }
}

// Build a WMTS KVP tile URL template mapping Leaflet z/x/y to WMTS parameters
export function buildWMTSKvpTemplate(
  base: string,
  fullLayerName: string,
  tileMatrixSet: string,
  format: string = "image/png",
  version: string = "1.0.0",
) {
  // GeoServer expects tilematrix like EPSG:3857:Z
  return `${base}?service=WMTS&version=${encodeURIComponent(version)}&request=GetTile&layer=${encodeURIComponent(fullLayerName)}&style=&tilematrixset=${encodeURIComponent(tileMatrixSet)}&format=${encodeURIComponent(format)}&tilematrix=${encodeURIComponent(tileMatrixSet)}:{z}&tilerow={y}&tilecol={x}`;
}

// Accept only WebMercator variants for WMTS (EPSG:3857 family)
export function isWebMercatorMatrixSet(name: string | undefined | null): boolean {
  if (!name) return false;
  return /3857|900913|googlemapscompatible|google|web ?mercator|mercatorquad/i.test(
    name,
  );
}

export function pickWebMercatorMatrixSet(
  candidateSets: string[],
): string | undefined {
  if (!candidateSets || !candidateSets.length) return undefined;
  // First pass: direct EPSG:3857 style codes
  let chosen = candidateSets.find((s) => /3857/.test(s));
  if (chosen) return chosen;
  // Second: common aliases
  chosen = candidateSets.find((s) => /900913|google|mercator/i.test(s));
  return chosen;
}

// Parse a WCS GetCoverage URL and derive a WMS GetMap base (Leaflet-friendly) + legend params
export function parseWCSUrl(access_url: string): ParsedWcsLayer {
  try {
    const urlObj = new URL(access_url);
    const baseUrl = `${urlObj.origin}${urlObj.pathname}`; // e.g. https://server/geoserver/wcs
    const params = urlObj.searchParams;
    // coverageId may appear as coverageId or coverage
    const coverageId = params.get("coverageId") || params.get("coverage") || "";
    if (!coverageId) {
      Logger.warn("Could not extract coverageId from WCS URL:", access_url);
    }
    // Derive WMS base by swapping trailing /wcs or /ows with /wms
    let wmsBaseUrl = baseUrl;
    if (wmsBaseUrl.endsWith("/wcs")) {
      wmsBaseUrl = wmsBaseUrl.slice(0, -4) + "/wms";
    } else if (wmsBaseUrl.endsWith("/ows")) {
      wmsBaseUrl = wmsBaseUrl.replace(/\/ows$/, "/wms");
    } else if (!wmsBaseUrl.endsWith("/wms")) {
      // Best-effort: append /wms if neither present
      wmsBaseUrl = wmsBaseUrl + "/wms";
    }
    // Build legend URL (standard WMS GetLegendGraphic)
    const legendParams = new URLSearchParams({
      service: "WMS",
      request: "GetLegendGraphic",
      version: "1.1.0",
      format: "image/png",
      layer: coverageId,
    });
    const legendUrl = `${wmsBaseUrl}?${legendParams.toString()}`;
    return {
      baseUrl: wmsBaseUrl,
      layers: coverageId,
      format: "image/png",
      transparent: true,
      legendUrl,
      originalUrl: access_url,
    };
  } catch (err) {
    Logger.error("Error parsing WCS URL:", err);
    return {
      baseUrl: access_url,
      layers: "",
      format: "image/png",
      transparent: true,
      legendUrl: "",
      originalUrl: access_url,
    };
  }
}
