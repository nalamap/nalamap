"use client";

import { useRef, useState, useEffect } from "react";
import { formatFileSize, isFileSizeValid } from "../../utils/fileUtils";
import { getUploadUrl, getApiBase } from "../../utils/apiBase";
import { sha256OfFile } from "../../utils/hashUtil";
import Logger from "../../utils/logger";

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
  "📡 Synchronizing with the International Date Line...",
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
  "🎨 Creating a masterpiece worthy of the geographic Louvre...",
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
  "🏅 Pinning a medal on your data for outstanding service...",
];

function getRandomMessage(messages: string[]): string {
  return messages[Math.floor(Math.random() * messages.length)];
}

interface UploadSectionProps {
  addLayer: (layer: any) => void;
  updateLayerStyle: (layerId: string, style: any) => void;
}

export default function UploadSection({
  addLayer,
  updateLayerStyle,
}: UploadSectionProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const xhrRef = useRef<XMLHttpRequest | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [currentFileIndex, setCurrentFileIndex] = useState<number>(0);
  const [totalFiles, setTotalFiles] = useState<number>(0);
  const [currentFileName, setCurrentFileName] = useState<string>("");
  const [funnyMessage, setFunnyMessage] = useState<string>("");

  const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB in bytes
  const MAX_FILE_SIZE_FORMATTED = formatFileSize(MAX_FILE_SIZE);

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
    const API_BASE_URL = getApiBase();
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
          throw new Error(
            `File ${file.name} size (${formatFileSize(file.size)}) exceeds the ${MAX_FILE_SIZE_FORMATTED} limit.`,
          );
        }

        // Upload phase (0-70% of total progress for this file)
        const baseProgress = (i / files.length) * 100;
        const uploadPhaseProgress = (progressPercent: number) => {
          const fileProgress =
            baseProgress + (progressPercent * 0.7) / files.length;
          setUploadProgress(Math.round(fileProgress));
        };

        // assemble form data
        const formData = new FormData();
        formData.append("file", file);

        // Upload the file
        // Compute SHA-256 locally before upload for integrity verification
        const localSha256 = await sha256OfFile(file);

        const { url, id } = await new Promise<{ url: string; id: string }>(
          (resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhrRef.current = xhr;

            xhr.open("POST", API_UPLOAD_URL);

            // Set up progress tracking for upload phase
            xhr.upload.onprogress = (event) => {
              if (event.lengthComputable) {
                const percentComplete = Math.round(
                  (event.loaded / event.total) * 100,
                );
                uploadPhaseProgress(percentComplete);
              }
            };

            xhr.onload = () => {
              if (xhr.status >= 200 && xhr.status < 300) {
                try {
                  const data = JSON.parse(xhr.responseText);
                  resolve(data);
                } catch (error) {
                  reject(new Error("Invalid JSON response"));
                }
              } else {
                try {
                  const errorData = JSON.parse(xhr.responseText);
                  reject(new Error(errorData.detail || "Upload failed"));
                } catch (e) {
                  reject(new Error(`Upload failed: ${xhr.statusText}`));
                }
              }
            };

            xhr.onerror = () => reject(new Error("Network error occurred"));
            xhr.ontimeout = () => reject(new Error("Upload timed out"));
            xhr.onabort = () => reject(new Error("Upload cancelled by user"));

            xhr.send(formData);
          },
        );

        // Upload completed, update progress to 70%
        const uploadCompleteProgress = baseProgress + 70 / files.length;
        setUploadProgress(Math.round(uploadCompleteProgress));

        // Verify integrity against backend-reported hash/size
        try {
          const metaRes = await fetch(
            `${API_BASE_URL}/uploads/meta/${encodeURIComponent(id)}`,
          );
          if (metaRes.ok) {
            const meta = await metaRes.json();
            if (meta?.sha256 && typeof meta.sha256 === "string") {
              if (meta.sha256.toLowerCase() !== localSha256.toLowerCase()) {
                throw new Error(
                  `Integrity check failed for ${file.name}. Expected ${localSha256.slice(0, 8)}…, got ${String(meta.sha256).slice(0, 8)}…`,
                );
              }
            }
            if (meta?.size && Number.isFinite(Number(meta.size))) {
              const serverSize = Number(meta.size);
              if (serverSize !== file.size) {
                throw new Error(
                  `Size mismatch for ${file.name}. Local ${file.size} bytes vs server ${serverSize} bytes`,
                );
              }
            }
          } else {
            Logger.warn(
              "Upload meta endpoint returned",
              metaRes.status,
              metaRes.statusText,
            );
          }
        } catch (verifyErr) {
          // Surface integrity failure to the user and abort processing this file
          throw verifyErr instanceof Error
            ? verifyErr
            : new Error(String(verifyErr));
        }

        // Create the new layer
        const newLayer = {
          id: id,
          name: file.name,
          data_type: "uploaded",
          data_link: url,
          visible: true,
          data_source_id: "manual",
          data_origin: "uploaded",
          data_source: "user",
        };

        // Add to store
        addLayer(newLayer);
        newLayers.push(newLayer);

        // Styling phase (70-100% of total progress for this file)
        const stylingPhaseProgress = (percent: number) => {
          const fileProgress =
            baseProgress + 70 / files.length + (percent * 0.3) / files.length;
          setUploadProgress(Math.round(fileProgress));
        };

        // Apply automatic AI styling
        try {
          stylingPhaseProgress(0); // Start styling phase

          // Set a funny styling message
          setFunnyMessage(getRandomMessage(FUNNY_STYLING_MESSAGES));

          const styleResponse = await fetch(`${API_BASE_URL}/ai-style`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              layers: [newLayer],
            }),
          });

          stylingPhaseProgress(50); // Halfway through styling

          if (styleResponse.ok) {
            const styleResult = await styleResponse.json();
            if (styleResult.success && styleResult.styled_layers.length > 0) {
              const styledLayer = styleResult.styled_layers[0];
              // Update the layer with the AI-generated styling
              if (styledLayer.style) {
                updateLayerStyle(id, styledLayer.style);
                Logger.log(
                  `Applied automatic AI styling to layer: ${file.name}`,
                );
              }
            }
          } else {
            Logger.warn(
              "Automatic styling request failed:",
              styleResponse.statusText,
            );
          }

          stylingPhaseProgress(100); // Styling complete

          // Set a funny finalizing message
          setFunnyMessage(getRandomMessage(FUNNY_FINALIZING_MESSAGES));
        } catch (autoStyleError) {
          Logger.warn("Error applying automatic styling:", autoStyleError);
          stylingPhaseProgress(100); // Still mark as complete even if styling fails

          // Set a funny finalizing message even if styling fails
          setFunnyMessage(getRandomMessage(FUNNY_FINALIZING_MESSAGES));
        }
      }

      // All files processed successfully
      setUploadProgress(100);
      Logger.log(`Successfully uploaded and styled ${files.length} file(s)`);
    } catch (err) {
      if (err instanceof Error && err.message === "Upload cancelled by user") {
        Logger.log("Upload was cancelled by the user");
      } else {
        setUploadError(
          `Upload error: ${err instanceof Error ? err.message : String(err)}`,
        );
        Logger.error("Error uploading files:", err);
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

  return (
    <div className="mb-4">
      <h3 className="font-semibold mb-2">Upload Data</h3>
      <div
        className={`border border-dashed border-primary-400 p-4 rounded bg-primary-100 text-center cursor-pointer ${isUploading ? "opacity-75" : ""}`}
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
            <div className="w-full max-w-xs bg-primary-200 rounded-full h-2.5 mb-2">
              <div
                className="bg-info-600 h-2.5 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              ></div>
            </div>
            <p className="text-sm text-info-600">{uploadProgress}% Complete</p>
            {totalFiles > 1 && (
              <p className="text-xs text-neutral-600">
                File {currentFileIndex} of {totalFiles}
              </p>
            )}
            {currentFileName && (
              <p className="text-xs text-neutral-500 mt-1 truncate max-w-xs">
                {currentFileName}
              </p>
            )}
            <p className="text-xs text-neutral-400 mt-1 text-center italic">
              {funnyMessage ||
                (uploadProgress < 70
                  ? "Uploading..."
                  : uploadProgress < 100
                    ? "Applying AI styling..."
                    : "Finalizing...")}
            </p>
            <button
              onClick={(e) => {
                e.stopPropagation(); // Prevent triggering the file input click
                cancelUpload();
              }}
              className="mt-2 px-3 py-1 bg-danger-100 text-danger-700 text-xs rounded hover:bg-danger-200 transition-colors"
            >
              Cancel Upload
            </button>
          </div>
        ) : (
          <>
            <p className="text-sm text-neutral-500">
              Drag & drop or click to upload GeoJSON files
            </p>
            <p className="text-xs text-neutral-400 mt-1">
              Supports multiple files • Max size: {MAX_FILE_SIZE_FORMATTED}
            </p>
            <p className="text-xs text-neutral-400">Format: .geojson only</p>
          </>
        )}
      </div>
      {uploadError && (
        <div className="mt-2 p-2 bg-danger-100 border border-danger-400 text-danger-700 text-sm rounded">
          {uploadError}
        </div>
      )}
    </div>
  );
}
