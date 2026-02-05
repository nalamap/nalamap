"use client";

import { useState, useEffect, useRef } from "react";
import { X } from "lucide-react";
import { GeoDataObject } from "../../models/geodatamodel";
import WorldBankChart, {
  ChartDataItem,
  ChartByCategory,
} from "../charts/WorldBankChart";

interface SearchResultsProps {
  results: GeoDataObject[];
  loading: boolean;
  onSelectLayer: (result: GeoDataObject) => void;
}

// Check if a result is from World Bank and has chart data
function isWorldBankResult(result: GeoDataObject): boolean {
  return (
    result.data_source_id === "worldBankIndicators" ||
    result.data_source === "World Bank"
  );
}

// Extract chart data from properties
function getChartData(result: GeoDataObject): {
  chartData: ChartDataItem[];
  chartByCategory: ChartByCategory;
  country: string;
  dataPeriod: string;
} | null {
  const props = result.properties as Record<string, unknown> | undefined;
  if (!props || !props.chart_data || !Array.isArray(props.chart_data)) {
    return null;
  }

  return {
    chartData: props.chart_data as ChartDataItem[],
    chartByCategory: (props.chart_by_category || {}) as ChartByCategory,
    country: (props.country as string) || "Unknown",
    dataPeriod: (props.data_period as string) || "",
  };
}

export default function SearchResults({
  results,
  loading,
  onSelectLayer,
}: SearchResultsProps) {
  const [showAllResults, setShowAllResults] = useState(false);
  const [activeDetailsId, setActiveDetailsId] = useState<string | null>(null);
  const [chartModalId, setChartModalId] = useState<string | null>(null);
  // Track which results have been auto-opened to avoid re-triggering
  const autoOpenedRef = useRef<Set<string>>(new Set());

  // Auto-open chart modal for World Bank results
  useEffect(() => {
    if (results.length > 0) {
      // Find the first World Bank result that hasn't been auto-opened yet
      const worldBankResult = results.find(
        (r) => isWorldBankResult(r) && getChartData(r) && !autoOpenedRef.current.has(r.id)
      );

      if (worldBankResult) {
        autoOpenedRef.current.add(worldBankResult.id);
        setChartModalId(worldBankResult.id);
      }
    }
  }, [results]);

  if (results.length === 0 || loading) {
    return null;
  }

  const resultsToShow = showAllResults ? results : results.slice(0, 5);

  return (
    <div className="mt-6 mb-2 px-2 bg-neutral-50 rounded border">
      <div className="font-semibold p-1">Search Results:</div>
      {resultsToShow.map((result) => {
        const isWorldBank = isWorldBankResult(result);
        const chartDataResult = isWorldBank ? getChartData(result) : null;

        return (
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

              {/* Chart Button - Only for World Bank results */}
              {isWorldBank && chartDataResult && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setChartModalId(chartModalId === result.id ? null : result.id);
                  }}
                  className={`px-2 py-1 rounded text-xs flex-shrink-0 ${
                    chartModalId === result.id
                      ? "bg-blue-600 text-white"
                      : "bg-blue-100 text-blue-700 hover:bg-blue-200"
                  }`}
                >
                  View Chart 📊
                </button>
              )}

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
                      
                      <div className="space-y-1">
                        {/* Source Layers */}
                        {result.processing_metadata.origin_layers && 
                         result.processing_metadata.origin_layers.length > 0 && (
                          <p className="text-xs text-neutral-900 dark:text-neutral-100">
                            <strong className="text-neutral-700 dark:text-neutral-200">Source Layers:</strong> {result.processing_metadata.origin_layers.join(', ')}
                          </p>
                        )}
                        
                        {/* Operation */}
                        <p className="text-xs text-neutral-900 dark:text-neutral-100 capitalize">
                          <strong className="text-neutral-700 dark:text-neutral-200">Operation:</strong> {result.processing_metadata.operation}
                        </p>
                        
                        {/* CRS Used */}
                        <p className="text-xs text-neutral-900 dark:text-neutral-100">
                          <strong className="text-neutral-700 dark:text-neutral-200">CRS Used:</strong> {result.processing_metadata.crs_used}
                          {result.processing_metadata.auto_selected && ' 🎯'}
                          {result.processing_metadata.authority === 'WKT' && result.processing_metadata.wkt && (
                            <>
                              {' '}
                              <button
                                type="button"
                                className="underline text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  alert(`Custom CRS definition (WKT):\n\n${result.processing_metadata!.wkt!}`);
                                }}
                                aria-label="Show custom CRS WKT details"
                              >
                                (details)
                              </button>
                            </>
                          )}
                        </p>
                        
                        {/* CRS Name */}
                        <p className="text-xs text-neutral-900 dark:text-neutral-100">
                          <strong className="text-neutral-700 dark:text-neutral-200">CRS Name:</strong> {result.processing_metadata.crs_name}
                        </p>
                        
                        {/* Projection Property */}
                        {result.processing_metadata.projection_property && (
                          <p className="text-xs text-neutral-900 dark:text-neutral-100 capitalize">
                            <strong className="text-neutral-700 dark:text-neutral-200">Projection:</strong> {result.processing_metadata.projection_property}
                          </p>
                        )}
                        
                        {/* Selection Reason */}
                        {result.processing_metadata.selection_reason && (
                          <p className="text-xs text-neutral-900 dark:text-neutral-100">
                            <strong className="text-neutral-700 dark:text-neutral-200">Selection Reason:</strong> {result.processing_metadata.selection_reason}
                          </p>
                        )}
                        
                        {/* Expected Error */}
                        {result.processing_metadata.expected_error !== undefined && (
                          <p className="text-xs text-neutral-900 dark:text-neutral-100">
                            <strong className="text-neutral-700 dark:text-neutral-200">Expected Error:</strong> &lt;{result.processing_metadata.expected_error}%
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
        );
      })}

      {/* World Bank Chart Modal */}
      {chartModalId && (() => {
        const result = results.find(r => r.id === chartModalId);
        if (!result) return null;

        const chartDataResult = getChartData(result);
        if (!chartDataResult) return null;

        return (
          <div
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-[200]"
            onClick={() => setChartModalId(null)}
          >
            <div
              className="bg-white rounded-lg shadow-2xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Modal Header */}
              <div className="sticky top-0 bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between z-10">
                <h2 className="text-lg font-bold text-gray-900">
                  📊 {result.title || result.name}
                </h2>
                <button
                  onClick={() => setChartModalId(null)}
                  className="text-neutral-400 hover:text-neutral-600 p-1 hover:bg-neutral-100 rounded"
                  aria-label="Close chart"
                >
                  <X size={20} />
                </button>
              </div>

              {/* Chart Content */}
              <div className="p-4">
                <WorldBankChart
                  country={chartDataResult.country}
                  chartData={chartDataResult.chartData}
                  chartByCategory={chartDataResult.chartByCategory}
                  dataPeriod={chartDataResult.dataPeriod}
                />
              </div>
            </div>
          </div>
        );
      })()}

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
