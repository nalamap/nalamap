"use client";

import { useState, useEffect } from "react";
import {
  Eye,
  EyeOff,
  Trash2,
  Search,
  GripVertical,
  Palette,
  Download,
} from "lucide-react";
import { getApiBase } from "../../utils/apiBase";
import Logger from "../../utils/logger";

// Reusable component for quick action buttons
interface QuickActionButton {
  label: string;
  style: any;
  className?: string;
}

interface QuickActionsProps {
  layerId: string;
  updateLayerStyle: (layerId: string, style: any) => void;
  buttons: QuickActionButton[];
}

const QuickActionsButtons: React.FC<QuickActionsProps> = ({
  layerId,
  updateLayerStyle,
  buttons,
}) => (
  <div className="flex flex-wrap gap-1">
    {buttons.map((button, index) => (
      <button
        key={index}
        onClick={() => updateLayerStyle(layerId, button.style)}
        className={
          button.className ||
          "px-2 py-1 bg-neutral-500 text-neutral-50 text-xs rounded hover:bg-neutral-600 cursor-pointer transition-colors"
        }
      >
        {button.label}
      </button>
    ))}
  </div>
);

// Configuration for different quick action button sets
const BASIC_QUICK_ACTIONS: QuickActionButton[] = [
  { label: "Dashed", style: { stroke_dash_array: "5,5" } },
  { label: "Dotted", style: { stroke_dash_array: "3,3" } },
  { label: "Solid", style: { stroke_dash_array: undefined } },
  { label: "Large Points", style: { radius: 12, stroke_weight: 3 } },
];

const ADVANCED_QUICK_ACTIONS: QuickActionButton[] = [
  {
    label: "Thick Dashed",
    style: {
      stroke_color: "#ff0000",
      stroke_weight: 4,
      stroke_dash_array: "10,5",
      fill_opacity: 0.1,
    },
    className:
      "px-2 py-1 bg-corporate-1-500 text-neutral-50 text-xs rounded hover:bg-corporate-1-600 cursor-pointer transition-colors",
  },
  {
    label: "Subtle Blue",
    style: {
      stroke_color: "#0066cc",
      stroke_weight: 1,
      stroke_opacity: 0.8,
      fill_color: "#0066cc",
      fill_opacity: 0.15,
    },
    className:
      "px-2 py-1 bg-corporate-2-500 text-neutral-50 text-xs rounded hover:bg-corporate-2-600 cursor-pointer transition-colors",
  },
  {
    label: "Green Outline",
    style: {
      stroke_color: "#00aa00",
      stroke_weight: 3,
      stroke_opacity: 1.0,
      stroke_dash_array: "3,3,10,3",
      fill_opacity: 0.0,
    },
    className:
      "px-2 py-1 bg-corporate-2-500 text-neutral-50 text-xs rounded hover:bg-corporate-2-600 cursor-pointer transition-colors",
  },
  {
    label: "Highlight Points",
    style: {
      stroke_color: "#ff6600",
      stroke_weight: 2,
      radius: 15,
      fill_color: "#ffaa00",
      fill_opacity: 0.6,
    },
    className:
      "px-2 py-1 bg-warning-500 text-neutral-50 text-xs rounded hover:bg-warning-600 cursor-pointer transition-colors",
  },
];

const SECONDARY_QUICK_ACTIONS: QuickActionButton[] = [
  { label: "Subtle", style: { stroke_weight: 1, fill_opacity: 0.1 } },
  { label: "Bold", style: { stroke_weight: 4, stroke_opacity: 1.0 } },
];

interface LayerListProps {
  layers: any[];
  toggleLayerVisibility: (layerId: string) => void;
  removeLayer: (layerId: string) => void;
  reorderLayers: (fromIndex: number, toIndex: number) => void;
  updateLayerStyle: (layerId: string, style: any) => void;
  setZoomTo: (layerId: string) => void;
}

