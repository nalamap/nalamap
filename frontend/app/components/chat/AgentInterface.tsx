"use client";

import { useState, useEffect, useRef } from "react";
import wellknown from "wellknown";
import { useNaLaMapAgent } from "../../hooks/useNaLaMapAgent";
import { ArrowUp, X, Loader2 } from "lucide-react";
import { useLayerStore } from "../../stores/layerStore";
import { GeoDataObject } from "../../models/geodatamodel";
import { hashString } from "../../utils/hashUtil";
import ReactMarkdown from "react-markdown";
import { getApiBase } from "../../utils/apiBase";

// Helper function to determine score color and appropriate text color
const getScoreStyle = (score?: number): { backgroundColor: string; color: string } => {
  if (typeof score !== 'number' || score < 0 || score > 100) {
    return { backgroundColor: '#9ca3af', color: '#ffffff' }; // Default gray bg, white text (Tailwind gray-400)
  }
  // Map 0-100 to 0-120 hue (red to green)
  const hue = (score / 100) * 120;
  const saturation = 60;
  const lightness = 55;
  const backgroundColor = `hsl(${hue}, ${saturation}%, ${lightness}%)`;
  const textColor = '#ffffff';
  return { backgroundColor, color: textColor };
};

// Helper function to extract text content from message content
// Handles both string content and content blocks array formats
const extractTextContent = (content: any): string => {
  if (typeof content === 'string') {
    return content;
  }
  
  if (Array.isArray(content)) {
    // Extract text from content blocks
    return content
      .filter(block => block.type === 'text')
      .map(block => block.text || '')
      .join('\n');
  }
  
  // Fallback for unexpected content types
  return String(content);
};

// helper to get a WKT string from whatever format the store has
function toWkt(bbox: GeoDataObject["bounding_box"]): string | undefined {
  if (!bbox) return undefined;

  // 1) If it's already an object, stringify directly
  if (typeof bbox === "object") {
    return wellknown.stringify({
      type: "Polygon",
      coordinates: [[
        [bbox[0], bbox[1]],
        [bbox[2], bbox[1]],
        [bbox[2], bbox[3]],
        [bbox[0], bbox[3]],
        [bbox[0], bbox[1]]
      ]]
    });
  }

  // 2) If it's a string that looks like JSON, parse then stringify
  const trimmed = bbox.trim();
  if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
    try {
      const geojson = JSON.parse(bbox);
      return wellknown.stringify(geojson);
    } catch {
      // fall through: maybe it wasn't valid JSON after all
    }
  }

  // 3) Otherwise assume the string is already WKT
  return bbox;
}

