"use client";

import { useState, useEffect, useRef } from "react";
import { X, MapPin, Square, Minus } from "lucide-react";
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

// --- Overpass grouping ---

interface OverpassProps {
  featureCount: number;
  queryAmenityKey: string;
  queryLocation: string;
  queryOsmTag: string;
  geometryType: string;
  geometryLabel: string;
  geometryHint: string;
  sampleNames: string[];
  spatialExtent: string | null;
}

function isOverpassCollection(result: GeoDataObject): boolean {
  return result.data_source_id === "geocodeOverpassCollection";
}

function getOverpassProps(result: GeoDataObject): OverpassProps {
  const props = result.properties as Record<string, unknown> | undefined;
  return {
    featureCount: (props?.feature_count as number) || 0,
    queryAmenityKey: (props?.query_amenity_key as string) || "",
    queryLocation: (props?.query_location as string) || "",
    queryOsmTag: (props?.query_osm_tag as string) || "",
    geometryType: (props?.geometry_type_collected as string) || "",
    geometryLabel: (props?.geometry_label as string) || "",
    geometryHint: (props?.geometry_hint as string) || "",
    sampleNames: Array.isArray(props?.sample_names)
      ? (props.sample_names as string[])
      : [],
    spatialExtent: (props?.spatial_extent as string) || null,
  };
}

interface OverpassGroup {
  groupKey: string;
  groupTitle: string;
  spatialExtent: string | null;
  results: GeoDataObject[];
}

function groupOverpassResults(results: GeoDataObject[]): {
  groups: OverpassGroup[];
  others: GeoDataObject[];
} {
  const groups: OverpassGroup[] = [];
  const others: GeoDataObject[] = [];
  const groupMap = new Map<string, OverpassGroup>();

  for (const result of results) {
    if (!isOverpassCollection(result)) {
      others.push(result);
      continue;
    }
    const p = getOverpassProps(result);
    const key = `${p.queryOsmTag}__${p.queryLocation}`;
    if (!groupMap.has(key)) {
      const group: OverpassGroup = {
        groupKey: key,
        groupTitle: p.queryAmenityKey
          ? `${p.queryAmenityKey} in ${p.queryLocation}`
          : p.queryLocation,
        spatialExtent: p.spatialExtent,
        results: [],
      };
      groupMap.set(key, group);
      groups.push(group);
    }
    groupMap.get(key)!.results.push(result);
  }

  return { groups, others };
}

function GeometryTypeIcon({ type }: { type: string }) {
  const t = type.toLowerCase();
  if (t === "points") return <MapPin size={11} className="flex-shrink-0 mt-px" />;
  if (t === "areas") return <Square size={11} className="flex-shrink-0 mt-px" />;
  if (t === "lines") return <Minus size={11} className="flex-shrink-0 mt-px" />;
  return null;
}

