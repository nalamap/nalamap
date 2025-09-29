"use client";

import { useRef, useState, useEffect } from "react";
import { useMapStore } from "../../stores/mapStore";
import { useLayerStore } from "../../stores/layerStore";
import { Eye, EyeOff, Trash2, Search, MapPin, GripVertical, Palette } from "lucide-react";
import { formatFileSize, isFileSizeValid } from "../../utils/fileUtils";
import { getUploadUrl } from "../../utils/apiBase";

// Funny geo and data-themed loading messages
const FUNNY_UPLOAD_MESSAGES = [
  "📍 Pinning your data to reality...",
  "🗺️ Teaching your data where it belongs...",
  "🌍 Giving your coordinates a home on Earth...",
  "📊 Converting chaos into beautiful geodata...",
  "🛰️ Negotiating with satellites for better reception...",
  "🗂️ Organizing your spatial mess...",
  "📐 Measuring the distance between confusion and clarity...",
  "🧭 Finding magnetic north in your dataset...",
  "🌐 Translating your data into Earth language...",
  "📡 Beaming your files through geographic dimensions...",
  "🗺️ Drawing invisible lines between your data points...",
  "📍 GPS-ing your way through file structures...",
  "🌏 Making Mother Earth proud of your data...",
  "📊 Convincing your data to stay within map boundaries...",
  "🛰️ Asking Google Earth to make room for your layer...",
  "🗃️ Filing your geodata in Earth's cabinet...",
  "📐 Calculating the shortest path to awesome maps...",
  "🧭 Pointing your data in the right direction...",
  "🌍 Giving your coordinates their passport to the map...",
  "📡 Synchronizing with the International Date Line..."
];

const FUNNY_STYLING_MESSAGES = [
  "🎨 Teaching your data some fashion sense...",
  "✨ Sprinkling AI magic on your boring gray shapes...",
  "🌈 Choosing colors that would make a cartographer cry (tears of joy)...",
  "🎭 Giving your data a makeover worthy of a map magazine cover...",
  "🖌️ Consulting with Picasso's ghost about color theory...",
  "💄 Applying digital makeup to your geographic features...",
  "👗 Dressing up your data for the geographic gala...",
  "🎨 Mixing pixels and polygons in the perfect palette...",
  "✨ Transforming your data from 'meh' to 'magnificent'...",
  "🌟 Making your layers so pretty, other maps will be jealous...",
  "🎪 Turning your dataset into a visual circus (the good kind)...",
  "🖼️ Creating art that would make da Vinci switch to GIS...",
  "🎨 Channeling Bob Ross for some happy little features...",
  "💅 Giving your polygons a professional manicure...",
  "🌈 Finding the perfect shade of 'wow' for your data...",
  "✨ Applying Instagram filters to geographic reality...",
  "🎭 Teaching your data to express its inner beauty...",
  "🖌️ Painting your data with the brush of artificial intelligence...",
  "🌟 Making your map so stunning, satellites will take selfies...",
  "🎨 Creating a masterpiece worthy of the geographic Louvre..."
];

const FUNNY_FINALIZING_MESSAGES = [
  "🏁 Crossing the finish line with style...",
  "✅ Putting the final bow on your geographic gift...",
  "🎉 Celebrating your data's successful transformation...",
  "🎯 Hitting the bullseye of cartographic perfection...",
  "🚀 Preparing for launch into the mapping stratosphere...",
  "⭐ Adding the final touches of geographic brilliance...",
  "🏆 Awarding your data the gold medal of visualization...",
  "🎪 Rolling out the red carpet for your new layer...",
  "✨ Sprinkling the last bits of mapping fairy dust...",
  "🎊 Throwing a small party for your successfully styled data...",
  "🎈 Inflating the balloons for your layer's grand opening...",
  "🎭 Taking a bow for this geographic performance...",
  "🌟 Polishing your data until it sparkles on the map...",
  "🎨 Signing the artist's name on your cartographic masterpiece...",
  "🏅 Pinning a medal on your data for outstanding service..."
];

function getRandomMessage(messages: string[]): string {
  return messages[Math.floor(Math.random() * messages.length)];
}

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

