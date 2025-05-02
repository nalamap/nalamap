"use client";

import { useState } from "react";
import MapSwitcher from "./MapSwitcher";
import { useGeoweaverAgent } from "../hooks/useGeoweaverAgent";

type Message = { role: "user" | "agent"; content: string };

export default function MapWithChat() {
  // API URL from environment variable or fallback.
  const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";
  // Custom search hook.
  const { input, setInput, geoDataList: geoweaverAgentResults, loading, error, queryGeoweaverAgent } =
    useGeoweaverAgent(API_BASE_URL);
  // State to store the layer(s) the user selects to visualize.
  // Initialize with a default empty layer to ensure the map loads with our baselayers
  const [mapLayers, setMapLayers] = useState<any[]>([]);
  // State for conversation with the agent.
  const [conversation, setConversation] = useState<Message[]>([]);
  // Control visibility of the search results panel.
  const [isSearchResultsVisible, setIsSearchResultsVisible] =
    useState(true);

  // TODO: verify
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await queryGeoweaverAgent("search");
    setIsSearchResultsVisible(true);
  };

  const handleLayerSelect = (result: any) => {
    // Update the map layers.
    setMapLayers([result]);
    // Hide the search results after selection.
    setIsSearchResultsVisible(false);
    // Trigger a conversation with the agent.
    const userMsg = `I selected the layer "${result.name}". Can you suggest additional layers?`;
    setConversation((prev) => [...prev, { role: "user", content: userMsg }]);
    // Simulate an agent response.
    setTimeout(() => {
      const additionalLayers = [      // Agent responds with additional layers in JSON.
        {
          resource_id: "agent-2",
          source_type: "wms",
          name: "Hydrology",
          title: "Hydrology",
          description: "Water bodies, rivers, and streams.",
          access_url:
            "https://io.apps.fao.org/geoserver/wms?service=WMS&request=GetMap&layers=AQUAMAPS:rivers_africa&format=image/png&transparent=true",
          format: "image/png",
          llm_description: "Blue hues represent water features.",
          bounding_box: null,
          score: 0.85,
        }
      ];
      setConversation((prev) => [
        ...prev,
        { role: "agent", content: "Based on your selection, here are some additional layers:" },
      ]);
      // Update the map layers with the additional layers.
      setMapLayers((prev) => [...prev, ...additionalLayers]);
    }, 1500);
  };

  return (
    <div className="relative h-full w-full">
      {/* MapSwitcher renders the map with the selected layers */}
      <MapSwitcher layers={mapLayers} />

      {/* Top center search bar */}
      <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-50 w-3/4">
        <form onSubmit={handleSubmit} className="flex">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Search for layers..."
            className="w-full border rounded-l px-4 py-2 focus:outline-none focus:ring"
          />
          <button
            type="submit"
            className="bg-blue-500 text-white px-4 py-2 rounded-r"
          >
            Search
          </button>
        </form>
        {loading && (
          <div className="mt-2 text-center text-gray-700">Loading...</div>
        )}
        {error && (
          <div className="mt-2 text-center text-red-500">{error}</div>
        )}
        {isSearchResultsVisible && geoweaverAgentResults.length > 0 && (
          <div className="mt-2 bg-primary rounded shadow p-4 max-h-64 overflow-y-auto">
            <h3 className="font-bold mb-2 text-center">
              Search Results
            </h3>
            <div className="space-y-2">
              {geoweaverAgentResults.map((result) => (
                <div
                  key={result.id}
                  className="p-2 border rounded cursor-pointer hover:bg-primary-100"
                  onClick={() => handleLayerSelect(result)}
                >
                  <div className="font-bold">{result.name}</div>
                  <div className="text-sm truncate" title={result.llm_description}>
                    {result.llm_description}
                  </div>
                  <div className="text-xs text-gray-600">
                    {result.data_origin} | Score: {result.score}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Chat prompt overlay at bottom left */}
      <div className="absolute left-4 bottom-4 w-80 bg-white shadow-lg rounded-lg overflow-hidden flex flex-col z-50">
        <div className="flex-1 overflow-y-auto p-2 border-b">
          {conversation.map((msg, idx) => (
            <div key={idx} className="mb-2 text-sm">
              <strong>{msg.role === "user" ? "User:" : "Agent:"}</strong>{" "}
              {msg.content}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