// Shared details popup used by both card types
function DetailsPopup({
  result,
  onClose,
}: {
  result: GeoDataObject;
  onClose: () => void;
}) {
  return (
    <div
      className="obsidian-floating-card search-results-popup fixed left-4 right-4 bottom-20 max-h-[60vh] overflow-y-auto p-4 text-sm z-50 md:absolute md:bottom-full md:left-0 md:right-auto md:mb-2 md:w-80 md:max-h-96"
      onClick={(e) => e.stopPropagation()}
    >
      <h4 className="search-result-title text-sm mb-2 break-words">
        {result.title || "Details"}
      </h4>
      <p className="search-result-copy text-xs mb-2 break-words">
        <strong>Description:</strong>{" "}
        {result.llm_description || result.description || "N/A"}
      </p>
      <p className="search-result-copy text-xs mb-2 break-words">
        <strong>Data Source:</strong> {result.data_source || "N/A"}
      </p>
      <p className="search-result-copy text-xs mb-2">
        <strong>Layer Type:</strong> {result.layer_type || "N/A"}
      </p>
      {result.bounding_box && (
        <p className="search-result-copy text-xs break-all">
          <strong>BBox:</strong>{" "}
          {typeof result.bounding_box === "string"
            ? result.bounding_box
            : JSON.stringify(result.bounding_box)}
        </p>
      )}

      {result.processing_metadata && (
        <div className="pt-3 mt-3 border-t border-neutral-200">
          <h5 className="font-semibold text-neutral-700 mb-2 text-xs">
            Processing Information
          </h5>
          <div className="space-y-1">
            {result.processing_metadata.origin_layers &&
              result.processing_metadata.origin_layers.length > 0 && (
                <p className="text-xs text-neutral-900 dark:text-neutral-100">
                  <strong className="text-neutral-700 dark:text-neutral-200">
                    Source Layers:
                  </strong>{" "}
                  {result.processing_metadata.origin_layers.join(", ")}
                </p>
              )}
            <p className="text-xs text-neutral-900 dark:text-neutral-100 capitalize">
              <strong className="text-neutral-700 dark:text-neutral-200">
                Operation:
              </strong>{" "}
              {result.processing_metadata.operation}
            </p>
            <p className="text-xs text-neutral-900 dark:text-neutral-100">
              <strong className="text-neutral-700 dark:text-neutral-200">
                CRS Used:
              </strong>{" "}
              {result.processing_metadata.crs_used}
              {result.processing_metadata.auto_selected && " 🎯"}
              {result.processing_metadata.authority === "WKT" &&
                result.processing_metadata.wkt && (
                  <>
                    {" "}
                    <button
                      type="button"
                      className="underline text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300"
                      onClick={(e) => {
                        e.stopPropagation();
                        alert(
                          `Custom CRS definition (WKT):\n\n${result.processing_metadata!.wkt!}`
                        );
                      }}
                      aria-label="Show custom CRS WKT details"
                    >
                      (details)
                    </button>
                  </>
                )}
            </p>
            <p className="text-xs text-neutral-900 dark:text-neutral-100">
              <strong className="text-neutral-700 dark:text-neutral-200">
                CRS Name:
              </strong>{" "}
              {result.processing_metadata.crs_name}
            </p>
            {result.processing_metadata.projection_property && (
              <p className="text-xs text-neutral-900 dark:text-neutral-100 capitalize">
                <strong className="text-neutral-700 dark:text-neutral-200">
                  Projection:
                </strong>{" "}
                {result.processing_metadata.projection_property}
              </p>
            )}
            {result.processing_metadata.selection_reason && (
              <p className="text-xs text-neutral-900 dark:text-neutral-100">
                <strong className="text-neutral-700 dark:text-neutral-200">
                  Selection Reason:
                </strong>{" "}
                {result.processing_metadata.selection_reason}
              </p>
            )}
            {result.processing_metadata.expected_error !== undefined && (
              <p className="text-xs text-neutral-900 dark:text-neutral-100">
                <strong className="text-neutral-700 dark:text-neutral-200">
                  Expected Error:
                </strong>{" "}
                &lt;{result.processing_metadata.expected_error}%
              </p>
            )}
          </div>
        </div>
      )}

      {/* Query Construction Section (for geocoding results) */}
      {result.processing_metadata?.query_intent && (
        <div className="pt-3 mt-3 border-t border-neutral-200 dark:border-neutral-600">
          <h5 className="font-semibold text-neutral-700 dark:text-neutral-200 mb-2 text-xs">
            Query Construction
          </h5>

          {/* Search intent */}
          <div className="mb-3 p-2 bg-blue-50 dark:bg-blue-900/20 rounded border border-blue-200 dark:border-blue-800">
            <span className="text-xs font-semibold text-blue-800 dark:text-blue-300">
              Search Intent
            </span>
            <p className="text-xs text-neutral-900 dark:text-neutral-100 mt-1">
              &quot;{result.processing_metadata.query_intent}&quot;
              {result.processing_metadata.query_location && (
                <> in {result.processing_metadata.query_location}</>
              )}
            </p>
          </div>

          {/* Resolution method */}
          {result.processing_metadata.resolution_detail && (
            <div className="mb-2">
              <span className="font-semibold text-neutral-700 dark:text-neutral-300 text-xs">
                Resolution:
              </span>
              <p className="text-xs text-neutral-900 dark:text-neutral-100">
                {result.processing_metadata.resolution_detail}
              </p>
            </div>
          )}

          {/* Tags used */}
          {result.processing_metadata.osm_tags_used &&
            result.processing_metadata.osm_tags_used.length > 0 && (
              <div className="mb-2">
                <span className="font-semibold text-neutral-700 dark:text-neutral-300 text-xs">
                  OSM Tags ({result.processing_metadata.osm_tags_used.length}):
                </span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {result.processing_metadata.osm_tags_used.map((tag: string) => (
                    <span
                      key={tag}
                      className="px-1.5 py-0.5 bg-neutral-200 dark:bg-neutral-700 text-neutral-800 dark:text-neutral-200 rounded text-xs font-mono"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            )}

          {/* Excluded tags (if any) */}
          {result.processing_metadata.osm_tags_excluded &&
            result.processing_metadata.osm_tags_excluded.length > 0 && (
              <div className="mb-2">
                <span className="font-semibold text-neutral-700 dark:text-neutral-300 text-xs">
                  Excluded:
                </span>
                {result.processing_metadata.osm_tags_excluded.map(
                  (e: { tag: string; reason: string }) => (
                    <p key={e.tag} className="text-xs text-neutral-600 dark:text-neutral-400 italic">
                      {e.tag} — {e.reason}
                    </p>
                  )
                )}
              </div>
            )}

          {/* Refinement hint */}
          <p className="text-xs text-neutral-600 dark:text-neutral-400 mt-2 italic">
            Ask in the chat to refine this query
          </p>
        </div>
      )}

      <button
        onClick={(e) => {
          e.stopPropagation();
          onClose();
        }}
        className="obsidian-button-ghost mt-3 w-full py-2 text-xs md:hidden"
      >
        Close
      </button>
    </div>
  );
}

// Card for a single geometry type within an Overpass group
function GeometryCard({
  result,
  onSelectLayer,
  activeDetailsId,
  setActiveDetailsId,
}: {
  result: GeoDataObject;
  onSelectLayer: (r: GeoDataObject) => void;
  activeDetailsId: string | null;
  setActiveDetailsId: (id: string | null) => void;
}) {
  const p = getOverpassProps(result);

  return (
    <div className="obsidian-floating-card search-result-card p-2 transition-colors">
      {/* Header: geometry label + feature count */}
      <div className="flex items-start justify-between gap-1 mb-1">
        <div className="search-result-title flex items-center gap-1 text-xs min-w-0">
          <GeometryTypeIcon type={p.geometryType} />
          <span className="break-words">{p.geometryLabel || p.geometryType}</span>
        </div>
        <span className="obsidian-chip text-[10px] flex-shrink-0 whitespace-nowrap">
          {p.featureCount.toLocaleString()} features
        </span>
      </div>

      {/* Hint */}
      {p.geometryHint && (
        <div className="search-result-hint text-[10px] mb-1 italic">
          {p.geometryHint}
        </div>
      )}

      {/* Sample names preview */}
      {p.sampleNames.length > 0 && (
        <div className="search-result-example text-[10px] mb-2 line-clamp-1">
          e.g. {p.sampleNames.slice(0, 3).join(", ")}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex flex-wrap items-center gap-1.5 relative">
        <button
          onClick={(e) => {
            e.stopPropagation();
            onSelectLayer(result);
          }}
          className="obsidian-button-primary px-2 py-1 text-xs flex-shrink-0"
        >
          Add to Map
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            setActiveDetailsId(
              activeDetailsId === result.id ? null : result.id
            );
          }}
          className="obsidian-button-ghost px-2 py-1 text-xs flex-shrink-0"
        >
          Details
        </button>

        {activeDetailsId === result.id && (
          <DetailsPopup
            result={result}
            onClose={() => setActiveDetailsId(null)}
          />
        )}
      </div>
    </div>
  );
}

export default function SearchResults(props: SearchResultsProps) {
  const { results, onSelectLayer } = props;
  const [showAllResults, setShowAllResults] = useState(false);
  const [activeDetailsId, setActiveDetailsId] = useState<string | null>(null);
  const [chartModalId, setChartModalId] = useState<string | null>(null);
  const autoOpenedRef = useRef<Set<string>>(new Set());

  // Auto-open chart modal for World Bank results
  useEffect(() => {
    if (results.length > 0) {
      const worldBankResult = results.find(
        (r) =>
          isWorldBankResult(r) &&
          getChartData(r) &&
          !autoOpenedRef.current.has(r.id)
      );
      if (worldBankResult) {
        autoOpenedRef.current.add(worldBankResult.id);
        setChartModalId(worldBankResult.id);
      }
    }
  }, [results]);

  if (results.length === 0) {
    return null;
  }

  const { groups, others } = groupOverpassResults(results);
  const othersToShow = showAllResults ? others : others.slice(0, 5);

  return (
    <div className="search-results obsidian-results-panel mt-6 mb-2 px-2">
      <div className="search-results-title p-1">Search Results</div>

      {/* Overpass geometry groups */}
      {groups.map((group) => (
        <div key={group.groupKey} className="search-result-group">
          {/* Group header */}
          <div className="mb-2">
            <div className="search-result-group-title text-sm">
              {group.groupTitle}
            </div>
            {group.spatialExtent && (
              <div className="search-result-group-copy text-[10px]">
                {group.spatialExtent}
              </div>
            )}
            {group.results.length > 1 && (
              <div className="search-result-group-copy text-[10px] mt-0.5">
                Choose one or more geometry types to add:
              </div>
            )}
          </div>

          {/* One card per geometry type */}
          <div className="flex flex-col gap-2">
            {group.results.map((result) => (
              <GeometryCard
                key={result.id}
                result={result}
                onSelectLayer={onSelectLayer}
                activeDetailsId={activeDetailsId}
                setActiveDetailsId={setActiveDetailsId}
              />
            ))}
          </div>
        </div>
      ))}

      {/* Non-Overpass results (World Bank, Nominatim, etc.) */}
      {othersToShow.map((result) => {
        const isWorldBank = isWorldBankResult(result);
        const chartDataResult = isWorldBank ? getChartData(result) : null;

        return (
          <div
            key={result.id}
            className="search-result-row"
          >
            <div
              onClick={() => onSelectLayer(result)}
              className="cursor-pointer"
            >
              <div className="search-result-title text-sm break-words">{result.title}</div>
              <div
                className="search-result-copy text-xs line-clamp-2"
                title={result.llm_description}
              >
                {result.llm_description}
              </div>

              {/* Buttons row */}
              <div className="flex flex-wrap items-center gap-2 mt-2 relative">
                <button
                  className="obsidian-chip px-2 py-1 text-xs flex-shrink-0"
                  onClick={(e) => {
                    e.stopPropagation();
                    setActiveDetailsId(null);
                  }}
                >
                  Type: {result.layer_type && `${result.layer_type}`}
                </button>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setActiveDetailsId(
                      activeDetailsId === result.id ? null : result.id
                    );
                  }}
                  className="obsidian-button-ghost px-2 py-1 text-xs flex-shrink-0"
                >
                  Details
                </button>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectLayer(result);
                  }}
                  className="obsidian-button-primary px-2 py-1 text-xs flex-shrink-0"
                >
                  Add to Map
                </button>

                {isWorldBank && chartDataResult && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setChartModalId(
                        chartModalId === result.id ? null : result.id
                      );
                    }}
                    className={`px-2 py-1 rounded text-xs flex-shrink-0 ${
                      chartModalId === result.id
                        ? "obsidian-button-primary"
                        : "obsidian-button-ghost"
                    }`}
                  >
                    View Chart 📊
                  </button>
                )}

                {activeDetailsId === result.id && (
                  <DetailsPopup
                    result={result}
                    onClose={() => setActiveDetailsId(null)}
                  />
                )}
              </div>

              <div className="search-result-meta text-[10px] mt-1">
                {result.data_origin}
              </div>
            </div>
          </div>
        );
      })}

      {/* World Bank Chart Modal */}
      {chartModalId &&
        (() => {
          const result = results.find((r) => r.id === chartModalId);
          if (!result) return null;
          const chartDataResult = getChartData(result);
          if (!chartDataResult) return null;

          return (
            <div
              className="obsidian-modal"
              onClick={() => setChartModalId(null)}
            >
              <div
                className="obsidian-modal-card"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="obsidian-modal-header flex items-center justify-between px-4 py-3">
                  <h2 className="obsidian-heading text-lg">
                    📊 {result.title || result.name}
                  </h2>
                  <button
                    onClick={() => setChartModalId(null)}
                    className="obsidian-icon-button"
                    aria-label="Close chart"
                  >
                    <X size={20} />
                  </button>
                </div>
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

      {others.length > 5 && (
        <button
          onClick={() => setShowAllResults((s) => !s)}
          className="obsidian-button-ghost mt-3 w-full py-2 text-center"
        >
          {showAllResults
            ? "Show Less"
            : `Show More (${others.length - 5} more)`}
        </button>
      )}
    </div>
  );
}
