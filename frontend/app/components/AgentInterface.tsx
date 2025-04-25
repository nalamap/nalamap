"use client";

import { useState, useEffect, useRef } from "react";
import { useGeoweaverAgent } from "../hooks/useGeoweaverAgent";
import { ArrowUp } from "lucide-react";
import { useLayerStore } from "../stores/layerStore";


interface Props {
  onLayerSelect: (layers: any[]) => void;
  conversation: { role: "user" | "agent"; content: string }[];
  setConversation: React.Dispatch<React.SetStateAction<{ role: "user" | "agent"; content: string }[]>>;
}

export default function AgentInterface({ onLayerSelect, conversation: conversation_old, setConversation }: Props) {
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";
  const [activeTool, setActiveTool] = useState < "search" | "chat" | "geocode" | "geoprocess" | null>("chat");
  const { input, setInput, messages: conversation, geoDataList, loading, error, queryGeoweaverAgent } = useGeoweaverAgent(API_BASE_URL);
  const containerRef = useRef<HTMLDivElement>(null);
  const addLayer = useLayerStore((s) => s.addLayer);
  const getLayers = useLayerStore.getState;

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

    if (activeTool === "search" || activeTool === "geocode") {
      await queryGeoweaverAgent(activeTool);
      setConversation((c) => [...c, { role: "agent", content: "Done." }]);
    } else if (activeTool === "geoprocess") {
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

    setInput("");
  };

  const handleLayerSelect = (layer: any) => {
    useLayerStore.getState().addLayer(layer);
    setConversation((prev) => [
      ...prev,
      { role: "agent", content: `Layer "${layer.name}" added to the map.` },
    ]);
  };

  return (
    <div className="h-full w-full bg-gray-100 p-4 flex flex-col overflow-hidden relative border-l">
      {/* Header */}
      <h2 className="text-xl font-bold mb-4">Map Assistant</h2>

      {/* Chat content area */}
      <div ref={containerRef} className="overflow-auto flex-1 scroll-smooth pb-2">
        <div className="flex flex-col space-y-3">
          {conversation.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] px-4 py-2 rounded-lg ${msg.role === "user"
                    ? "bg-blue-100 rounded-tr-none text-right"
                    : "bg-gray-50 rounded-tl-none border"
                  }`}
              >
                <div className="text-sm break-words">
                  {msg.content}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {msg.role === "user" ? "You" : "Agent"}
                </div>
              </div>
            </div>
          ))}
        </div>

        {(activeTool === "search" || activeTool === "geocode" || activeTool === "chat") && geoDataList.length > 0 && (
          <div className="max-h-100 overflow-y-auto mt-6 mb-2 px-2 bg-gray-50 rounded border">
            <div className="font-semibold p-1">Search Results:</div>
            {geoDataList.map((result) => (
              <div
                key={result.id}
                onClick={() => handleLayerSelect(result)}
                className="p-2 border-b last:border-none cursor-pointer hover:bg-gray-100"
              >
                <div className="font-bold text-sm">{result.name}</div>
                <div className="text-xs text-gray-600 truncate" title={result.llm_description}>
                  {result.llm_description}
                </div>
                <div className="text-[10px] text-gray-500">{result.data_origin} | Score: {result.score}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <hr className="my-4" />

      {/* Tool selector and input */}
      <div className="mb-4">
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
            className={`px-2 py-1 rounded ${activeTool === "geoprocess" ? "bg-secondary-700 text-white" : "bg-gray-200"}`}
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
      </div>
    </div>
  );
}