const QuickActionsButtons: React.FC<QuickActionsProps> = ({ layerId, updateLayerStyle, buttons }) => (
  <div className="flex flex-wrap gap-1">
    {buttons.map((button, index) => (
      <button
        key={index}
        onClick={() => updateLayerStyle(layerId, button.style)}
        className={button.className || "px-2 py-1 bg-gray-500 text-white text-xs rounded hover:bg-gray-600"}
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
    style: { stroke_color: "#ff0000", stroke_weight: 4, stroke_dash_array: "10,5", fill_opacity: 0.1 },
    className: "px-2 py-1 bg-rose-500 text-white text-xs rounded hover:bg-rose-600"
  },
  { 
    label: "Subtle Blue", 
    style: { stroke_color: "#0066cc", stroke_weight: 1, stroke_opacity: 0.8, fill_color: "#0066cc", fill_opacity: 0.15 },
    className: "px-2 py-1 bg-sky-500 text-white text-xs rounded hover:bg-sky-600"
  },
  { 
    label: "Green Outline", 
    style: { stroke_color: "#00aa00", stroke_weight: 3, stroke_opacity: 1.0, stroke_dash_array: "3,3,10,3", fill_opacity: 0.0 },
    className: "px-2 py-1 bg-emerald-500 text-white text-xs rounded hover:bg-emerald-600"
  },
  { 
    label: "Highlight Points", 
    style: { stroke_color: "#ff6600", stroke_weight: 2, radius: 15, fill_color: "#ffaa00", fill_opacity: 0.6 },
    className: "px-2 py-1 bg-amber-500 text-white text-xs rounded hover:bg-amber-600"
  },
];

const SECONDARY_QUICK_ACTIONS: QuickActionButton[] = [
  { label: "Subtle", style: { stroke_weight: 1, fill_opacity: 0.1 } },
  { label: "Bold", style: { stroke_weight: 4, stroke_opacity: 1.0 } },
];

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
  const [currentFileIndex, setCurrentFileIndex] = useState<number>(0);
  const [totalFiles, setTotalFiles] = useState<number>(0);
  const [currentFileName, setCurrentFileName] = useState<string>("");
  const [funnyMessage, setFunnyMessage] = useState<string>("");
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

  // Rotate funny messages during upload for entertainment
  useEffect(() => {
    if (!isUploading) return;

    const messageRotationInterval = setInterval(() => {
      if (uploadProgress < 70) {
        setFunnyMessage(getRandomMessage(FUNNY_UPLOAD_MESSAGES));
      } else if (uploadProgress < 100) {
        setFunnyMessage(getRandomMessage(FUNNY_STYLING_MESSAGES));
      } else {
        setFunnyMessage(getRandomMessage(FUNNY_FINALIZING_MESSAGES));
      }
    }, 3000); // Change message every 3 seconds

    return () => clearInterval(messageRotationInterval);
  }, [isUploading, uploadProgress]);

  const cancelUpload = () => {
    if (xhrRef.current) {
      xhrRef.current.abort();
      xhrRef.current = null;
      setIsUploading(false);
      setUploadProgress(0);
      setCurrentFileIndex(0);
      setTotalFiles(0);
      setCurrentFileName("");
      setFunnyMessage("");
      setUploadError("Upload cancelled by user");
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    // Clear any previous error message
    setUploadError(null);
    setIsUploading(true);
    setUploadProgress(0);
    setTotalFiles(files.length);
    setCurrentFileIndex(0);

    const API_UPLOAD_URL = getUploadUrl();
    const newLayers: any[] = [];

    try {
      // Process each file sequentially
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        setCurrentFileIndex(i + 1);
        setCurrentFileName(file.name);
        
        // Set a funny upload message
        setFunnyMessage(getRandomMessage(FUNNY_UPLOAD_MESSAGES));

        // Check file size limit
        if (!isFileSizeValid(file, MAX_FILE_SIZE)) {
          throw new Error(`File ${file.name} size (${formatFileSize(file.size)}) exceeds the ${MAX_FILE_SIZE_FORMATTED} limit.`);
        }

        // Upload phase (0-70% of total progress for this file)
        const baseProgress = (i / files.length) * 100;
        const uploadPhaseProgress = (progressPercent: number) => {
          const fileProgress = baseProgress + (progressPercent * 0.7) / files.length;
          setUploadProgress(Math.round(fileProgress));
        };

        // assemble form data
        const formData = new FormData();
        formData.append("file", file);

        // Upload the file
        const { url, id } = await new Promise<{ url: string, id: string }>((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhrRef.current = xhr;

          xhr.open('POST', API_UPLOAD_URL);

          // Set up progress tracking for upload phase
          xhr.upload.onprogress = (event) => {
            if (event.lengthComputable) {
              const percentComplete = Math.round((event.loaded / event.total) * 100);
              uploadPhaseProgress(percentComplete);
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

        // Upload completed, update progress to 70%
        const uploadCompleteProgress = baseProgress + (70 / files.length);
        setUploadProgress(Math.round(uploadCompleteProgress));

        // Create the new layer
        const newLayer = {
          id: id,
          name: file.name,
          data_type: "uploaded",
          data_link: url,
          visible: true,
          data_source_id: "manual",
          data_origin: "uploaded",
          data_source: "user"
        };

        // Add to store
        addLayer(newLayer);
        newLayers.push(newLayer);

        // Styling phase (70-100% of total progress for this file)
        const stylingPhaseProgress = (percent: number) => {
          const fileProgress = baseProgress + 70 / files.length + (percent * 0.3) / files.length;
          setUploadProgress(Math.round(fileProgress));
        };

        // Apply automatic AI styling
        try {
          stylingPhaseProgress(0); // Start styling phase
          
          // Set a funny styling message
          setFunnyMessage(getRandomMessage(FUNNY_STYLING_MESSAGES));

          const styleResponse = await fetch('http://localhost:8000/api/auto-style', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              layers: [newLayer]
            })
          });

          stylingPhaseProgress(50); // Halfway through styling

          if (styleResponse.ok) {
            const styleResult = await styleResponse.json();
            if (styleResult.success && styleResult.styled_layers.length > 0) {
              const styledLayer = styleResult.styled_layers[0];
              // Update the layer with the AI-generated styling
              if (styledLayer.style) {
                updateLayerStyle(id, styledLayer.style);
                console.log(`Applied automatic AI styling to layer: ${file.name}`);
              }
            }
          } else {
            console.warn('Automatic styling request failed:', styleResponse.statusText);
          }

          stylingPhaseProgress(100); // Styling complete
          
          // Set a funny finalizing message
          setFunnyMessage(getRandomMessage(FUNNY_FINALIZING_MESSAGES));
        } catch (autoStyleError) {
          console.warn('Error applying automatic styling:', autoStyleError);
          stylingPhaseProgress(100); // Still mark as complete even if styling fails
          
          // Set a funny finalizing message even if styling fails
          setFunnyMessage(getRandomMessage(FUNNY_FINALIZING_MESSAGES));
        }
      }

      // All files processed successfully
      setUploadProgress(100);
      console.log(`Successfully uploaded and styled ${files.length} file(s)`);

    } catch (err) {
      if (err instanceof Error && err.message === 'Upload cancelled by user') {
        console.log('Upload was cancelled by the user');
      } else {
        setUploadError(`Upload error: ${err instanceof Error ? err.message : String(err)}`);
        console.error("Error uploading files:", err);
      }
    } finally {
      // reset so same files can be re‑picked
      e.target.value = "";
      setIsUploading(false);
      setUploadProgress(0);
      setCurrentFileIndex(0);
      setTotalFiles(0);
      setCurrentFileName("");
      setFunnyMessage("");
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
            accept=".geojson"
            onChange={handleFileUpload}
            className="hidden"
            disabled={isUploading}
            multiple
          />
          {isUploading ? (
            <div className="flex flex-col items-center justify-center">
              <div className="w-full max-w-xs bg-gray-200 rounded-full h-2.5 mb-2">
                <div
                  className="bg-blue-500 h-2.5 rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                ></div>
              </div>
              <p className="text-sm text-blue-500">{uploadProgress}% Complete</p>
              {totalFiles > 1 && (
                <p className="text-xs text-gray-600">File {currentFileIndex} of {totalFiles}</p>
              )}
              {currentFileName && (
                <p className="text-xs text-gray-500 mt-1 truncate max-w-xs">{currentFileName}</p>
              )}
              <p className="text-xs text-gray-400 mt-1 text-center italic">
                {funnyMessage || 
                  (uploadProgress < 70 ? 'Uploading...' : uploadProgress < 100 ? 'Applying AI styling...' : 'Finalizing...')
                }
              </p>
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
              <p className="text-sm text-gray-500">Drag & drop or click to upload GeoJSON files</p>
              <p className="text-xs text-gray-400 mt-1">Supports multiple files • Max size: {MAX_FILE_SIZE_FORMATTED}</p>
              <p className="text-xs text-gray-400">Format: .geojson only</p>
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
                        <div className="font-bold text-gray-800 whitespace-normal break-words">{layer.title || layer.name}</div>
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
                          <h4 className="text-xs font-semibold text-gray-600 mb-1">Quick Actions</h4>
                          <QuickActionsButtons
                            layerId={layer.id}
                            updateLayerStyle={updateLayerStyle}
                            buttons={[...BASIC_QUICK_ACTIONS, ...SECONDARY_QUICK_ACTIONS]}
                          />
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
