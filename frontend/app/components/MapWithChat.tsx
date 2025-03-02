"use client";

import { useState } from "react";
import { useChat } from "@ai-sdk/react";
import MapLibreMap from "./MapLibreMap";

export default function MapWithChat() {
  // State to store search results from the chat response.
  const [searchResults, setSearchResults] = useState<any[]>([]);
  // State to store the layer(s) the user selects to visualize.
  const [mapLayers, setMapLayers] = useState<any[]>([]);

  const { messages, input, handleInputChange, handleSubmit } = useChat({
    api: "/api/search",
    id: "map-chat",
    streamProtocol: "text",
    onResponse: async (response) => {
      const clonedResponse = response.clone();
      const data = await clonedResponse.json();
      console.log(data);
      if (data && data.messages && Array.isArray(data.messages)) {
        // Assume that the assistant message attaches the results in a "data" field.
        const assistantMsg = data.messages.find(
          (msg: any) => msg.role === "assistant" && msg.parts
        );
        if (assistantMsg) {
          setSearchResults(assistantMsg.parts);
        }
      }
    },
    onError: (error) => {
      console.error("Chat API Error:", error);
    },
  });

  return (
    <div className="relative h-full w-full">
      {/* Map component */}
      <MapLibreMap layers={mapLayers} />
      {/* Chat overlay */}
      <div className="absolute left-4 bottom-4 w-80 h-96 bg-white shadow-lg rounded-lg overflow-hidden flex flex-col">
        {/* Chat history container */}
        <div className="flex-1 overflow-y-auto p-2 border-b">
          {messages.map((msg, idx) => (
            <div key={msg.id || idx} className="mb-2 text-sm">
              <strong>{msg.role === "user" ? "User:" : "Agent:"}</strong>{" "}
              {msg.content}
            </div>
          ))}
        </div>
        {/* Input and search results */}
        <div className="relative">
          <form onSubmit={handleSubmit} className="p-2">
            <input
              type="text"
              value={input}
              onChange={handleInputChange}
              placeholder="Type your query..."
              className="w-full border rounded p-2 focus:outline-none focus:ring"
            />
          </form>
          {/* Render search results as an absolute dropdown above the input */}
          {searchResults.length > 0 && (
            <div className="absolute left-0 right-0 bottom-full mb-2 max-h-40 overflow-y-auto bg-white shadow rounded z-10">
              <h3 className="font-bold p-2 border-b">
                Select a layer to visualize:
              </h3>
              {searchResults.map((result) => (
                <button
                  key={result.id}
                  onClick={() => setMapLayers([result])}
                  className="block w-full text-left p-1 hover:bg-gray-100"
                >
                  {result.llm_description || result.access_url}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