export default function LayerList({
  layers,
  toggleLayerVisibility,
  removeLayer,
  reorderLayers,
  updateLayerStyle,
  setZoomTo,
}: LayerListProps) {
  const [draggedIdx, setDraggedIdx] = useState<number | null>(null);
  const [dropTargetIdx, setDropTargetIdx] = useState<number | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [recentlyMovedId, setRecentlyMovedId] = useState<string | null>(null);
  const [stylePanelOpen, setStylePanelOpen] = useState<string | null>(null);

  // Download layer as GeoJSON
  const downloadLayer = async (layer: any) => {
    try {
      const apiBase = getApiBase();
      const response = await fetch(layer.data_link.startsWith('http') ? layer.data_link : `${apiBase}${layer.data_link}`);
      
      if (!response.ok) {
        throw new Error(`Failed to download layer: ${response.statusText}`);
      }
      
      const data = await response.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${layer.name || layer.title || 'layer'}.geojson`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      
      Logger.log(`Downloaded layer: ${layer.name}`);
    } catch (error) {
      Logger.error(`Error downloading layer ${layer.name}:`, error);
      alert(`Failed to download layer: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  // Handle drag start for download button - enables dragging to desktop/other apps
  const handleDownloadDragStart = async (e: React.DragEvent, layer: any) => {
    try {
      const apiBase = getApiBase();
      const response = await fetch(layer.data_link.startsWith('http') ? layer.data_link : `${apiBase}${layer.data_link}`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch layer: ${response.statusText}`);
      }
      
      const data = await response.json();
      const geoJsonString = JSON.stringify(data, null, 2);
      const fileName = `${layer.name || layer.title || 'layer'}.geojson`;
      
      // Set drag data for file download
      e.dataTransfer.effectAllowed = 'copy';
      e.dataTransfer.setData('DownloadURL', `application/json:${fileName}:data:application/json;charset=utf-8,${encodeURIComponent(geoJsonString)}`);
      e.dataTransfer.setData('text/plain', geoJsonString);
      
      Logger.log(`Started dragging layer: ${layer.name}`);
    } catch (error) {
      Logger.error(`Error preparing layer ${layer.name} for drag:`, error);
      e.preventDefault(); // Cancel drag if there's an error
    }
  };

  // Clear the recently moved highlight after animation completes
  useEffect(() => {
    if (recentlyMovedId) {
      const timer = setTimeout(() => {
        setRecentlyMovedId(null);
      }, 1000); // Match this with the CSS animation duration

      return () => clearTimeout(timer);
    }
  }, [recentlyMovedId]);

  return (
    <div className="mb-4">
      <h3 className="font-semibold mb-2">User Layers</h3>
      {layers.length === 0 ? (
        <p className="text-sm text-gray-500">No layers added yet.</p>
      ) : (
        <ul
          className={`space-y-2 text-sm ${isDragging ? "cursor-grabbing" : ""}`}
          onDragOver={(e) => e.preventDefault()}
          onDrop={() => {
            // Reset all drag and drop state on any drop within container
            setDraggedIdx(null);
            setDropTargetIdx(null);
            setIsDragging(false);
          }}
        >
          {[...layers]
            .slice()
            .reverse()
            .map((layer, idx, arr) => {
              const isBeingDragged = draggedIdx === idx;
              const isDropTarget = dropTargetIdx === idx;
              const isRecentlyMoved = recentlyMovedId === layer.id;

              // Determine if we're moving the layer upward or downward in the layer stack
              // If draggedIdx > dropTargetIdx, we're moving a layer up in the display (which is down in the actual stack)
              // If draggedIdx < dropTargetIdx, we're moving a layer down in the display (which is up in the actual stack)
              const isMovingUp =
                draggedIdx !== null &&
                dropTargetIdx !== null &&
                draggedIdx > dropTargetIdx;

              // Show indicator above for top item OR when moving a layer upward
              const showIndicatorAbove = idx === 0 || isMovingUp;

              return (
                <li
                  key={layer.id}
                  className={`relative transition-all duration-200 ${
                    isDropTarget
                      ? showIndicatorAbove
                        ? "mt-8"
                        : "mb-8"
                      : "mb-2"
                  } ${isBeingDragged ? "opacity-50 z-10" : "opacity-100"}`}
                  onDragOver={(e) => {
                    // This prevents the default behavior which would prevent drop
                    e.preventDefault();
                  }}
                >
                  {/* Drop indicator - showing ABOVE when appropriate */}
                  {isDropTarget && showIndicatorAbove && (
                    <div
                      className="absolute w-full h-4 -top-4 flex items-center justify-center"
                      style={{ pointerEvents: "none" }}
                    >
                      <div className="h-1.5 bg-info-600 w-full rounded-full animate-pulse"></div>
                    </div>
                  )}

                  <div
                    className={`bg-neutral-50 rounded shadow flex items-center justify-between transition-all ${
                      isDropTarget ? "border-2 border-info-400" : ""
                    } ${isRecentlyMoved ? "highlight-animation" : ""}`}
                    draggable
                    onDragStart={(e) => {
                      setDraggedIdx(idx);
                      setDropTargetIdx(null);
                      setIsDragging(true);

                      // Set drag ghost image if supported
                      if (e.dataTransfer.setDragImage) {
                        const ghostElement = document.createElement("div");
                        ghostElement.style.width = "200px";
                        ghostElement.style.padding = "8px";
                        ghostElement.style.borderRadius = "4px";
                        ghostElement.style.backgroundColor =
                          "rgba(59, 130, 246, 0.2)";
                        ghostElement.style.border =
                          "1px solid rgba(59, 130, 246, 0.5)";
                        ghostElement.style.color = "#1e40af";
                        ghostElement.style.fontWeight = "bold";
                        ghostElement.innerText = layer.title || layer.name;
                        document.body.appendChild(ghostElement);
                        e.dataTransfer.setDragImage(ghostElement, 100, 20);

                        // Clean up ghost element after it's been used
                        setTimeout(() => {
                          document.body.removeChild(ghostElement);
                        }, 0);
                      }
                    }}
                    onDragEnd={() => {
                      setIsDragging(false);
                      setDraggedIdx(null);
                      setDropTargetIdx(null);
                    }}
                    onDragOver={(e) => {
                      e.preventDefault();
                      if (draggedIdx !== idx && dropTargetIdx !== idx) {
                        setDropTargetIdx(idx);
                      }
                    }}
                    onDragEnter={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      if (draggedIdx !== idx) {
                        setDropTargetIdx(idx);
                      }
                    }}
                    onDragLeave={(e) => {
                      e.preventDefault();
                      e.stopPropagation();

                      // Check if we're leaving the element and not entering a child
                      const rect = e.currentTarget.getBoundingClientRect();
                      const x = e.clientX;
                      const y = e.clientY;

                      if (
                        x < rect.left ||
                        x >= rect.right ||
                        y < rect.top ||
                        y >= rect.bottom
                      ) {
                        if (dropTargetIdx === idx) {
                          setDropTargetIdx(null);
                        }
                      }
                    }}
                    onDrop={(e) => {
                      e.preventDefault();
                      e.stopPropagation();

                      if (draggedIdx === null || draggedIdx === idx) return;

                      // arr is reversed, so we need to map back to the original index
                      const from = layers.length - 1 - draggedIdx;
                      const to = layers.length - 1 - idx;
                      reorderLayers(from, to);

                      // Mark the moved layer for highlight animation
                      const movedLayerId = arr[draggedIdx].id;
                      setRecentlyMovedId(movedLayerId);

                      // Reset drag state
                      setIsDragging(false);
                      setDraggedIdx(null);
                      setDropTargetIdx(null);
                    }}
                    style={{
                      cursor: isDragging ? "grabbing" : "grab",
                    }}
                    title="Drag to reorder"
                  >
                    <div className="flex items-center p-2 flex-1 min-w-0">
                      <div className="mr-2 text-neutral-400 cursor-grab flex-shrink-0">
                        <GripVertical size={16} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="font-bold text-neutral-800 whitespace-normal break-words">
                          {layer.title || layer.name}
                        </div>
                        <div className="text-xs text-neutral-500">
                          {layer.data_type}{" "}
                          {layer.layer_type && ` (${layer.layer_type})`}
                        </div>
                      </div>
                      <div className="flex items-center flex-wrap gap-1 sm:gap-2 ml-2 flex-shrink-0">
                        <button
                          onClick={() => setZoomTo(layer.id)}
                          title="Zoom to this layer"
                          className="text-neutral-600 hover:text-info-600 p-1 hover:bg-neutral-100 rounded transition-colors cursor-pointer"
                        >
                          <Search size={16} />
                        </button>
                        <button
                          onClick={() => toggleLayerVisibility(layer.id)}
                          title="Toggle Visibility"
                          className="text-neutral-600 hover:text-info-600 p-1 hover:bg-neutral-100 rounded transition-colors cursor-pointer"
                        >
                          {layer.visible ? (
                            <Eye size={16} />
                          ) : (
                            <EyeOff size={16} />
                          )}
                        </button>
                        <button
                          onClick={() =>
                            setStylePanelOpen(
                              stylePanelOpen === layer.id ? null : layer.id,
                            )
                          }
                          title="Style Layer"
                          className={`p-1 rounded transition-colors cursor-pointer ${stylePanelOpen === layer.id ? "text-info-600 bg-info-100" : "text-neutral-600 hover:text-info-600 hover:bg-neutral-100"}`}
                        >
                          <Palette size={16} />
                        </button>
                        <button
                          onClick={() => downloadLayer(layer)}
                          draggable="true"
                          onDragStart={(e) => handleDownloadDragStart(e, layer)}
                          title="Download as GeoJSON (click or drag to desktop)"
                          className="text-neutral-600 hover:text-success-600 p-1 hover:bg-neutral-100 rounded transition-colors cursor-grab active:cursor-grabbing"
                        >
                          <Download size={16} />
                        </button>
                        <button
                          onClick={() => removeLayer(layer.id)}
                          title="Remove Layer"
                          className="text-danger-500 hover:text-danger-700 p-1 hover:bg-danger-50 rounded transition-colors cursor-pointer"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Style Panel */}
                  {stylePanelOpen === layer.id && (
                    <div className="mt-2 p-3 bg-neutral-50 rounded border-l-4 border-info-400">
                      <h4 className="font-semibold text-sm mb-2">
                        Style Options
                      </h4>
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        {/* Stroke Color */}
                        <div>
                          <label className="block text-neutral-700">
                            Stroke Color
                          </label>
                          <input
                            type="color"
                            value={layer.style?.stroke_color || "#3388ff"}
                            onChange={(e) =>
                              updateLayerStyle(layer.id, {
                                stroke_color: e.target.value,
                              })
                            }
                            className="w-full h-6 rounded border"
                          />
                        </div>

                        {/* Stroke Weight */}
                        <div>
                          <label className="block text-gray-700">
                            Stroke Weight
                          </label>
                          <input
                            type="range"
                            min="1"
                            max="10"
                            value={layer.style?.stroke_weight || 2}
                            onChange={(e) =>
                              updateLayerStyle(layer.id, {
                                stroke_weight: parseInt(e.target.value),
                              })
                            }
                            className="w-full"
                          />
                          <span className="text-gray-500">
                            {layer.style?.stroke_weight || 2}px
                          </span>
                        </div>

                        {/* Stroke Opacity */}
                        <div>
                          <label className="block text-gray-700">
                            Stroke Opacity
                          </label>
                          <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.1"
                            value={layer.style?.stroke_opacity || 1.0}
                            onChange={(e) =>
                              updateLayerStyle(layer.id, {
                                stroke_opacity: parseFloat(e.target.value),
                              })
                            }
                            className="w-full"
                          />
                          <span className="text-gray-500">
                            {Math.round(
                              (layer.style?.stroke_opacity || 1.0) * 100,
                            )}
                            %
                          </span>
                        </div>

                        {/* Dash Array */}
                        <div>
                          <label className="block text-gray-700">
                            Dash Pattern
                          </label>
                          <select
                            value={layer.style?.stroke_dash_array || ""}
                            onChange={(e) =>
                              updateLayerStyle(layer.id, {
                                stroke_dash_array: e.target.value || undefined,
                              })
                            }
                            className="w-full border rounded px-2 py-1"
                          >
                            <option value="">Solid Line</option>
                            <option value="5,5">Dashed (5,5)</option>
                            <option value="10,5">Long Dash (10,5)</option>
                            <option value="3,3">Dotted (3,3)</option>
                            <option value="10,5,5,5">
                              Dash-Dot (10,5,5,5)
                            </option>
                            <option value="15,5,5,5,5,5">
                              Long Dash-Dot (15,5,5,5,5,5)
                            </option>
                          </select>
                        </div>

                        {/* Dash Offset */}
                        {layer.style?.stroke_dash_array && (
                          <div>
                            <label className="block text-gray-700">
                              Dash Offset
                            </label>
                            <input
                              type="range"
                              min="0"
                              max="20"
                              value={layer.style?.stroke_dash_offset || 0}
                              onChange={(e) =>
                                updateLayerStyle(layer.id, {
                                  stroke_dash_offset: parseFloat(
                                    e.target.value,
                                  ),
                                })
                              }
                              className="w-full"
                            />
                            <span className="text-gray-500">
                              {layer.style?.stroke_dash_offset || 0}px
                            </span>
                          </div>
                        )}

                        {/* Fill Color */}
                        <div>
                          <label className="block text-gray-700">
                            Fill Color
                          </label>
                          <input
                            type="color"
                            value={layer.style?.fill_color || "#3388ff"}
                            onChange={(e) =>
                              updateLayerStyle(layer.id, {
                                fill_color: e.target.value,
                              })
                            }
                            className="w-full h-6 rounded border"
                          />
                        </div>

                        {/* Fill Opacity */}
                        <div>
                          <label className="block text-gray-700">
                            Fill Opacity
                          </label>
                          <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.1"
                            value={layer.style?.fill_opacity || 0.3}
                            onChange={(e) =>
                              updateLayerStyle(layer.id, {
                                fill_opacity: parseFloat(e.target.value),
                              })
                            }
                            className="w-full"
                          />
                          <span className="text-gray-500">
                            {Math.round(
                              (layer.style?.fill_opacity || 0.3) * 100,
                            )}
                            %
                          </span>
                        </div>

                        {/* Circle Radius (for point data) */}
                        <div>
                          <label className="block text-gray-700">
                            Point Radius
                          </label>
                          <input
                            type="range"
                            min="1"
                            max="20"
                            value={layer.style?.radius || 6}
                            onChange={(e) =>
                              updateLayerStyle(layer.id, {
                                radius: parseInt(e.target.value),
                              })
                            }
                            className="w-full"
                          />
                          <span className="text-gray-500">
                            {layer.style?.radius || 6}px
                          </span>
                        </div>

                        {/* Line Cap Style */}
                        <div>
                          <label className="block text-gray-700">
                            Line Cap
                          </label>
                          <select
                            value={layer.style?.line_cap || "round"}
                            onChange={(e) =>
                              updateLayerStyle(layer.id, {
                                line_cap: e.target.value,
                              })
                            }
                            className="w-full border rounded px-2 py-1"
                          >
                            <option value="round">Round</option>
                            <option value="square">Square</option>
                            <option value="butt">Butt</option>
                          </select>
                        </div>

                        {/* Line Join Style */}
                        <div>
                          <label className="block text-gray-700">
                            Line Join
                          </label>
                          <select
                            value={layer.style?.line_join || "round"}
                            onChange={(e) =>
                              updateLayerStyle(layer.id, {
                                line_join: e.target.value,
                              })
                            }
                            className="w-full border rounded px-2 py-1"
                          >
                            <option value="round">Round</option>
                            <option value="bevel">Bevel</option>
                            <option value="miter">Miter</option>
                          </select>
                        </div>
                      </div>

                      {/* Advanced styling section */}
                      <div className="mt-3 pt-3 border-t border-gray-200">
                        <h4 className="text-xs font-semibold text-gray-600 mb-2">
                          Advanced Effects
                        </h4>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          {/* Shadow Color */}
                          <div>
                            <label className="block text-gray-700">
                              Shadow Color
                            </label>
                            <input
                              type="color"
                              value={layer.style?.shadow_color || "#000000"}
                              onChange={(e) =>
                                updateLayerStyle(layer.id, {
                                  shadow_color: e.target.value,
                                  shadow_offset_x:
                                    layer.style?.shadow_offset_x || 2,
                                  shadow_offset_y:
                                    layer.style?.shadow_offset_y || 2,
                                  shadow_blur: layer.style?.shadow_blur || 4,
                                })
                              }
                              className="w-full h-6 rounded border"
                            />
                          </div>

                          {/* Shadow Blur */}
                          <div>
                            <label className="block text-gray-700">
                              Shadow Blur
                            </label>
                            <input
                              type="range"
                              min="0"
                              max="10"
                              value={layer.style?.shadow_blur || 0}
                              onChange={(e) =>
                                updateLayerStyle(layer.id, {
                                  shadow_blur: parseFloat(e.target.value),
                                })
                              }
                              className="w-full"
                            />
                            <span className="text-gray-500">
                              {layer.style?.shadow_blur || 0}px
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Preset buttons */}
                      <div className="mt-3">
                        <h4 className="text-xs font-semibold text-neutral-600 mb-2">
                          Quick Presets
                        </h4>
                        <div className="flex flex-wrap gap-1 mb-2">
                          <button
                            onClick={() =>
                              updateLayerStyle(layer.id, {
                                stroke_color: "#ff0000",
                                fill_color: "#ff0000",
                                fill_opacity: 0.2,
                              })
                            }
                            className="px-2 py-1 bg-danger-500 text-neutral-50 text-xs rounded hover:bg-danger-600 cursor-pointer transition-colors"
                          >
                            Red
                          </button>
                          <button
                            onClick={() =>
                              updateLayerStyle(layer.id, {
                                stroke_color: "#00ff00",
                                fill_color: "#00ff00",
                                fill_opacity: 0.2,
                              })
                            }
                            className="px-2 py-1 bg-corporate-2-500 text-neutral-50 text-xs rounded hover:bg-corporate-2-600 cursor-pointer transition-colors"
                          >
                            Green
                          </button>
                          <button
                            onClick={() =>
                              updateLayerStyle(layer.id, {
                                stroke_color: "#0000ff",
                                fill_color: "#0000ff",
                                fill_opacity: 0.2,
                              })
                            }
                            className="px-2 py-1 bg-info-600 text-neutral-50 text-xs rounded hover:bg-info-700 cursor-pointer transition-colors"
                          >
                            Blue
                          </button>
                          <button
                            onClick={() =>
                              updateLayerStyle(layer.id, {
                                stroke_color: "#ffff00",
                                fill_color: "#ffff00",
                                fill_opacity: 0.2,
                              })
                            }
                            className="px-2 py-1 bg-warning-500 text-neutral-50 text-xs rounded hover:bg-warning-600 cursor-pointer transition-colors"
                          >
                            Yellow
                          </button>
                          <button
                            onClick={() =>
                              updateLayerStyle(layer.id, {
                                stroke_color: "#800080",
                                fill_color: "#800080",
                                fill_opacity: 0.2,
                              })
                            }
                            className="px-2 py-1 bg-corporate-3-500 text-neutral-50 text-xs rounded hover:bg-corporate-3-600 cursor-pointer transition-colors"
                          >
                            Purple
                          </button>
                          <button
                            onClick={() =>
                              updateLayerStyle(layer.id, {
                                stroke_color: "#ffa500",
                                fill_color: "#ffa500",
                                fill_opacity: 0.2,
                              })
                            }
                            className="px-2 py-1 bg-warning-500 text-neutral-50 text-xs rounded hover:bg-warning-600 cursor-pointer transition-colors"
                          >
                            Orange
                          </button>
                        </div>
                        <QuickActionsButtons
                          layerId={layer.id}
                          updateLayerStyle={updateLayerStyle}
                          buttons={BASIC_QUICK_ACTIONS}
                        />

                        {/* Advanced Styling Presets */}
                        <div className="mt-2">
                          <QuickActionsButtons
                            layerId={layer.id}
                            updateLayerStyle={updateLayerStyle}
                            buttons={ADVANCED_QUICK_ACTIONS}
                          />
                        </div>

                        {/* Geometry-specific quick actions */}
                        <div className="mt-2">
                          <h4 className="text-xs font-semibold text-neutral-600 mb-1">
                            Quick Actions
                          </h4>
                          <QuickActionsButtons
                            layerId={layer.id}
                            updateLayerStyle={updateLayerStyle}
                            buttons={[
                              ...BASIC_QUICK_ACTIONS,
                              ...SECONDARY_QUICK_ACTIONS,
                            ]}
                          />
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Drop indicator - showing BELOW when appropriate */}
                  {isDropTarget && !showIndicatorAbove && (
                    <div
                      className="absolute w-full h-4 -bottom-4 flex items-center justify-center"
                      style={{ pointerEvents: "none" }}
                    >
                      <div className="h-1.5 bg-info-600 w-full rounded-full animate-pulse"></div>
                    </div>
                  )}
                </li>
              );
            })}
        </ul>
      )}

      {/* Add the animation CSS */}
      <style jsx global>{`
        @keyframes highlight {
          0% {
            background-color: white;
          }
          30% {
            background-color: rgba(59, 130, 246, 0.2);
          }
          100% {
            background-color: white;
          }
        }

        .highlight-animation {
          animation: highlight 1s ease;
        }
      `}</style>
    </div>
  );
}
