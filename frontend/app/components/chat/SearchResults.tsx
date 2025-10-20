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
