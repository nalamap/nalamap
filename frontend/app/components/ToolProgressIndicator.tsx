// components/ToolProgressIndicator.tsx
"use client";

import React from "react";
import { ToolUpdate } from "../stores/chatInterfaceStore";

interface ToolProgressIndicatorProps {
  toolUpdates: ToolUpdate[];
}

/**
 * Format tool input parameters for display
 * Extracts user-friendly information from complex objects
 */
function formatToolInput(input: any): string | null {
  if (!input || typeof input !== "object") {
    return null;
  }

  const params: string[] = [];

  // Extract common meaningful parameters
  if (input.query) {
    params.push(`query: "${input.query}"`);
  }

  if (input.location) {
    params.push(`location: "${input.location}"`);
  }

  if (input.search_query) {
    params.push(`search: "${input.search_query}"`);
  }

  if (input.operator) {
    params.push(`operator: ${input.operator}`);
  }

  if (input.operation) {
    params.push(`operation: ${input.operation}`);
  }

  if (input.distance !== undefined) {
    params.push(`distance: ${input.distance}m`);
  }

  if (input.buffer_distance !== undefined) {
    params.push(`buffer: ${input.buffer_distance}m`);
  }

  // Handle layer references - show layer name instead of full object
  if (input.layer_id) {
    params.push(`layer: ${input.layer_id}`);
  }

  if (input.layer_name) {
    params.push(`layer: "${input.layer_name}"`);
  }

  // Handle multiple layers
  if (input.layer_ids && Array.isArray(input.layer_ids)) {
    params.push(`layers: ${input.layer_ids.length} selected`);
  }

  // Handle GeoJSON features - show count instead of full geometry
  if (input.features && Array.isArray(input.features)) {
    params.push(`features: ${input.features.length} items`);
  }

  // Handle geometry type
  if (input.geometry_type) {
    params.push(`type: ${input.geometry_type}`);
  }

  // Handle attribute filters
  if (input.attribute) {
    params.push(`attribute: ${input.attribute}`);
  }

  if (input.filter) {
    if (typeof input.filter === "string") {
      params.push(`filter: "${input.filter}"`);
    } else {
      params.push(`filter applied`);
    }
  }

  // Handle bbox (bounding box)
  if (input.bbox && Array.isArray(input.bbox) && input.bbox.length === 4) {
    params.push(`bbox: [${input.bbox.map((n: number) => n.toFixed(2)).join(", ")}]`);
  }

  // Handle service URLs (show domain only)
  if (input.service_url) {
    try {
      const url = new URL(input.service_url);
      params.push(`service: ${url.hostname}`);
    } catch {
      params.push(`service: ${input.service_url.substring(0, 30)}...`);
    }
  }

  // Handle coordinate pairs
  if (input.coordinates && Array.isArray(input.coordinates)) {
    if (input.coordinates.length === 2) {
      params.push(`coords: [${input.coordinates.map((n: number) => n.toFixed(4)).join(", ")}]`);
    }
  }

  // Handle limit/max results
  if (input.limit !== undefined) {
    params.push(`limit: ${input.limit}`);
  }

  if (input.max_results !== undefined) {
    params.push(`max: ${input.max_results}`);
  }

  // If we found any meaningful parameters, return them
  if (params.length > 0) {
    return params.join(", ");
  }

  // If no specific parameters were found, check if there are any keys
  const keys = Object.keys(input).filter((k) => !k.startsWith("_"));
  if (keys.length > 0 && keys.length <= 3) {
    // Show simple key-value pairs for small objects
    return keys
      .map((key) => {
        const value = input[key];
        if (typeof value === "string") {
          return `${key}: "${value.substring(0, 30)}"`;
        } else if (typeof value === "number") {
          return `${key}: ${value}`;
        } else if (typeof value === "boolean") {
          return `${key}: ${value}`;
        }
        return null;
      })
      .filter(Boolean)
      .join(", ");
  }

  return null;
}

const ToolProgressIndicator: React.FC<ToolProgressIndicatorProps> = ({
  toolUpdates,
}) => {
  if (toolUpdates.length === 0) {
    return null;
  }

  return (
    <div className="tool-progress-container">
      <div className="tool-progress-header">
        <span className="tool-progress-title">Agent Activity</span>
      </div>
      <div className="tool-progress-list">
        {toolUpdates.map((tool, index) => {
          const formattedParams = formatToolInput(tool.input);
          
          return (
            <div
              key={`${tool.name}-${index}`}
              className={`tool-progress-item tool-progress-${tool.status}`}
            >
              <div className="tool-progress-icon">
                {tool.status === "running" && (
                  <svg
                    className="tool-spinner"
                    viewBox="0 0 24 24"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <circle
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="3"
                      strokeLinecap="round"
                      strokeDasharray="32 32"
                    >
                      <animateTransform
                        attributeName="transform"
                        type="rotate"
                        from="0 12 12"
                        to="360 12 12"
                        dur="1s"
                        repeatCount="indefinite"
                      />
                    </circle>
                  </svg>
                )}
                {tool.status === "complete" && (
                  <svg
                    className="tool-check"
                    viewBox="0 0 24 24"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      d="M20 6L9 17L4 12"
                      stroke="currentColor"
                      strokeWidth="3"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                )}
                {tool.status === "error" && (
                  <svg
                    className="tool-error"
                    viewBox="0 0 24 24"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                    <path
                      d="M15 9L9 15M9 9L15 15"
                      stroke="currentColor"
                      strokeWidth="3"
                      strokeLinecap="round"
                    />
                  </svg>
                )}
              </div>
              <div className="tool-progress-content">
                <span className="tool-progress-name">{formatToolName(tool.name)}</span>
                {formattedParams && (
                  <span className="tool-progress-params">{formattedParams}</span>
                )}
                {tool.error && <span className="tool-progress-error">{tool.error}</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

function formatToolName(name: string): string {
  // Convert snake_case or camelCase to Title Case
  return name
    .replace(/_/g, " ")
    .replace(/([A-Z])/g, " $1")
    .trim()
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

export default ToolProgressIndicator;
