"use client";

import { useState, useEffect, useRef } from "react";
import wellknown from "wellknown";
import { useGeoweaverAgent } from "../hooks/useGeoweaverAgent";
import { ArrowUp, X, Loader2 } from "lucide-react";
import { useLayerStore } from "../stores/layerStore";
import { GeoDataObject } from "../models/geodatamodel";
import { hashString } from "../utils/hashUtil";

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

interface Props {
  onLayerSelect: (layers: any[]) => void;
  conversation: { role: "user" | "agent"; content: string }[];
  setConversation: React.Dispatch<React.SetStateAction<{ role: "user" | "agent"; content: string }[]>>;
}

export default function AgentInterface({ onLayerSelect, conversation: conversation_old, setConversation }: Props) {
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";
  const [activeTool, setActiveTool] = useState<"search" | "chat" | "geocode" | "geoprocess" | null>("chat");
  const { input, setInput, messages: conversation, geoDataList, loading, error, queryGeoweaverAgent } = useGeoweaverAgent(API_BASE_URL);
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
  let apiOptions: { portal?: string; bboxWkt?: string } | undefined = undefined;

  const showToolMessages = true;
  //automate scroll to bottom with new entry
  useEffect(() => {
    const el = containerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [conversation]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    // Add user message
    setConversation((c) => [...c, { role: "user", content: input }]);

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

      await queryGeoweaverAgent("search", undefined, apiOptions);

      setConversation((c) => [
        ...c,
        { role: "agent", content: "Search complete." },
      ]);
    }


    if (activeTool === "geocode") {
      await queryGeoweaverAgent(activeTool);
      setConversation((c) => [...c, { role: "agent", content: "Done." }]);
    } else if (activeTool === "geoprocess") {
      await queryGeoweaverAgent(activeTool);
      setConversation((c) => [
        ...c,
        { role: "agent", content: `Processing: ${input}` },
      ]);
    } else if (activeTool === "chat") {
      await queryGeoweaverAgent(activeTool);
      setConversation((prev) => [
        ...prev,
        { role: "agent", content: `Processing request: ${input}` },
      ]);

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
    setConversation((prev) => [
      ...prev,
      { role: "agent", content: `Layer "${layer.name}" added to the map.` },
    ]);
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
                  <div className="text-sm break-words">{msg.content}</div>
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
          <div className="max-h-100 overflow-y-auto mt-6 mb-2 px-2 bg-gray-50 rounded border">
            <div className="font-semibold p-1">Search Results:</div>
            {resultsToShow.map((result) => (
              <div key={result.id} className="p-2 border-b last:border-none hover:bg-gray-100">
                <div onClick={() => handleLayerSelect(result)} className="cursor-pointer">
                  <div className="font-bold text-sm">{result.title}</div>
                  <div className="text-xs text-gray-600 truncate" title={result.llm_description}>{result.llm_description}</div>
                  <div className="text-[10px] text-gray-500">{result.data_origin} | Score: {result.score}</div>
                </div>
                <button onClick={() => setOverlayData(result)} className="ml-2 px-2 py-1 bg-blue-500 text-white rounded text-xs">Details</button>
                <button onClick={() => handleLayerSelect(result)} className="ml-2 px-2 py-1 bg-blue-500 text-white rounded text-xs">Add to Map</button>
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
            className={`px-2 py-1 rounded text-white`}
            style={{
              backgroundColor: activeTool === "search" ? 'rgb(102, 102, 102)' : 'rgb(64, 64, 64)'
            }}
          >
            Search
          </button>
          <button
            onClick={() => setActiveTool("geoprocess")}
            className={`px-2 py-1 rounded text-white`}
            style={{
              backgroundColor: activeTool === "geoprocess" ? 'rgb(102, 102, 102)' : 'rgb(64, 64, 64)'
            }}
          >
            Geoprocessing
          </button>
          <button
            onClick={() => setActiveTool("geocode")}
            className={`px-2 py-1 rounded text-white`}
            style={{
              backgroundColor: activeTool === "geocode" ? 'rgb(102, 102, 102)' : 'rgb(64, 64, 64)'
            }}
          >
            Geocode
          </button>
        </div>


        <form onSubmit={handleSubmit} className="relative mt-4">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={`Type a ${activeTool} command...`}
            className="w-full border border-gray-300 bg-gray-100 rounded px-4 py-3 pr-10 focus:outline-none focus:ring focus:ring-secondary-300"
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
            <div className="text-[10px] text-gray-500">Score: {overlayData.score}</div>
            {overlayData.bounding_box && (
              <pre className="text-[10px] text-gray-500 mt-2 whitespace-pre-wrap break-all">BBox: {overlayData.bounding_box}</pre>
            )}
          </div>
        )
      }
    </div >
  );
}