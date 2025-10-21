// components/ToolProgressIndicator.tsx
"use client";

import React from "react";
import { ToolUpdate } from "../stores/chatInterfaceStore";

interface ToolProgressIndicatorProps {
  toolUpdates: ToolUpdate[];
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
        {toolUpdates.map((tool, index) => (
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
              {tool.error && <span className="tool-progress-error">{tool.error}</span>}
            </div>
          </div>
        ))}
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
