import { getApiBase } from "../../../utils/apiBase";
import Logger from "../../../utils/logger";

/**
 * Check if a URL is external (not on the same origin as the current page or API).
 * External URLs may need to be fetched through the CORS proxy.
 */
export function isExternalUrl(url: string): boolean {
  try {
    const targetUrl = new URL(url);
    const currentOrigin =
      typeof window !== "undefined" ? window.location.origin : "";
    const apiBase = getApiBase();
    const apiOrigin = apiBase.startsWith("http") ? new URL(apiBase).origin : "";

    // Check if URL is on the same origin as the page or API
    return (
      targetUrl.origin !== currentOrigin &&
      targetUrl.origin !== apiOrigin &&
      !url.startsWith("/")
    );
  } catch {
    return false;
  }
}

/**
 * Detect Docker-internal service hosts that are unreachable from the browser.
 * These should always be fetched through the backend proxy.
 */
function isContainerInternalHostUrl(url: string): boolean {
  try {
    const targetUrl = new URL(url);
    const host = (targetUrl.hostname || "").toLowerCase();
    return host === "ogcapi" || host === "backend";
  } catch {
    return false;
  }
}

/**
 * Build a proxied URL for fetching external GeoJSON/WFS data through our backend.
 */
function getProxiedUrl(originalUrl: string, srsName?: string): string {
  const apiBase = getApiBase();
  const params = new URLSearchParams({ url: originalUrl });
  if (srsName) {
    params.set("srsName", srsName);
  }
  return `${apiBase}/proxy/geojson?${params.toString()}`;
}

/**
 * Build a proxied URL for fetching external images through our backend.
 * Used for legend images from external GeoServers with CORS restrictions.
 */
export function getProxiedImageUrl(originalUrl: string): string {
  const apiBase = getApiBase();
  const params = new URLSearchParams({ url: originalUrl });
  return `${apiBase}/proxy/image?${params.toString()}`;
}

/**
 * Fetch GeoJSON/WFS data, using proxy for external URLs that fail due to CORS.
 */
export async function fetchWithCorsProxy(
  url: string,
  options?: RequestInit,
): Promise<Response> {
  const isExternal = isExternalUrl(url);
  const forceProxy = isExternal && isContainerInternalHostUrl(url);

  // Docker-internal hostnames are not browser-reachable; proxy directly.
  if (forceProxy) {
    let srsName: string | undefined;
    try {
      const testU = new URL(url);
      srsName = testU.searchParams.get("srsName") || undefined;
    } catch {
      /* ignore */
    }
    const proxiedUrl = getProxiedUrl(url, srsName);
    return fetch(proxiedUrl, {
      headers: {
        Accept: "application/json, application/geo+json, */*;q=0.1",
      },
    });
  }

  // First, try direct fetch
  try {
    const res = await fetch(url, options);
    if (res.ok) return res;
    // If not OK but no CORS error, return the response anyway
    return res;
  } catch (err) {
    // Check if this is likely a CORS error (TypeError on fetch indicates network failure)
    if (isExternal && err instanceof TypeError) {
      Logger.log(
        `[CORS Proxy] Direct fetch failed for external URL, trying proxy: ${url}`,
      );

      // Extract srsName if this is a WFS request
      let srsName: string | undefined;
      try {
        const testU = new URL(url);
        srsName = testU.searchParams.get("srsName") || undefined;
      } catch {
        /* ignore */
      }

      // Retry through proxy
      const proxiedUrl = getProxiedUrl(url, srsName);
      return fetch(proxiedUrl, {
        headers: {
          Accept: "application/json, application/geo+json, */*;q=0.1",
        },
      });
    }
    // Not a CORS error or not external, re-throw
    throw err;
  }
}
