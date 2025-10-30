"use client";

import { useState } from "react";
import { GeoDataObject } from "../../models/geodatamodel";

interface SearchResultsProps {
  results: GeoDataObject[];
  loading: boolean;
  onSelectLayer: (result: GeoDataObject) => void;
}

export default function SearchResults({
  results,
  loading,
  onSelectLayer,
}: SearchResultsProps) {
  const [showAllResults, setShowAllResults] = useState(false);
  const [activeDetailsId, setActiveDetailsId] = useState<string | null>(null);

  if (results.length === 0 || loading) {
    return null;
  }

  const resultsToShow = showAllResults ? results : results.slice(0, 5);

  return (
    <div className="mt-6 mb-2 px-2 bg-neutral-50 rounded border">
      <div className="font-semibold p-1">Search Results:</div>
      {resultsToShow.map((result) => (
        <div
          key={result.id}
          className="p-2 border-b last:border-none hover:bg-neutral-100"
        >
          <div
            onClick={() => onSelectLayer(result)}
            className="cursor-pointer"
          >
            <div className="font-bold text-sm break-words">{result.title}</div>
            <div
              className="text-xs text-gray-600 line-clamp-2"
              title={result.llm_description}
            >
              {result.llm_description}
            </div>

            {/* Buttons row - now with responsive flex-wrap */}
            <div className="flex flex-wrap items-center gap-2 mt-2 relative">
              {/* Layer Type Button */}
              <button
                className="px-2 py-1 text-xs rounded bg-primary-200 text-primary-900 hover:bg-primary-300 flex-shrink-0"
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveDetailsId(null);
                }}
              >
                Type: {result.layer_type && `${result.layer_type}`}
              </button>

              {/* Details Button */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveDetailsId(
                    activeDetailsId === result.id ? null : result.id,
                  );
                }}
                className="px-2 py-1 bg-neutral-300 text-neutral-900 rounded text-xs hover:bg-neutral-400 flex-shrink-0"
              >
                Details
              </button>

              {/* Add to Map Button */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectLayer(result);
                }}
                className="px-2 py-1 bg-info-600 text-neutral-50 rounded text-xs hover:bg-info-700 flex-shrink-0"
              >
                Add to Map
              </button>

              {/* Details Pop-up */}
              {activeDetailsId === result.id && (
                <div
                  className="fixed left-4 right-4 bottom-20 max-h-[60vh] overflow-y-auto bg-white border border-gray-300 rounded-lg shadow-xl p-4 z-50 md:absolute md:bottom-full md:left-0 md:right-auto md:mb-2 md:w-80 md:max-h-96"
                  onClick={(e) => e.stopPropagation()}
                >
                  <h4 className="font-bold text-sm mb-2 break-words">
                    {result.title || "Details"}
                  </h4>
                  <p className="text-xs mb-2 break-words">
                    <strong>Description:</strong>{" "}
                    {result.llm_description ||
                      result.description ||
                      "N/A"}
                  </p>
                  <p className="text-xs mb-2 break-words">
                    <strong>Data Source:</strong>{" "}
                    {result.data_source || "N/A"}
                  </p>
                  <p className="text-xs mb-2">
                    <strong>Layer Type:</strong>{" "}
                    {result.layer_type || "N/A"}
                  </p>
                  {result.bounding_box && (
                    <p className="text-xs break-all">
                      <strong>BBox:</strong>{" "}
                      {typeof result.bounding_box === "string"
                        ? result.bounding_box
                        : JSON.stringify(result.bounding_box)}
                    </p>
                  )}
                  
                  {/* Processing Metadata Section */}
                  {result.processing_metadata && (
                    <div className="pt-3 mt-3 border-t border-neutral-200">
                      <h5 className="font-semibold text-neutral-700 mb-2 text-xs">Processing Information</h5>
                      
                      {/* Source Layers - Prominently displayed */}
                      {result.processing_metadata.origin_layers && 
                       result.processing_metadata.origin_layers.length > 0 && (
                        <div className="mb-2 p-2 bg-secondary-50 dark:bg-secondary-900 rounded border border-secondary-200 dark:border-secondary-700">
                          <span className="font-semibold text-secondary-700 dark:text-secondary-300 text-xs uppercase tracking-wide block mb-1">Source Layers</span>
                          <p className="text-xs text-neutral-700 dark:text-neutral-300">
                            {result.processing_metadata.origin_layers.join(', ')}
                          </p>
                        </div>
                      )}
                      
                      {/* Operation Summary */}
                      <div className="mb-2 p-2 bg-info-50 dark:bg-info-900 rounded border border-info-200 dark:border-info-700">
                        <p className="text-xs text-neutral-700">
                          <strong className="text-info-700">
                            {result.processing_metadata.operation.charAt(0).toUpperCase() + 
                             result.processing_metadata.operation.slice(1)}
                          </strong> operation
                          {result.processing_metadata.operation === 'buffer' && 
                           result.description?.match(/\d+\.?\d*\s*(m|km|meters|kilometers)/i) && 
                           ` with ${result.description.match(/\d+\.?\d*\s*(m|km|meters|kilometers)/i)![0]}`}
                          {' using '}
                          <strong className="text-info-700">{result.processing_metadata.crs_used}</strong>
                          {result.processing_metadata.auto_selected && ' 🎯'}
                        </p>
                      </div>
                      
                      {/* CRS Details */}
                      <div className="space-y-1">
                        <p className="text-xs">
                          <strong>CRS Name:</strong> {result.processing_metadata.crs_name}
                        </p>
                        <p className="text-xs capitalize">
                          <strong>Projection:</strong> {result.processing_metadata.projection_property}
                        </p>
                        {result.processing_metadata.auto_selected && result.processing_metadata.selection_reason && (
                          <p className="text-xs">
                            <strong>Selection Reason:</strong> {result.processing_metadata.selection_reason}
                          </p>
                        )}
                        {result.processing_metadata.expected_error !== undefined && (
                          <p className="text-xs">
                            <strong>Expected Error:</strong> &lt;{result.processing_metadata.expected_error}%
                          </p>
                        )}
                      </div>
                    </div>
                  )}
                  
                  {/* Close button for mobile */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setActiveDetailsId(null);
                    }}
                    className="mt-3 w-full py-2 bg-neutral-200 hover:bg-neutral-300 rounded text-xs font-medium md:hidden"
                  >
                    Close
                  </button>
                </div>
              )}
            </div>

            <div className="text-[10px] text-gray-500 mt-1">
              {result.data_origin}
            </div>
          </div>
        </div>
      ))}
      {results.length > 5 && (
        <button
          onClick={() => setShowAllResults((s) => !s)}
          className="w-full py-2 text-center text-blue-600 hover:underline"
        >
          {showAllResults
            ? "Show Less"
            : `Show More (${results.length - 5} more)`}
        </button>
      )}
    </div>
  );
}
