"use client";

import { memo, useEffect, useMemo, useState } from "react";

import Logger from "../../../utils/logger";
import { getProxiedImageUrl, isExternalUrl } from "./proxy";
import { ParsedWmsLayer, ParsedWmtsLayer } from "./types";

// Legend component that displays a title above the legend image.
export const Legend = memo(function Legend({
  wmsLayer,
  wmtsLayer,
  title,
  standalone = false,
}: {
  wmsLayer?: ParsedWmsLayer;
  wmtsLayer?: ParsedWmtsLayer;
  title?: string;
  standalone?: boolean;
}) {
  // Create a stable unique identifier for this legend
  const uniqueId = useMemo(() => {
    if (wmsLayer) {
      return `wms-${wmsLayer.baseUrl}-${wmsLayer.layers}`;
    }
    if (wmtsLayer) {
      return `wmts-${wmtsLayer.originalUrl}`;
    }
    return "unknown";
  }, [wmsLayer?.baseUrl, wmsLayer?.layers, wmtsLayer?.originalUrl]);

  const [legendUrl, setLegendUrl] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [hasError, setHasError] = useState<boolean>(false);
  const [hasFallbackAttempted, setHasFallbackAttempted] =
    useState<boolean>(false);
  const [hasProxyAttempted, setHasProxyAttempted] = useState<boolean>(false);
  const [lastUniqueId, setLastUniqueId] = useState<string>("");
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);
  const [isImageMaximized, setIsImageMaximized] = useState<boolean>(false);
  // Keep track of the original (non-proxied) URL for fallback logic
  const [originalLegendUrl, setOriginalLegendUrl] = useState<string>("");

  useEffect(() => {
    // Only reset states if this is actually a different layer
    if (lastUniqueId !== uniqueId) {
      setIsLoading(true);
      setHasError(false);
      setHasFallbackAttempted(false);
      setHasProxyAttempted(false);
      setLastUniqueId(uniqueId);

      if (wmsLayer) {
        // Original WMS legend URL
        const wmsLegendUrl = `${wmsLayer.baseUrl}?service=WMS&request=GetLegendGraphic&layer=${wmsLayer.layers}&format=image/png`;
        setOriginalLegendUrl(wmsLegendUrl);
        setLegendUrl(wmsLegendUrl);
      } else if (wmtsLayer) {
        // For WMTS, start with WMTS GetLegendGraphic (for non-standard providers like FAO)
        if (wmtsLayer.wmtsLegendUrl) {
          setOriginalLegendUrl(wmtsLayer.wmtsLegendUrl);
          setLegendUrl(wmtsLayer.wmtsLegendUrl);
        } else if (wmtsLayer.wmsLegendUrl) {
          // Direct WMS fallback if no WMTS URL available
          setOriginalLegendUrl(wmtsLayer.wmsLegendUrl);
          setLegendUrl(wmtsLayer.wmsLegendUrl);
          setHasFallbackAttempted(true); // Mark as already using fallback
        } else {
          setHasError(true);
          setIsLoading(false);
        }
      } else {
        setHasError(true);
        setIsLoading(false);
      }
    }
  }, [uniqueId, wmsLayer, wmtsLayer, lastUniqueId]);

  // Don't render if no valid legend URL or has error
  if (!legendUrl || hasError) {
    return null;
  }

  const baseClasses = "bg-white p-2 rounded shadow";
  const positionClasses = standalone ? "absolute bottom-2 right-2 z-[9999]" : "";
  // Fixed width of 15% of screen width
  const sizeClasses = "w-[15vw] min-w-[200px]";

  return (
    <div className={`${baseClasses} ${positionClasses} ${sizeClasses}`.trim()}>
      {/* Header with title and toggle button */}
      <div className="flex items-center justify-between mb-2">
        {title && (
          <h4
            className={`font-bold text-sm flex-1 mr-2 ${
              isCollapsed
                ? "truncate" // Truncate with ellipsis when collapsed
                : "break-words" // Allow line breaks when expanded
            }`}
          >
            {title}
          </h4>
        )}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded hover:bg-gray-100 transition-colors"
          title={isCollapsed ? "Expand legend" : "Collapse legend"}
          aria-label={isCollapsed ? "Expand legend" : "Collapse legend"}
        >
          <svg
            className={`w-4 h-4 transition-transform ${isCollapsed ? "rotate-0" : "rotate-180"}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </button>
      </div>

      {/* Legend content - only show when not collapsed */}
      {!isCollapsed && (
        <>
          {isLoading && (
            <div className="flex items-center justify-center h-16 text-xs text-gray-500">
              Loading legend...
            </div>
          )}
          <div className="relative group cursor-pointer">
            <img
              src={legendUrl}
              alt="Layer Legend"
              className={`w-full object-contain transition-all duration-300 ease-in-out ${
                isImageMaximized ? "max-h-none" : "max-h-50"
              }`}
              style={{ display: isLoading ? "none" : "block" }}
              onClick={() => setIsImageMaximized(!isImageMaximized)}
              title={
                isImageMaximized ? "Click to minimize" : "Click to maximize"
              }
              onLoad={() => {
                setIsLoading(false);
                Logger.log("Legend loaded successfully:", legendUrl);
              }}
              onError={() => {
                Logger.warn("Legend image failed to load:", legendUrl);

                // If this was a WMTS legend that failed and we haven't tried fallback yet
                if (
                  wmtsLayer &&
                  legendUrl === wmtsLayer.wmtsLegendUrl &&
                  wmtsLayer.wmsLegendUrl &&
                  !hasFallbackAttempted
                ) {
                  Logger.log("Trying WMS fallback for WMTS legend");
                  setHasFallbackAttempted(true);
                  setOriginalLegendUrl(wmtsLayer.wmsLegendUrl);
                  setLegendUrl(wmtsLayer.wmsLegendUrl);
                  setIsLoading(true); // Reset loading state for fallback attempt
                } else if (
                  !hasProxyAttempted &&
                  originalLegendUrl &&
                  isExternalUrl(originalLegendUrl)
                ) {
                  // Try using the image proxy for external URLs that may have CORS issues
                  Logger.log("Trying image proxy for legend:", originalLegendUrl);
                  setHasProxyAttempted(true);
                  setLegendUrl(getProxiedImageUrl(originalLegendUrl));
                  setIsLoading(true); // Reset loading state for proxy attempt
                } else {
                  // Final failure - hide the legend
                  Logger.log("Legend loading failed permanently");
                  setHasError(true);
                  setIsLoading(false);
                }
              }}
            />
            {/* Hover indicator */}
            <div className="absolute bottom-1 right-1 bg-black bg-opacity-70 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              {isImageMaximized ? "Click to minimize" : "Click to maximize"}
            </div>
          </div>
        </>
      )}
    </div>
  );
});
