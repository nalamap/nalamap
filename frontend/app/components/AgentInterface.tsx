"use client";

import { useState } from "react";
import { useGeoweaverAgent } from "../hooks/useGeoweaverAgent";
import { ArrowUp } from "lucide-react";
import { useLayerStore } from "../stores/layerStore";


interface Props {
  onLayerSelect: (layers: any[]) => void;
  conversation: { role: "user" | "agent"; content: string }[];
  setConversation: React.Dispatch<React.SetStateAction<{ role: "user" | "agent"; content: string }[]>>;
}

export default function AgentInterface({ onLayerSelect, conversation, setConversation }: Props) {
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";
  const [activeTool, setActiveTool] = useState<"search" | "process" | "geocode" | null>("search");
  const { input, setInput, geoweaverAgentResults, loading, error, queryGeoweaverAgent } = useGeoweaverAgent(API_BASE_URL);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    setConversation((prev) => [...prev, { role: "user", content: input }]);

    if (activeTool === "search") {
      await queryGeoweaverAgent(activeTool);
      setConversation((prev) => [
        ...prev,
        { role: "agent", content: "Search completed." },
      ]);
    } else if (activeTool === "geocode") {
      await queryGeoweaverAgent(activeTool);
      setConversation((prev) => [
        ...prev,
        { role: "agent", content: "Search completed." },
      ]);
    } else if (activeTool === "process") {
      setConversation((prev) => [
        ...prev,
        { role: "agent", content: `Processing request: ${input}` },
      ]);
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
    <div className="w-[26rem] min-w-[20rem] bg-white border-l shadow-lg flex flex-col overflow-hidden relative">
      {/* Chat content area */}
      <div className="flex-1 p-4">
        <div className="overflow-y-auto text-sm mb-2 px-2">
          {conversation.map((msg, idx) => (
            <div key={idx}>
              <strong>{msg.role === "user" ? "You:" : "Agent:"}</strong> {msg.content}
            </div>
          ))}
        </div>

        {(activeTool === "search" || activeTool === "geocode") && geoweaverAgentResults.length > 0 && (
          <div className="max-h-100 overflow-y-auto mb-2 px-2 bg-gray-50 rounded border">
            <div className="font-semibold p-1">Search Results:</div>
            {geoweaverAgentResults.map((result) => (
              <div
                key={result.resource_id}
                onClick={() => handleLayerSelect(result)}
                className="p-2 border-b last:border-none cursor-pointer hover:bg-gray-100"
              >
                <div className="font-bold text-sm">{result.name}</div>
                <div className="text-xs text-gray-600 truncate" title={result.llm_description}>
                  {result.llm_description}
                </div>
                <div className="text-[10px] text-gray-500">{result.source_type} | Score: {result.score}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Tool selector and input */}
      <div className="p-4 border-t flex flex-col gap-2 min-w-0">
        <div className="flex gap-2 justify-center">
          <button
            onClick={() => setActiveTool("search")}
            className={`px-2 py-1 rounded ${activeTool === "search" ? "bg-secondary-700 text-white" : "bg-gray-200"}`}
          >
            Search
          </button>
          <button
            onClick={() => setActiveTool("process")}
            className={`px-2 py-1 rounded ${activeTool === "process" ? "bg-secondary-700 text-white" : "bg-gray-200"}`}
          >
            Geoprocessing
          </button>
          <button
            onClick={() => setActiveTool("geocode")}
            className={`px-2 py-1 rounded ${activeTool === "geocode" ? "bg-secondary-700 text-white" : "bg-gray-200"}`}
          >
            Geocoding
          </button>
        </div>


        <form onSubmit={handleSubmit} className="relative">
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