export default function AgentInterface() {
  const API_BASE_URL = getApiBase();
  const [activeTool, setActiveTool] = useState<"search" | "chat" | "geocode" | "geoprocess" | "ai-style" | null>("chat");
  const { input, setInput, messages: conversation, geoDataList, loading, error, queryNaLaMapAgent } =
    useNaLaMapAgent(API_BASE_URL);
  // useNaLaMapAgent hook provides `conversation` (messages) state, no local state needed here
  const containerRef = useRef<HTMLDivElement>(null);
  const addLayer = useLayerStore((s) => s.addLayer);
  const getLayers = useLayerStore.getState;
  // show only first 5 results or all
  const [showAllResults, setShowAllResults] = useState(false);
  // state for description modal
  const [modalData, setModalData] = useState<GeoDataObject | null>(null);
  const [overlayData, setOverlayData] = useState<GeoDataObject | null>(null);
  // which one we'll use for the bbox filter
  const [selectedLayerId, setSelectedLayerId] = useState<string | null>(null);
  // portal filter string
  const [portalFilter, setPortalFilter] = useState<string>("");
  // show/hide tool responses
  const [expandedToolMessage, setExpandedToolMessage] = useState<Record<number, boolean>>({})
  // State for score info tooltip
  const [activeScoreInfoId, setActiveScoreInfoId] = useState<string | null>(null);
  // State for new Details pop-up
  const [activeDetailsId, setActiveDetailsId] = useState<string | null>(null);
  let apiOptions: { portal?: string; bboxWkt?: string } | undefined = undefined;

  const showToolMessages = false; // TODO: Move to settings

  //automate scroll to bottom with new entry
  useEffect(() => {
    const el = containerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [conversation]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    // The hook (queryNaLaMapAgent) will append the human message for us

    if (activeTool === "search") {
      let wkt: string | undefined = undefined;
      let portal: string | undefined = undefined;
      let fullQuery = input;
      const selected = useLayerStore.getState().layers.find((l) => l.selected);
      if (selected?.bounding_box) {
        wkt = toWkt(selected.bounding_box);
        if (wkt) {
          fullQuery += ` with given ${wkt}`;
        }
      }
      if (portalFilter.trim()) {
        fullQuery += ` portal:${portalFilter.trim()}`;
      }

      apiOptions = { // Pass bbox and portal as separate structured options
        portal: portal,
        bboxWkt: wkt
      };

      await queryNaLaMapAgent("search", undefined, apiOptions);

    }
    
    else if (activeTool === "geocode") {
      await queryNaLaMapAgent(activeTool);
    } else if (activeTool === "geoprocess") {
      await queryNaLaMapAgent(activeTool);
    } else if (activeTool === "chat") {
      await queryNaLaMapAgent(activeTool);
    } else if (activeTool === "ai-style") {
      // AI styling is now integrated into the main chat agent, so use "chat" endpoint
      await queryNaLaMapAgent("chat");

      /* TODO: Move to Backend
      // pass current layer URLs to the geoprocess endpoint
      const urls = getLayers().layers.map((l) => l.access_url);
      await query("geoprocess", urls);

      // once done, add each new URL as a layer
      processedUrls.forEach((url) => {
        const id = url.split("/").pop()!;
        addLayer({
          resource_id: id,
          name: `Processed ${id}`,
          source_type: "processed",
          access_url: url,
          format: "geojson",
          visible: true,
        });
      });

      // report back to user
      setConversation((c) => [
        ...c,
        {
          role: "agent",
          content: `Finished. Tools used: ${toolsUsed.join(", ")}`,
        },
      ]);*/
    }
  };

  const handleLayerSelect = (layer: any) => {
    useLayerStore.getState().addLayer(layer);
  };

  // determine which results to show
  const resultsToShow = showAllResults ? geoDataList : geoDataList.slice(0, 5);

  return (
    <div className="h-full w-full bg-gray-100 p-4 flex flex-col overflow-hidden relative border-l">
      {/* Header */}
      <h2 className="text-xl font-bold mb-4">Map Assistant</h2>

      {/* Chat content area */}
      <div ref={containerRef} className="overflow-auto flex-1 scroll-smooth pb-2">
        <div className="flex flex-col space-y-3">
          {conversation.map((msg, idx) => {
            const msgKey = msg.id?.trim() || hashString(`${idx}:${msg.type}:${msg.content}`);

            // 1) Handle an AI message that kicked off a tool call
            if (msg.type === 'ai' && msg.additional_kwargs?.tool_calls?.length) {

              if (!showToolMessages)
                return; // 

              const call = msg.additional_kwargs.tool_calls[0]
              const isOpen = !!expandedToolMessage[idx]

              return (
                <div
                  key={msgKey}
                  className="flex justify-start"
                >
                  <div className="max-w px-4 py-2 rounded-lg bg-gray-50 rounded-tl-none border">
                    {/* "Using tool…" header */}
                    <div className="text-sm font-medium">
                      Using tool ' {call.function.name} ' with arguments ' {call.function.arguments} '
                    </div>

                    {/* toggle button */}
                    <button
                      className="ml-2 px-2 py-1 bg-blue-500 text-white rounded text-xs"
                      onClick={() =>
                        setExpandedToolMessage((prev) => ({ ...prev, [idx]: !prev[idx] }))
                      }
                    >
                      {isOpen ? 'Hide result' : 'Show result'}
                    </button>

                    {/* if expanded, show the next message's content (must be type "tool") */}
                    {isOpen &&
                      conversation[idx + 1]?.type === 'tool' && (
                        <div className="mt-2 text-sm break-words whitespace-pre-wrap">
                          {conversation[idx + 1].content}
                        </div>
                      )}
                  </div>
                </div>
              )
            }

            // 2) Don't render standalone tool messages (they'll live under their AI caller)
            if (msg.type === 'tool') {
              return null
            }

            // 3) Fall back to your normal human/AI rendering
            const isHuman = msg.type === 'human'
            return (
            <div
              key={msgKey}
              className={`flex ${isHuman ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] px-4 py-2 rounded-lg ${isHuman
                  ? 'bg-blue-100 rounded-tr-none text-right'
                  : 'bg-gray-50 rounded-tl-none border'
                  }`}
                >
                  {isHuman ? (
                    <div className="text-sm break-words">{extractTextContent(msg.content)}</div>
                  ) : (
                    <div className="text-sm break-words chat-markdown">
                      <ReactMarkdown>{extractTextContent(msg.content)}</ReactMarkdown>
                    </div>
                  )}
                  <div className="text-xs text-gray-500 mt-1">
                    {isHuman
                      ? 'You'
                      : msg.type === 'ai'
                        ? 'Agent'
                        : 'Unknown'}
                  </div>
                </div>
              </div>
            )
          })}

          {(loading &&
            <div className="flex justify-start mb-2">
              <div className="flex items-center space-x-2 max-w-[80%] px-4 py-2 rounded-lg bg-gray-50 rounded-tl-none border">
                {/* spinning loader */}
                <Loader2 size={16} className="animate-spin text-gray-500" />
                <span className="text-sm text-gray-500">NaLaMap Agent is working on your request...</span>
              </div>
            </div>
          )}
        </div>

        {(activeTool === "search" || activeTool === "geocode" || activeTool === "chat" || activeTool === "geoprocess") && geoDataList.length > 0 && !loading && (
          <div className="mt-6 mb-2 px-2 bg-gray-50 rounded border">
            <div className="font-semibold p-1">Search Results:</div>
            {resultsToShow.map((result) => (
              <div key={result.id} className="p-2 border-b last:border-none hover:bg-gray-100">
                <div onClick={() => handleLayerSelect(result)} className="cursor-pointer">
                  <div className="font-bold text-sm">{result.title}</div>
                  <div className="text-xs text-gray-600 truncate" title={result.llm_description}>{result.llm_description}</div>
                  <div className="flex items-center mt-1" style={{ position: 'relative' }}>
                    {/* Score Button with color scaling 
                    <button
                      className="px-2 py-1 text-xs rounded"
                      style={getScoreStyle(result.score != null ? Math.round(result.score * 100) : undefined)}
                      onClick={(e) => {
                        e.stopPropagation();
                        // If score button were to have its own pop-up via activeScoreInfoId:
                        // setActiveScoreInfoId(activeScoreInfoId === result.id ? null : result.id);
                        setActiveDetailsId(null); // Close details if score is clicked
                      }}
                    >
                      Score: {result.score != null ? Math.round(result.score * 100) : 'N/A'}
                    </button>*/}
                    {/* Layer Type Button */}
                    <button
                      className="px-2 py-1 text-xs rounded"
                      style={getScoreStyle(result.score != null ? Math.round(result.score * 100) : undefined)}
                      onClick={(e) => {
                        e.stopPropagation();
                        // If score button were to have its own pop-up via activeScoreInfoId:
                        // setActiveScoreInfoId(activeScoreInfoId === result.id ? null : result.id);
                        setActiveDetailsId(null); // Close details if score is clicked
                      }}
                    >
                      Type: {result.layer_type && `${result.layer_type}`}
                    </button>
                    {/* Details Button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setActiveDetailsId(activeDetailsId === result.id ? null : result.id);
                        setActiveScoreInfoId(null); // Close score tooltip if details is clicked
                      }}
                      className="ml-2 px-2 py-1 bg-gray-300 text-black rounded text-xs hover:bg-gray-400"
                    >
                      Details
                    </button>

                    {/* Add to Map Button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleLayerSelect(result);
                      }}
                      className="ml-2 px-2 py-1 bg-blue-500 text-white rounded text-xs hover:bg-blue-600"
                    >
                      Add to Map
                    </button>

                    {/* Details Pop-up */}
                    {activeDetailsId === result.id && (
                      <div
                        style={{
                          position: 'absolute',
                          bottom: '100%', // Position above the button row
                          left: '0',
                          marginBottom: '5px',
                          backgroundColor: 'white',
                          color: '#333',
                          border: '1px solid #ddd',
                          padding: '10px',
                          borderRadius: '4px',
                          boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
                          zIndex: 50,
                          fontSize: '12px',
                          width: '280px',
                          textAlign: 'left',
                        }}
                        onClick={(e) => e.stopPropagation()} // Prevent closing when clicking inside pop-up
                      >
                        <h4 className="font-bold text-sm mb-1">{result.title || 'Details'}</h4>
                        <p className="text-xs mb-1"><strong>Description:</strong> {result.llm_description || result.description || 'N/A'}</p>
                        <p className="text-xs mb-1"><strong>Data Source:</strong> {result.data_source || 'N/A'}</p>
                        <p className="text-xs mb-1"><strong>Layer Type:</strong> {result.layer_type || 'N/A'}</p>
                        {result.bounding_box && <p className="text-xs whitespace-pre-wrap break-all"><strong>BBox:</strong> {typeof result.bounding_box === 'string' ? result.bounding_box : JSON.stringify(result.bounding_box)}</p>}
                      </div>
                    )}
                  </div>
                  <div className="text-[10px] text-gray-500 mt-1">{result.data_origin}</div>
                </div>
              </div>
            ))}
            {geoDataList.length > 5 && (
              <button onClick={() => setShowAllResults((s) => !s)} className="w-full py-2 text-center text-blue-600 hover:underline">
                {showAllResults ? "Show Less" : `Show More (${geoDataList.length - 5} more)`}
              </button>
            )}
          </div>
        )}
      </div>

      < hr className="my-4" />

      {/* Tool selector and input */}
      < div className="mb-4" >
        <div className="flex flex-wrap gap-2 justify-center sm:flex-row flex-col">
          <button
            onClick={() => setActiveTool("chat")}
            className={`px-2 py-1 rounded text-white`}
            style={{
              backgroundColor: activeTool === "chat" ? 'rgb(102, 102, 102)' : 'rgb(64, 64, 64)'
            }}
          >
            Chat
          </button>
          <button
            onClick={() => setActiveTool("search")}
            className={`px-2 py-1 rounded text-white hidden`}
            style={{
              backgroundColor: activeTool === "search" ? 'rgb(102, 102, 102)' : 'rgb(64, 64, 64)'
            }}
          >
            Search
          </button>
          <button
            onClick={() => setActiveTool("geoprocess")}
            className={`px-2 py-1 rounded text-white hidden`}
            style={{
              backgroundColor: activeTool === "geoprocess" ? 'rgb(102, 102, 102)' : 'rgb(64, 64, 64)'
            }}
          >
            Geoprocessing
          </button>
          <button
            onClick={() => setActiveTool("geocode")}
            className={`px-2 py-1 rounded text-white hidden`}
            style={{
              backgroundColor: activeTool === "geocode" ? 'rgb(102, 102, 102)' : 'rgb(64, 64, 64)'
            }}
          >
            Geocode
          </button>
          <button
            onClick={() => setActiveTool("ai-style")}
            className={`px-2 py-1 rounded text-white hidden`}
            style={{
              backgroundColor: activeTool === "ai-style" ? 'rgb(102, 102, 102)' : 'rgb(64, 64, 64)'
            }}
          >
            AI Style
          </button>
        </div>


        <form onSubmit={handleSubmit} className="relative mt-4">
          <textarea
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              // Auto-resize the textarea
              e.target.style.height = 'auto';
              e.target.style.height = `${e.target.scrollHeight}px`;
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
            placeholder={activeTool === "ai-style" ? "Describe how to style your layers (e.g., 'make it red', 'thick blue borders', 'transparent fill')..." : `Type a ${activeTool} command...`}
            className="w-full border border-gray-300 bg-gray-100 rounded px-4 py-3 pr-10 focus:outline-none focus:ring focus:ring-secondary-300 resize-none overflow-hidden"
            style={{ minHeight: '45px', maxHeight: '200px' }}
            rows={1}
          />
          <button
            type="submit"
            className="absolute right-2 bottom-2 text-gray-500 hover:text-gray-900 transition-colors"
            title="Send"
          >
            <ArrowUp size={20} />
          </button>
        </form>
      </div >
      {/* Overlay details panel */}
      {
        overlayData && (
          <div className="fixed right-4 top-16 w-1/3 max-h-[70vh] overflow-y-auto bg-white shadow-lg rounded p-4 z-50">
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-lg font-bold">{overlayData.title}</h3>
              <button onClick={() => setOverlayData(null)}><X /></button>
            </div>
            <p className="text-sm text-gray-700 mb-2">{overlayData.llm_description}</p>
            <div className="text-[10px] text-gray-500 mb-1">Source: {overlayData.data_source}</div>
            <div className="text-[10px] text-gray-500 mb-1">Layer Type: {overlayData.layer_type}</div>
            <div className="text-[10px] text-gray-500 mb-1">
              <span style={getScoreStyle(overlayData.score != null ? Math.round(overlayData.score * 100) : undefined)}>
                Score: {overlayData.score != null ? Math.round(overlayData.score * 100) : 'N/A'}
              </span>
            </div>
            {overlayData.bounding_box && (
              <pre className="text-[10px] text-gray-500 mt-2 whitespace-pre-wrap break-all">BBox: {overlayData.bounding_box}</pre>
            )}
          </div>
        )
      }
    </div >
  );
}
