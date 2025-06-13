"use client";

import { useRef, useState, useEffect } from "react";
import { useMapStore } from "../stores/mapStore";
import { useLayerStore } from "../stores/layerStore";
import { Eye, EyeOff, Trash2, Search, MapPin, GripVertical, Palette } from "lucide-react";
import { formatFileSize, isFileSizeValid } from "../utils/fileUtils";


export default function LayerManagement() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const setBasemap = useMapStore((state) => state.setBasemap);
  const layers = useLayerStore((state) => state.layers);
  const addLayer = useLayerStore((state) => state.addLayer);
  const selectForSearch = useLayerStore((s) => s.selectLayerForSearch);
  const toggleSelection = useLayerStore((s) => s.toggleLayerSelection);
  const toggleLayerVisibility = useLayerStore((state) => state.toggleLayerVisibility);
  const removeLayer = useLayerStore((state) => state.removeLayer);
  const reorderLayers = useLayerStore((state) => state.reorderLayers);
  const updateLayerStyle = useLayerStore((state) => state.updateLayerStyle);
  const setZoomTo = useLayerStore((s) => s.setZoomTo);
  const [draggedIdx, setDraggedIdx] = useState<number | null>(null);
  const [dropTargetIdx, setDropTargetIdx] = useState<number | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [recentlyMovedId, setRecentlyMovedId] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [stylePanelOpen, setStylePanelOpen] = useState<string | null>(null); // Store layer ID of open styling panel

  // Use ref to store the XMLHttpRequest
  const xhrRef = useRef<XMLHttpRequest | null>(null);

  // Define file size limit constant
  const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB in bytes
  const MAX_FILE_SIZE_FORMATTED = formatFileSize(MAX_FILE_SIZE);

  // Clear the recently moved highlight after animation completes
  useEffect(() => {
    if (recentlyMovedId) {
      const timer = setTimeout(() => {
        setRecentlyMovedId(null);
      }, 1000); // Match this with the CSS animation duration

      return () => clearTimeout(timer);
    }
  }, [recentlyMovedId]);

  const cancelUpload = () => {
    if (xhrRef.current) {
      xhrRef.current.abort();
      xhrRef.current = null;
      setIsUploading(false);
      setUploadProgress(0);
      setUploadError("Upload cancelled by user");
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Clear any previous error message
    setUploadError(null);
    setIsUploading(true);
    setUploadProgress(0);

    // Check file size limit
    if (!isFileSizeValid(file, MAX_FILE_SIZE)) {
      setUploadError(`File size (${formatFileSize(file.size)}) exceeds the ${MAX_FILE_SIZE_FORMATTED} limit. Please upload a smaller file.`);
      e.target.value = "";
      setIsUploading(false);
      return;
    }

    // assemble form data
    const formData = new FormData();
    formData.append("file", file);
    const API_UPLOAD_URL = process.env.NEXT_PUBLIC_API_UPLOAD_URL || "http://localhost:8000/api/upload";

    try {
      // Use XMLHttpRequest to track upload progress
      const xhr = new XMLHttpRequest();
      xhrRef.current = xhr;

      // Create a promise to handle the upload
      const uploadPromise = new Promise<{ url: string, id: string }>((resolve, reject) => {
        xhr.open('POST', API_UPLOAD_URL);

        // Set up progress tracking
        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable) {
            const percentComplete = Math.round((event.loaded / event.total) * 100);
            setUploadProgress(percentComplete);
          }
        };

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              const data = JSON.parse(xhr.responseText);
              resolve(data);
            } catch (error) {
              reject(new Error('Invalid JSON response'));
            }
          } else {
            // Try to parse error as JSON first
            try {
              const errorData = JSON.parse(xhr.responseText);
              reject(new Error(errorData.detail || 'Upload failed'));
            } catch (e) {
              reject(new Error(`Upload failed: ${xhr.statusText}`));
            }
          }
        };

        xhr.onerror = () => reject(new Error('Network error occurred'));
        xhr.ontimeout = () => reject(new Error('Upload timed out'));
        xhr.onabort = () => reject(new Error('Upload cancelled by user'));

        xhr.send(formData);
      });

      // Wait for upload to complete
      const { url, id } = await uploadPromise;

      // now add to your zustand store
      addLayer({
        id: id,
        name: file.name,
        data_type: "uploaded",
        data_link: url,
        visible: true,
        data_source_id: "manual",
        data_origin: "uploaded",
        data_source: "user"
      });
    } catch (err) {
      if (err instanceof Error && err.message === 'Upload cancelled by user') {
        console.log('Upload was cancelled by the user');
      } else {
        setUploadError(`Upload error: ${err instanceof Error ? err.message : String(err)}`);
        console.error("Error uploading file:", err);
      }
    } finally {
      // reset so same file can be re‑picked
      e.target.value = "";
      setIsUploading(false);
      setUploadProgress(0);
      xhrRef.current = null;
    }
  };

  const handleBasemapChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selected = e.target.value;
    type BasemapKey = 'osm' | 'carto-positron' | 'carto-dark' | 'google-satellite' | 'google-hybrid' | 'google-terrain';

    const basemaps: Record<BasemapKey, { url: string; attribution: string }> = {
      osm: {
        url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      },
      "carto-positron": {
        url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="https://carto.com/attribution">CARTO</a>'
      },
      "carto-dark": {
        url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="https://carto.com/attribution">CARTO</a>'
      },
      "google-satellite": {
        url: "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attribution: '&copy; Google Satellite'
      },
      "google-hybrid": {
        url: "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
        attribution: '&copy; Google Hybrid'
      },
      "google-terrain": {
        url: "https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}",
        attribution: '&copy; Google Terrain'
      }
    };
    setBasemap(basemaps[selected as BasemapKey] || basemaps["carto-positron"]);
  };

  return (
    <div
      className="w-full h-full bg-gray-100 p-4 border-r overflow-auto"
      onDragOver={(e) => e.preventDefault()}
      onDrop={() => {
        // Reset all drag and drop state on any drop within container
        setDraggedIdx(null);
        setDropTargetIdx(null);
        setIsDragging(false);
      }}
    >
      <h2 className="text-xl font-bold mb-4">Layer Management</h2>

      {/* Upload Section */}
      <div className="mb-4">
        <h3 className="font-semibold mb-2">Upload Data</h3>
        <div
          className={`border border-dashed border-gray-400 p-4 rounded bg-white text-center cursor-pointer ${isUploading ? 'opacity-75' : ''}`}
          onClick={() => !isUploading && fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".geojson,.kml,.json,.zip"
            onChange={handleFileUpload}
            className="hidden"
            disabled={isUploading}
          />
          {isUploading ? (
            <div className="flex flex-col items-center justify-center">
              <div className="w-full max-w-xs bg-gray-200 rounded-full h-2.5 mb-2">
                <div
                  className="bg-blue-500 h-2.5 rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                ></div>
              </div>
              <p className="text-sm text-blue-500">{uploadProgress}% Uploaded</p>
              <p className="text-xs text-gray-500 mt-1">Please wait...</p>
              <button
                onClick={(e) => {
                  e.stopPropagation(); // Prevent triggering the file input click
                  cancelUpload();
                }}
                className="mt-2 px-3 py-1 bg-red-100 text-red-700 text-xs rounded hover:bg-red-200 transition-colors"
              >
                Cancel Upload
              </button>
            </div>
          ) : (
            <>
              <p className="text-sm text-gray-500">Drag & drop or click to upload</p>
              <p className="text-xs text-gray-400 mt-1">Maximum file size: {MAX_FILE_SIZE_FORMATTED}</p>
            </>
          )}
        </div>
        {uploadError && (
          <div className="mt-2 p-2 bg-red-100 border border-red-400 text-red-700 text-sm rounded">
            {uploadError}
          </div>
        )}
      </div>

      <hr className="my-4" />

      <hr className="my-4" />

      {/* User Layers Section */}
      <div className="mb-4">
        <h3 className="font-semibold mb-2">User Layers</h3>
        {layers.length === 0 ? (
          <p className="text-sm text-gray-500">No layers added yet.</p>
        ) : (
          <ul className={`space-y-2 text-sm ${isDragging ? 'cursor-grabbing' : ''}`}>
            {[...layers].slice().reverse().map((layer, idx, arr) => {
              const isBeingDragged = draggedIdx === idx;
              const isDropTarget = dropTargetIdx === idx;
              const isRecentlyMoved = recentlyMovedId === layer.id;

              // Determine if we're moving the layer upward or downward in the layer stack
              // If draggedIdx > dropTargetIdx, we're moving a layer up in the display (which is down in the actual stack)
              // If draggedIdx < dropTargetIdx, we're moving a layer down in the display (which is up in the actual stack)
              const isMovingUp = draggedIdx !== null && dropTargetIdx !== null && draggedIdx > dropTargetIdx;

              // Show indicator above for top item OR when moving a layer upward
              const showIndicatorAbove = idx === 0 || isMovingUp;

              return (
                <li
                  key={layer.id}
                  className={`relative transition-all duration-200 ${isDropTarget ? (showIndicatorAbove ? 'mt-8' : 'mb-8') : 'mb-2'
                    } ${isBeingDragged ? 'opacity-50 z-10' : 'opacity-100'
                    }`}
                  onDragOver={(e) => {
                    // This prevents the default behavior which would prevent drop
                    e.preventDefault();
                  }}
                >
                  {/* Drop indicator - showing ABOVE when appropriate */}
                  {isDropTarget && showIndicatorAbove && (
                    <div
                      className="absolute w-full h-4 -top-4 flex items-center justify-center"
                      style={{ pointerEvents: 'none' }}
                    >
                      <div className="h-1.5 bg-blue-500 w-full rounded-full animate-pulse"></div>
                    </div>
                  )}

                  <div
                    className={`bg-white rounded shadow flex items-center justify-between transition-all ${isDropTarget ? 'border-2 border-blue-400' : ''
                      } ${isRecentlyMoved ? 'highlight-animation' : ''
                      }`}
                    draggable
                    onDragStart={(e) => {
                      setDraggedIdx(idx);
                      setDropTargetIdx(null);
                      setIsDragging(true);

                      // Set drag ghost image if supported
                      if (e.dataTransfer.setDragImage) {
                        const ghostElement = document.createElement('div');
                        ghostElement.style.width = '200px';
                        ghostElement.style.padding = '8px';
                        ghostElement.style.borderRadius = '4px';
                        ghostElement.style.backgroundColor = 'rgba(59, 130, 246, 0.2)';
                        ghostElement.style.border = '1px solid rgba(59, 130, 246, 0.5)';
                        ghostElement.style.color = '#1e40af';
                        ghostElement.style.fontWeight = 'bold';
                        ghostElement.innerText = layer.name;
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
                        x < rect.left || x >= rect.right ||
                        y < rect.top || y >= rect.bottom
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
                      cursor: isDragging ? "grabbing" : "grab"
                    }}
                    title="Drag to reorder"
                  >
                    <div className="flex items-center p-2 flex-1 min-w-0">
                      <div className="mr-2 text-gray-400 cursor-grab flex-shrink-0">
                        <GripVertical size={16} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="font-bold text-gray-800 truncate">{layer.name}</div>
                        <div className="text-xs text-gray-500">{layer.data_type} {layer.layer_type && ` (${layer.layer_type})`}</div>
                      </div>
                      <div className="flex items-center space-x-2 ml-2">
                        <button
                          onClick={() => setZoomTo(layer.id)}
                          title="Zoom to this layer"
                          className="text-gray-600 hover:text-blue-600"
                        >
                          <Search size={16} />
                        </button>
                        <button
                          onClick={() => toggleLayerVisibility(layer.id)}
                          title="Toggle Visibility"
                          className="text-gray-600 hover:text-blue-600"
                        >
                          {layer.visible ? <Eye size={16} /> : <EyeOff size={16} />}
                        </button>
                        <button
                          onClick={() => setStylePanelOpen(stylePanelOpen === layer.id ? null : layer.id)}
                          title="Style Layer"
                          className={`${stylePanelOpen === layer.id ? 'text-blue-600' : 'text-gray-600 hover:text-blue-600'}`}
                        >
                          <Palette size={16} />
                        </button>
                        <button
                          onClick={() => removeLayer(layer.id)}
                          title="Remove Layer"
                          className="text-red-500 hover:text-red-700"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Style Panel */}
                  {stylePanelOpen === layer.id && (
                    <div className="mt-2 p-3 bg-gray-50 rounded border-l-4 border-blue-400">
                      <h4 className="font-semibold text-sm mb-2">Style Options</h4>
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        {/* Stroke Color */}
                        <div>
                          <label className="block text-gray-700">Stroke Color</label>
                          <input
                            type="color"
                            value={layer.style?.stroke_color || "#3388ff"}
                            onChange={(e) => updateLayerStyle(layer.id, { stroke_color: e.target.value })}
                            className="w-full h-6 rounded border"
                          />
                        </div>
                        
                        {/* Stroke Weight */}
                        <div>
                          <label className="block text-gray-700">Stroke Weight</label>
                          <input
                            type="range"
                            min="1"
                            max="10"
                            value={layer.style?.stroke_weight || 2}
                            onChange={(e) => updateLayerStyle(layer.id, { stroke_weight: parseInt(e.target.value) })}
                            className="w-full"
                          />
                          <span className="text-gray-500">{layer.style?.stroke_weight || 2}px</span>
                        </div>
                        
                        {/* Stroke Opacity */}
                        <div>
                          <label className="block text-gray-700">Stroke Opacity</label>
                          <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.1"
                            value={layer.style?.stroke_opacity || 1.0}
                            onChange={(e) => updateLayerStyle(layer.id, { stroke_opacity: parseFloat(e.target.value) })}
                            className="w-full"
                          />
                          <span className="text-gray-500">{Math.round((layer.style?.stroke_opacity || 1.0) * 100)}%</span>
                        </div>
                        
                        {/* Dash Array */}
                        <div>
                          <label className="block text-gray-700">Dash Pattern</label>
                          <select
                            value={layer.style?.stroke_dash_array || ""}
                            onChange={(e) => updateLayerStyle(layer.id, { stroke_dash_array: e.target.value || undefined })}
                            className="w-full border rounded px-2 py-1"
                          >
                            <option value="">Solid Line</option>
                            <option value="5,5">Dashed (5,5)</option>
                            <option value="10,5">Long Dash (10,5)</option>
                            <option value="3,3">Dotted (3,3)</option>
                            <option value="10,5,5,5">Dash-Dot (10,5,5,5)</option>
                            <option value="15,5,5,5,5,5">Long Dash-Dot (15,5,5,5,5,5)</option>
                          </select>
                        </div>
                        
                        {/* Dash Offset */}
                        {layer.style?.stroke_dash_array && (
                          <div>
                            <label className="block text-gray-700">Dash Offset</label>
                            <input
                              type="range"
                              min="0"
                              max="20"
                              value={layer.style?.stroke_dash_offset || 0}
                              onChange={(e) => updateLayerStyle(layer.id, { stroke_dash_offset: parseFloat(e.target.value) })}
                              className="w-full"
                            />
                            <span className="text-gray-500">{layer.style?.stroke_dash_offset || 0}px</span>
                          </div>
                        )}
                        
                        {/* Fill Color */}
                        <div>
                          <label className="block text-gray-700">Fill Color</label>
                          <input
                            type="color"
                            value={layer.style?.fill_color || "#3388ff"}
                            onChange={(e) => updateLayerStyle(layer.id, { fill_color: e.target.value })}
                            className="w-full h-6 rounded border"
                          />
                        </div>
                        
                        {/* Fill Opacity */}
                        <div>
                          <label className="block text-gray-700">Fill Opacity</label>
                          <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.1"
                            value={layer.style?.fill_opacity || 0.3}
                            onChange={(e) => updateLayerStyle(layer.id, { fill_opacity: parseFloat(e.target.value) })}
                            className="w-full"
                          />
                          <span className="text-gray-500">{Math.round((layer.style?.fill_opacity || 0.3) * 100)}%</span>
                        </div>
                        
                        {/* Circle Radius (for point data) */}
                        <div>
                          <label className="block text-gray-700">Point Radius</label>
                          <input
                            type="range"
                            min="1"
                            max="20"
                            value={layer.style?.radius || 6}
                            onChange={(e) => updateLayerStyle(layer.id, { radius: parseInt(e.target.value) })}
                            className="w-full"
                          />
                          <span className="text-gray-500">{layer.style?.radius || 6}px</span>
                        </div>

                        {/* Line Cap Style */}
                        <div>
                          <label className="block text-gray-700">Line Cap</label>
                          <select
                            value={layer.style?.line_cap || "round"}
                            onChange={(e) => updateLayerStyle(layer.id, { line_cap: e.target.value })}
                            className="w-full border rounded px-2 py-1"
                          >
                            <option value="round">Round</option>
                            <option value="square">Square</option>
                            <option value="butt">Butt</option>
                          </select>
                        </div>

                        {/* Line Join Style */}
                        <div>
                          <label className="block text-gray-700">Line Join</label>
                          <select
                            value={layer.style?.line_join || "round"}
                            onChange={(e) => updateLayerStyle(layer.id, { line_join: e.target.value })}
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
                        <h4 className="text-xs font-semibold text-gray-600 mb-2">Advanced Effects</h4>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          {/* Shadow Color */}
                          <div>
                            <label className="block text-gray-700">Shadow Color</label>
                            <input
                              type="color"
                              value={layer.style?.shadow_color || "#000000"}
                              onChange={(e) => updateLayerStyle(layer.id, { 
                                shadow_color: e.target.value,
                                shadow_offset_x: layer.style?.shadow_offset_x || 2,
                                shadow_offset_y: layer.style?.shadow_offset_y || 2,
                                shadow_blur: layer.style?.shadow_blur || 4
                              })}
                              className="w-full h-6 rounded border"
                            />
                          </div>

                          {/* Shadow Blur */}
                          <div>
                            <label className="block text-gray-700">Shadow Blur</label>
                            <input
                              type="range"
                              min="0"
                              max="10"
                              value={layer.style?.shadow_blur || 0}
                              onChange={(e) => updateLayerStyle(layer.id, { shadow_blur: parseFloat(e.target.value) })}
                              className="w-full"
                            />
                            <span className="text-gray-500">{layer.style?.shadow_blur || 0}px</span>
                          </div>
                        </div>
                      </div>
                      
                      {/* Preset buttons */}
                      <div className="mt-3">
                        <h4 className="text-xs font-semibold text-gray-600 mb-2">Quick Presets</h4>
                        <div className="flex flex-wrap gap-1 mb-2">
                          <button 
                            onClick={() => updateLayerStyle(layer.id, { stroke_color: "#ff0000", fill_color: "#ff0000", fill_opacity: 0.2 })}
                            className="px-2 py-1 bg-red-500 text-white text-xs rounded hover:bg-red-600"
                          >
                            Red
                          </button>
                          <button 
                            onClick={() => updateLayerStyle(layer.id, { stroke_color: "#00ff00", fill_color: "#00ff00", fill_opacity: 0.2 })}
                            className="px-2 py-1 bg-green-500 text-white text-xs rounded hover:bg-green-600"
                          >
                            Green
                          </button>
                          <button 
                            onClick={() => updateLayerStyle(layer.id, { stroke_color: "#0000ff", fill_color: "#0000ff", fill_opacity: 0.2 })}
                            className="px-2 py-1 bg-blue-500 text-white text-xs rounded hover:bg-blue-600"
                          >
                            Blue
                          </button>
                          <button 
                            onClick={() => updateLayerStyle(layer.id, { stroke_color: "#ffff00", fill_color: "#ffff00", fill_opacity: 0.2 })}
                            className="px-2 py-1 bg-yellow-500 text-white text-xs rounded hover:bg-yellow-600"
                          >
                            Yellow
                          </button>
                          <button 
                            onClick={() => updateLayerStyle(layer.id, { stroke_color: "#800080", fill_color: "#800080", fill_opacity: 0.2 })}
                            className="px-2 py-1 bg-purple-500 text-white text-xs rounded hover:bg-purple-600"
                          >
                            Purple
                          </button>
                          <button 
                            onClick={() => updateLayerStyle(layer.id, { stroke_color: "#ffa500", fill_color: "#ffa500", fill_opacity: 0.2 })}
                            className="px-2 py-1 bg-orange-500 text-white text-xs rounded hover:bg-orange-600"
                          >
                            Orange
                          </button>
                        </div>
                        <div className="flex flex-wrap gap-1">
                          <button 
                            onClick={() => updateLayerStyle(layer.id, { stroke_dash_array: "5,5" })}
                            className="px-2 py-1 bg-gray-500 text-white text-xs rounded hover:bg-gray-600"
                          >
                            Dashed
                          </button>
                          <button 
                            onClick={() => updateLayerStyle(layer.id, { stroke_dash_array: "3,3" })}
                            className="px-2 py-1 bg-gray-500 text-white text-xs rounded hover:bg-gray-600"
                          >
                            Dotted
                          </button>
                          <button 
                            onClick={() => updateLayerStyle(layer.id, { stroke_dash_array: undefined })}
                            className="px-2 py-1 bg-gray-500 text-white text-xs rounded hover:bg-gray-600"
                          >
                            Solid
                          </button>
                          <button 
                            onClick={() => updateLayerStyle(layer.id, { radius: 12, stroke_weight: 3 })}
                            className="px-2 py-1 bg-gray-500 text-white text-xs rounded hover:bg-gray-600"
                          >
                            Large Points
                          </button>
                        </div>
                        
                        {/* Advanced Styling Presets */}
                        <div className="flex flex-wrap gap-1 mt-2">
                          <button 
                            onClick={() => updateLayerStyle(layer.id, { 
                              stroke_color: "#ff0000", 
                              stroke_weight: 4, 
                              stroke_dash_array: "10,5",
                              fill_opacity: 0.1 
                            })}
                            className="px-2 py-1 bg-rose-500 text-white text-xs rounded hover:bg-rose-600"
                          >
                            Thick Dashed
                          </button>
                          <button 
                            onClick={() => updateLayerStyle(layer.id, { 
                              stroke_color: "#0066cc", 
                              stroke_weight: 1, 
                              stroke_opacity: 0.8,
                              fill_color: "#0066cc",
                              fill_opacity: 0.15 
                            })}
                            className="px-2 py-1 bg-sky-500 text-white text-xs rounded hover:bg-sky-600"
                          >
                            Subtle Blue
                          </button>
                          <button 
                            onClick={() => updateLayerStyle(layer.id, { 
                              stroke_color: "#00aa00", 
                              stroke_weight: 3, 
                              stroke_opacity: 1.0,
                              stroke_dash_array: "3,3,10,3",
                              fill_opacity: 0.0 
                            })}
                            className="px-2 py-1 bg-emerald-500 text-white text-xs rounded hover:bg-emerald-600"
                          >
                            Green Outline
                          </button>
                          <button 
                            onClick={() => updateLayerStyle(layer.id, { 
                              stroke_color: "#ff6600", 
                              stroke_weight: 2, 
                              radius: 15,
                              fill_color: "#ffaa00",
                              fill_opacity: 0.6 
                            })}
                            className="px-2 py-1 bg-amber-500 text-white text-xs rounded hover:bg-amber-600"
                          >
                            Highlight Points
                          </button>
                        </div>
                        
                        {/* Geometry-specific quick actions */}
                        <div className="mt-2">
                          <h4 className="text-xs font-semibold text-gray-600 mb-1">Quick Actions</h4>
                          <div className="flex flex-wrap gap-1">
                            <button 
                              onClick={() => updateLayerStyle(layer.id, { stroke_dash_array: "5,5" })}
                              className="px-2 py-1 bg-gray-500 text-white text-xs rounded hover:bg-gray-600"
                            >
                              Dashed
                            </button>
                            <button 
                              onClick={() => updateLayerStyle(layer.id, { stroke_dash_array: "3,3" })}
                              className="px-2 py-1 bg-gray-500 text-white text-xs rounded hover:bg-gray-600"
                            >
                              Dotted
                            </button>
                            <button 
                              onClick={() => updateLayerStyle(layer.id, { stroke_dash_array: undefined })}
                              className="px-2 py-1 bg-gray-500 text-white text-xs rounded hover:bg-gray-600"
                            >
                              Solid
                            </button>
                            <button 
                              onClick={() => updateLayerStyle(layer.id, { radius: 12, stroke_weight: 3 })}
                              className="px-2 py-1 bg-gray-500 text-white text-xs rounded hover:bg-gray-600"
                            >
                              Large Points
                            </button>
                            <button 
                              onClick={() => updateLayerStyle(layer.id, { stroke_weight: 1, fill_opacity: 0.1 })}
                              className="px-2 py-1 bg-gray-500 text-white text-xs rounded hover:bg-gray-600"
                            >
                              Subtle
                            </button>
                            <button 
                              onClick={() => updateLayerStyle(layer.id, { stroke_weight: 4, stroke_opacity: 1.0 })}
                              className="px-2 py-1 bg-gray-500 text-white text-xs rounded hover:bg-gray-600"
                            >
                              Bold
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Drop indicator - showing BELOW when appropriate */}
                  {isDropTarget && !showIndicatorAbove && (
                    <div
                      className="absolute w-full h-4 -bottom-4 flex items-center justify-center"
                      style={{ pointerEvents: 'none' }}
                    >
                      <div className="h-1.5 bg-blue-500 w-full rounded-full animate-pulse"></div>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <hr className="my-4" />

      {/* Basemap Switcher */}
      <div>
        <h3 className="font-semibold mb-2">Basemap</h3>
        <select
          className="w-full p-2 border rounded"
          onChange={handleBasemapChange}
          defaultValue="carto-positron"
        >
          <option value="osm">OpenStreetMap</option>
          <option value="carto-positron">Carto Positron</option>
          <option value="carto-dark">Carto Dark Matter</option>
          <option value="google-satellite">Google Satellite</option>
          <option value="google-hybrid">Google Hybrid</option>
          <option value="google-terrain">Google Terrain</option>
        </select>
      </div>

      {/* Add the animation CSS */}
      <style jsx global>{`
        @keyframes highlight {
          0% { background-color: white; }
          30% { background-color: rgba(59, 130, 246, 0.2); }
          100% { background-color: white; }
        }
        
        .highlight-animation {
          animation: highlight 1s ease;
        }
      `}</style>
    </div>
  );
}
