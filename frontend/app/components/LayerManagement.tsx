"use client";

import { useRef, useState } from "react";
import { useMapStore } from "../stores/mapStore";
import { useLayerStore } from "../stores/layerStore";
import { Eye, EyeOff, Trash2, Search, MapPin } from "lucide-react";
import { formatFileSize, isFileSizeValid } from "../utils/fileUtils";


export default function LayerManagement() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const setBasemap = useMapStore((state) => state.setBasemap);
  const layers = useLayerStore((state) => state.layers);
  const addLayer = useLayerStore((state) => state.addLayer);
  const toggleLayerVisibility = useLayerStore((state) => state.toggleLayerVisibility);
  const removeLayer = useLayerStore((state) => state.removeLayer);
  const reorderLayers = useLayerStore((state) => state.reorderLayers);
  const setZoomTo = useLayerStore((s) => s.setZoomTo);
  const [draggedIdx, setDraggedIdx] = useState<number | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  
  // Use ref to store the XMLHttpRequest
  const xhrRef = useRef<XMLHttpRequest | null>(null);
  
  // Define file size limit constant
  const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB in bytes
  const MAX_FILE_SIZE_FORMATTED = formatFileSize(MAX_FILE_SIZE);

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
    const API_UPLOAD_URL = process.env.NEXT_PUBLIC_API_UPLOAD_URL || "http://localhost:8000/upload";

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
    <div className="w-full h-full bg-gray-100 p-4 border-r overflow-auto">
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

      {/* User Layers Section */}
      <div className="mb-4">
        <h3 className="font-semibold mb-2">User Layers</h3>
        {layers.length === 0 ? (
          <p className="text-sm text-gray-500">No layers added yet.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {[...layers].slice().reverse().map((layer, idx, arr) => (
              <li
                key={layer.id}
                className="bg-white p-2 rounded shadow flex items-center justify-between"
                draggable
                onDragStart={() => setDraggedIdx(idx)}
                onDragOver={e => e.preventDefault()}
                onDrop={() => {
                  if (draggedIdx === null || draggedIdx === idx) return;
                  // arr is reversed, so we need to map back to the original index
                  const from = layers.length - 1 - draggedIdx;
                  const to = layers.length - 1 - idx;
                  reorderLayers(from, to);
                  setDraggedIdx(null);
                }}
                style={{
                  opacity: draggedIdx === idx ? 0.5 : 1,
                  cursor: "grab"
                }}
                title="Drag to reorder"
              >
                <div className="flex-1 min-w-0">
                  <div className="font-bold text-gray-800 truncate">{layer.name}</div>
                  <div className="text-xs text-gray-500">{layer.data_type}</div>
                </div>
                <div className="flex items-center space-x-2">
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
                    onClick={() => removeLayer(layer.id)}
                    title="Remove Layer"
                    className="text-red-500 hover:text-red-700"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </li>
            ))}
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
    </div>
  );
}
